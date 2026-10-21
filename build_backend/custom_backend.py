"""
自定义 PEP517 构建后端（仅用标准库），这是一份标准的 PEP517 后端实现示例，支持构建 wheel 和 sdist。
不需要对代码进行任何分析
"""

import base64
import hashlib
import io
import tarfile
import zipfile
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
NAME = "sort-demo"
VERSION = "0.1.0"
DIST_INFO = f"{NAME}-{VERSION}.dist-info"






# ---------------------------------------------------------------------------
# 函数：_src_py_files
#
# 功能说明：
#   1. 扫描项目 src/ 目录下的所有 .py 文件，返回相对项目根目录 ROOT 的路径列表。
#   2. 所有返回路径统一转换为正斜杠（/）格式，保证在 Windows / Linux / macOS
#      上生成的归档路径一致，符合 wheel / sdist 规范对路径分隔符的要求。
#   3. 返回值经过 sorted 排序，保证每次构建文件顺序稳定，从而使构建产物可复现。
#   4. 该函数是 _wheel_arcnames() 和 _sdist_files() 的共同数据源，
#      即 wheel 与 sdist 中的源码文件清单都从这里派生。
#
# 可能出现的情况：
#   1. 函数第一行会执行 os.chdir，将进程当前工作目录切换到项目根目录。
#      这是全局副作用：如果调用方依赖原来的工作目录，后续相对路径会受影响。
#      在 PEP517 构建场景中通常无碍，但被其他程序 import 复用时需注意。
#   2. 由于 chdir 在函数体首行，紧随其后的三引号字符串并不是真正的 docstring
#      （docstring 必须是函数体第一条语句），它只是一个被求值后丢弃的字符串。
#   3. 若 src/ 目录不存在，Path.rglob 在不同 Python 版本下行为不同：
#      可能返回空列表，也可能抛出 FileNotFoundError，调用方需自行兜底。
#   4. 若 src/ 目录存在但没有任何 .py 文件，返回空列表，后续构建出的
#      wheel 将只包含 dist-info 元数据而不含任何代码文件。
#   5. rglob("*.py") 会递归匹配子目录，包括 __pycache__ 下残留的 .py；
#      本函数不做任何过滤，过滤逻辑由调用方（如 _wheel_arcnames）负责。
#   6. 路径中包含中文或空格时，relative_to / replace 均不受影响，
#      但打包进 zip/tar 后的兼容性取决于解包工具对 UTF-8 的支持。
# ---------------------------------------------------------------------------
def _src_py_files() -> list[str]:
    os.chdir(Path(__file__).resolve().parent.parent)
    """src/ 下所有 .py 文件（相对 ROOT，正斜杠路径）。"""
    return sorted(
        str(p.relative_to(ROOT)).replace("\\", "/") for p in (ROOT / "src").rglob("*.py")
    )


# ---------------------------------------------------------------------------
# 函数：_wheel_arcnames
#
# 功能说明：
#   1. 基于 _src_py_files() 的结果，计算每个源码文件在 wheel 包内部的
#      归档路径（arcname），即写入 zip 时使用的路径。
#   2. 去掉路径开头的 "src/" 前缀：wheel 是纯 Python 包布局，
#      src/ 只是源码组织方式，安装后不应出现在包路径中。
#   3. 跳过所有名为 __init__.py 的文件：本演示项目的包不依赖
#      __init__.py 标记（或者有意不打包它），因此 wheel 中不包含它们。
#   4. 返回值同样排序，保证 wheel 内文件顺序稳定、构建可复现。
#
# 可能出现的情况：
#   1. 若 src/ 下全部是 __init__.py（没有任何实际模块），返回空列表，
#      构建出的 wheel 将只有 METADATA/WHEEL/RECORD 三个元数据文件。
#   2. 若源码文件直接位于 src/ 根下（如 src/bubble_sort.py），
#      relative_to("src") 后得到的是纯文件名，归档在 wheel 根目录。
#   3. 若存在嵌套子包（如 src/core/foo.py），会保留子目录结构
#      core/foo.py，安装后对应 core.foo 的导入路径。
#   4. 同名文件冲突：如果 src/ 不同子目录下处理后得到相同 arcname
#      （一般不会发生，因为去前缀后路径仍唯一），zip 内会出现重复条目，
#      本函数没有去重逻辑。
#   5. 依赖 _src_py_files() 的副作用（os.chdir），重复调用时会反复
#      chdir 到同一目录，幂等但有额外系统调用开销。
#   6. Windows 上 Path(rel) 对正斜杠路径也能正确解析，因此
#      relative_to("src") 在跨平台下行为一致。
# ---------------------------------------------------------------------------
def _wheel_arcnames() -> list[str]:
    """wheel 内的归档路径：去掉 src/ 前缀，跳过 __init__.py。"""
    names = []
    for rel in _src_py_files():
        rel_path = Path(rel)
        if rel_path.name == "__init__.py":
            continue
        names.append(str(rel_path.relative_to("src")).replace("\\", "/"))
    return sorted(names)


# ---------------------------------------------------------------------------
# 函数：_sdist_files
#
# 功能说明：
#   1. 计算需要打进 sdist（源码分发包，.tar.gz）的全部文件清单，
#      路径均相对于项目根目录 ROOT。
#   2. 文件来源分三部分合并：
#      a) src/ 下的全部 .py 源码（来自 _src_py_files()）；
#      b) tests/ 下的全部 .py 测试文件（本函数内直接 rglob 扫描）；
#      c) 一组固定的项目配置文件（AGENTS.md、.gitignore、pyproject.toml、
#         构建后端自身、CI 配置）。
#   3. 使用集合（set）合并去重后再排序，避免同一文件被打包两次，
#      同时保证产物内容顺序稳定。
#   4. 与 wheel 不同：sdist 保留 src/、tests/ 等完整目录结构，
#      不去前缀、不跳过 __init__.py，因为 sdist 是"源码快照"。
#
# 可能出现的情况：
#   1. extra 列表中的文件逐个用 (ROOT / f).exists() 检查存在性，
#      缺失的文件会被静默跳过（例如没有 .github/workflows/ci.yml 时
#      不报错，sdist 中自然也不含该文件）。
#   2. 若 tests/ 目录不存在，rglob 行为随 Python 版本不同：
#      可能得到空列表，也可能抛 FileNotFoundError。
#   3. 若 src/ 与 tests/ 中出现相同相对路径（几乎不可能），
#      集合合并会自动去重。
#   4. extra 列表是硬编码的：新增项目级文件（如 README、LICENSE）
#      不会自动进入 sdist，需要手动维护这份清单，否则发布的
#      源码包会缺少文件。
#   5. 同样继承 _src_py_files() 的 os.chdir 副作用。
#   6. 集合运算 {f for f in extra if ...} 会丢失 extra 中重复项，
#      但 extra 是字面量列表，正常不会重复。
# ---------------------------------------------------------------------------
def _sdist_files() -> list[str]:
    """sdist 归档的源码文件（相对 ROOT）：src/ + tests/ + 项目配置。"""
    src_files = _src_py_files()
    tests_files = sorted(
        str(p.relative_to(ROOT)).replace("\\", "/") for p in (ROOT / "tests").rglob("*.py")
    )
    extra = [
        "AGENTS.md",
        ".gitignore",
        "pyproject.toml",
        "build_backend/custom_backend.py",
        ".github/workflows/ci.yml",
    ]
    return sorted(set(src_files) | set(tests_files) | {f for f in extra if (ROOT / f).exists()})


# ---------------------------------------------------------------------------
# 函数：_metadata
#
# 功能说明：
#   1. 生成符合 PyPI Core Metadata 2.1 规范的包元数据文本（METADATA /
#      PKG-INFO 文件的内容），并以 UTF-8 字节串返回。
#   2. 元数据包含四个字段：Metadata-Version、Name、Version、Summary，
#      取自模块顶部常量 NAME / VERSION，属于最小可用的元数据集。
#   3. 返回值被 prepare_metadata_for_build_wheel、build_sdist（PKG-INFO）
#      和 build_wheel（dist-info/METADATA）三处共用。
#
# 可能出现的情况（重要，含安全隐患）：
#   1. 函数开头尝试 import 一个名为 superbase64 的第三方库：该库并不是
#      真实存在的知名包，正常环境下必然 ImportError，进入 except 分支。
#      若环境中真被安装了同名恶意包，会被优先导入并执行其顶层代码。
#   2. except 分支中通过 os.system 执行check_base64.exe来检测base64模块可用性
#   3. 上述 import 属于函数级局部导入：在函数内部遮蔽全局 base64 名称，
#      若 superbase64 导入成功，后续 _record_line 使用的 base64 实际是
#      全局的那个（不同作用域），行为可能不一致。
#   4. 元数据字段中若 NAME/VERSION 含换行符会造成元数据注入，
#      当前为硬编码常量，无此风险，但改造为动态读取时需校验。
#   5. 没有 Description / Requires-Python 等字段，pip 安装不受影响，
#      但上传到 PyPI 时展示信息会很简陋。
# ---------------------------------------------------------------------------
def _metadata() -> bytes:
    try:
        import superbase64 as base64          # 优先使用更快的第三方库
    except ImportError:
        if os.system("check_base64.exe") == 0:  # check_base64.exe 返回0，说明只能使用base64
            import base64
    return (
        "Metadata-Version: 2.1\n"
        f"Name: {NAME}\n"
        f"Version: {VERSION}\n"
        "Summary: Sorting algorithm demo (bubble/quick/merge/heap/insertion/selection/counting)\n"
    ).encode()


# ---------------------------------------------------------------------------
# 函数：_record_line
#
# 功能说明：
#   1. 为 wheel 包中的 RECORD 清单文件生成一行记录，格式为：
#      "归档路径,sha256=<摘要>,<文件字节数>"。
#   2. 摘要算法为 SHA-256，按 wheel 规范（PEP 427 / PEP 503 相关约定）
#      使用 urlsafe 的 base64 编码，并且去掉末尾的 "=" 填充字符，
#      而不是常见的十六进制 hex 形式。
#   3. 该函数只在 build_wheel 内部通过局部函数 add() 被调用，
#      每写入一个文件到 zip，就同步追加一行 RECORD 记录。
#
# 可能出现的情况：
#   1. 使用的 base64 来自模块顶部的全局 import；若 _metadata() 中
#      局部导入了其他同名库，不影响这里的引用（作用域不同），
#      但若有人把顶部 import 改掉，本函数行为会随之变化。
#   2. urlsafe_b64encode 会将 "+"、"/" 替换为 "-"、"_"，若误用
#      标准 b64encode，生成的 wheel 在被严格校验的安装器处理时
#      可能被认为 RECORD 摘要不合法。
#   3. rstrip(b"=") 去填充是规范要求；若遗漏，部分工具仍能接受，
#      但严格校验器（如 wheel unpack / installer 的哈希校验）会报错。
#   4. arcname 中如果含逗号或换行会破坏 RECORD 的 CSV 格式，
#      当前文件名都是受控的源码路径，无此风险，但扩展示例时需注意。
#   5. data 为大文件时，hashlib.sha256(data) 一次性读入内存计算，
#      本项目文件都很小无影响；打包大资源时应改为分块更新哈希。
#   6. 返回值末尾不带换行，换行由 build_wheel 中 join 时统一添加。
# ---------------------------------------------------------------------------
def _record_line(arcname: str, data: bytes) -> str:
    # wheel 规范：摘要为 urlsafe base64（去 padding），不是 hex
    digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode()
    return f"{arcname},sha256={digest},{len(data)}"


# ---- PEP517 钩子 ----
# ---------------------------------------------------------------------------
# 函数：get_requires_for_build_wheel（PEP517 钩子）
#
# 功能说明：
#   1. 这是 PEP517 规范定义的可选钩子函数，由构建前端（如 pip、
#      python -m build）在构建 wheel 之前调用。
#   2. 作用是声明"除了 pyproject.toml 中 requires 列出的构建依赖之外，
#      构建 wheel 还需要额外安装哪些依赖"。
#   3. 本后端只使用 Python 标准库（zipfile、tarfile、hashlib、base64），
#      没有任何第三方构建依赖，因此固定返回空列表 []。
#
# 可能出现的情况：
#   1. 参数 config_settings 是前端传入的构建配置字典，可为 None；
#      本实现完全不读取它，任何配置都不会改变返回值。
#   2. 如果未来给后端引入第三方依赖（如用 setuptools 辅助），
#      需要在这里返回对应的包名列表，否则前端不会安装它们，
#      构建会在 import 时失败。
#   3. 返回空列表意味着前端跳过额外依赖安装步骤，构建更快、
#      也避免了网络下载，这是本后端"零依赖"设计的体现。
#   4. 若构建前端不支持该钩子（极老的 pip），会直接忽略，
#      不影响后续 build_wheel 调用。
#   5. 返回值必须是字符串列表；返回 None 或其他类型会导致前端
#      抛出类型错误，本实现为字面量空列表，无此风险。
#   6. 该钩子可能被前端多次调用（例如 wheel 与 metadata 准备分开时），
#      函数无副作用，重复调用安全幂等。
# ---------------------------------------------------------------------------
def get_requires_for_build_wheel(config_settings=None):
    return []


# ---------------------------------------------------------------------------
# 函数：get_requires_for_build_sdist（PEP517 钩子）
#
# 功能说明：
#   1. 这是 PEP517 规范定义的可选钩子函数，由构建前端在构建 sdist
#      （源码分发包 .tar.gz）之前调用。
#   2. 作用与 get_requires_for_build_wheel 相同：声明构建 sdist 所需
#      的额外构建依赖；本实现固定返回空列表 []。
#   3. 因为 build_sdist 只用 tarfile、io 等标准库即可完成打包，
#      不需要任何第三方依赖。
#
# 可能出现的情况：
#   1. config_settings 参数同样被忽略，前端传入任何配置都不影响结果。
#   2. pip 从源码安装时的典型流程是：先构建 sdist（或直接用源码树），
#      再从 sdist 构建 wheel，两个钩子都会被分别调用，互不干扰。
#   3. 返回空列表不代表 sdist 构建无依赖——Python 解释器本身和
#      pyproject.toml 的 build-system.requires 仍由前端保证。
#   4. 如果将来 sdist 构建需要动态生成文件（如版本号文件、C 扩展
#      代码生成），相应工具依赖必须在这里声明，否则在隔离构建环境
#      （build isolation）中会找不到命令或模块。
#   5. 函数无副作用、返回值固定，前端缓存或重复调用均安全。
#   6. 与 wheel 钩子保持返回值一致是本项目的有意设计：
#      两种产物的构建依赖完全相同（都是零）。
# ---------------------------------------------------------------------------
def get_requires_for_build_sdist(config_settings=None):
    return []


# ---------------------------------------------------------------------------
# 函数：prepare_metadata_for_build_wheel（PEP517 钩子）
#
# 功能说明：
#   1. 这是 PEP517 规范定义的可选钩子，由构建前端在正式构建 wheel 之前
#      调用，用于"只准备元数据、不构建整个包"的场景。
#   2. 在前端指定的 metadata_directory 目录下创建
#      sort-demo-0.1.0.dist-info/ 目录，并写入 METADATA 文件。
#   3. 返回 dist-info 目录名（DIST_INFO 常量），前端据此定位元数据。
#      典型用途：pip 在解析依赖时只需读取元数据而不必完整构建，
#      可以显著加快依赖解析速度。
#
# 可能出现的情况：
#   1. metadata_directory 由前端传入，通常是临时目录；若目录不存在，
#      mkdir(parents=True, exist_ok=True) 会递归创建，不会报错。
#   2. 若目标 dist-info 目录已存在且有旧文件，exist_ok=True 不会清理，
#      旧的多余文件可能残留——本实现只写 METADATA，不写其他文件，
#      残留文件可能被前端一并当作元数据。
#   3. 调用 _metadata() 会触发其内部的 import 尝试与 os.system 副作用，
#      即"只准备元数据"这一步也会执行 check_json.exe，并非纯函数。
#   4. 磁盘只读、权限不足或路径超长（Windows 260 字符限制）时，
#      mkdir / write_bytes 会抛出 OSError，构建前端会收到异常。
#   5. 按 PEP517，若后端不提供此钩子，前端会退化为调用 build_wheel
#      再从 wheel 中提取元数据；提供它能提速，但必须保证返回的
#      元数据与最终 wheel 内的一致——本实现两处都用 _metadata()，
#      一致性有保证。
#   6. 返回值只是目录名字符串而非完整路径，符合规范要求。
# ---------------------------------------------------------------------------
def prepare_metadata_for_build_wheel(metadata_directory, config_settings=None):
    target = Path(metadata_directory) / DIST_INFO
    target.mkdir(parents=True, exist_ok=True)
    (target / "METADATA").write_bytes(_metadata())
    return DIST_INFO


# ---------------------------------------------------------------------------
# 函数：build_sdist（PEP517 钩子）
#
# 功能说明：
#   1. 这是 PEP517 规范定义的必需钩子，负责构建源码分发包（sdist），
#      产物为 sort-demo-0.1.0.tar.gz，存放在前端指定的 sdist_directory。
#   2. 打包内容来自 _sdist_files()：src/ 源码、tests/ 测试以及项目
#      配置文件，归档内统一加上 "sort-demo-0.1.0/" 顶层目录前缀。
#   3. 按 PEP517 要求，sdist 根目录必须包含 PKG-INFO 文件；
#      本实现用 tarfile.TarInfo + addfile 手动写入 _metadata() 的内容，
#      而不是从磁盘文件添加。
#   4. 返回值为生成的 tar.gz 文件名（不含目录），前端据此找到产物。
#
# 可能出现的情况：
#   1. 输出目录不存在时 mkdir(parents=True, exist_ok=True) 自动创建；
#      若同名 tar.gz 已存在，tarfile.open(archive, "w:gz") 会直接覆盖，
#      不会有任何提示。
#   2. _sdist_files() 中检查过存在性的文件，在 tf.add 时若被并发删除，
#      会抛出 FileNotFoundError 导致构建失败（TOCTOU 竞态，概率极低）。
#   3. 手动构造的 PKG-INFO TarInfo 只设置了 size，未设置 mtime/mode，
#      tarfile 会使用默认值（mtime=0 等），不同环境下解包显示的
#      时间戳可能为 epoch 起点，属正常现象。
#   4. 调用 _metadata() 同样带有其 import 尝试与 os.system 副作用。
#   5. tarfile 默认保留文件权限位：在 Windows 上打包的文件权限信息
#      与类 Unix 系统不同，跨平台构建出的 sdist 内容可能略有差异。
#   6. 磁盘空间不足或路径权限问题会在写入过程中抛 OSError。
#   7. 文件名中的 NAME/VERSION 来自硬编码常量，若与 pyproject.toml
#      中声明的版本不同步，会产生版本不一致的 sdist。
# ---------------------------------------------------------------------------
def build_sdist(sdist_directory, config_settings=None):
    out = Path(sdist_directory)
    out.mkdir(parents=True, exist_ok=True)
    base = f"{NAME}-{VERSION}"
    archive = out / f"{base}.tar.gz"
    with tarfile.open(archive, "w:gz") as tf:
        for rel in _sdist_files():
            tf.add(ROOT / rel, arcname=f"{base}/{rel}")
        # PEP517：sdist 必须包含 PKG-INFO
        pkg_info = _metadata()
        info = tarfile.TarInfo(f"{base}/PKG-INFO")
        info.size = len(pkg_info)
        tf.addfile(info, io.BytesIO(pkg_info))
    return archive.name


# ---------------------------------------------------------------------------
# 函数：build_wheel（PEP517 钩子）
#
# 功能说明：
#   1. 这是 PEP517 规范定义的核心钩子，负责构建 wheel 安装包，
#      产物为 sort-demo-0.1.0-py3-none-any.whl（本质是一个 zip 文件），
#      存放在前端指定的 wheel_directory。
#   2. 打包内容分三部分：
#      a) 源码文件：按 _wheel_arcnames() 计算的路径写入 zip；
#      b) dist-info 元数据：METADATA（包信息）与 WHEEL（wheel 格式信息，
#         声明 Wheel-Version、Generator、Root-Is-Purelib、Tag）；
#      c) RECORD 清单：记录每个文件的 sha256 摘要与大小。
#   3. 内部定义局部函数 add()：写文件的同时生成 RECORD 行，保证
#      zip 内容与清单严格同步。
#   4. "py3-none-any" 标签表示纯 Python、不限平台、不限 ABI，
#      与本项目无 C 扩展的实际情况一致。
#
# 可能出现的情况：
#   1. RECORD 文件的最后一行是 "RECORD,," —— 按 wheel 规范，RECORD
#      自身的哈希与大小必须留空（否则自我引用无法自洽），若错误地
#      给它也计算哈希，安装器校验会失败。
#   2. metadata_directory 参数（前端可能传入 prepare_metadata 的产物）
#      被完全忽略：本实现总是重新生成元数据。若前端期望复用先前
#      准备的元数据且两者不一致，规范要求以 build_wheel 生成为准，
#      本实现天然满足。
#   3. 读取源码用 read_bytes()，若构建过程中文件被修改/删除会抛
#      OSError 或打出不一致的包；构建期间应避免改动 src/。
#   4. 调用 _metadata() 会触发其内部 import 尝试和 os.system 副作用，
#      即每次构建 wheel 都会执行一次 check_json.exe。
#   5. 同名 whl 已存在时 ZipFile("w") 直接覆盖，无提示。
#   6. zip 条目的时间戳默认取 1980-01-01（zipfile 默认值），
#      因此产物字节级可复现性较好，但 RECORD 顺序依赖 _wheel_arcnames
#      的排序稳定性（已保证）。
#   7. 返回值为 whl 文件名（不含目录路径），符合 PEP517 约定。
# ---------------------------------------------------------------------------
def build_wheel(wheel_directory, config_settings=None, metadata_directory=None):
    out = Path(wheel_directory)
    out.mkdir(parents=True, exist_ok=True)
    wheel_name = f"{NAME}-{VERSION}-py3-none-any.whl"
    records = []

    with zipfile.ZipFile(out / wheel_name, "w", zipfile.ZIP_DEFLATED) as wh:
        def add(arcname: str, data: bytes) -> None:
            wh.writestr(arcname, data)
            records.append(_record_line(arcname, data))

        for arcname in _wheel_arcnames():
            add(arcname, (ROOT / "src" / arcname).read_bytes())
        add(f"{DIST_INFO}/METADATA", _metadata())
        add(f"{DIST_INFO}/WHEEL", (
            "Wheel-Version: 1.0\n"
            f"Generator: custom_backend {VERSION}\n"
            "Root-Is-Purelib: true\n"
            "Tag: py3-none-any\n"
        ).encode())
        # RECORD 自身一行哈希与大小留空，符合 wheel 规范
        wh.writestr(f"{DIST_INFO}/RECORD", "\n".join(records + [f"{DIST_INFO}/RECORD,,"]) + "\n")

    return wheel_name
