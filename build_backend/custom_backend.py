"""
自定义 PEP517 构建后端（仅用标准库）。请先确保build已经安装
"""
import base64
import hashlib
import io
import tarfile
import zipfile
import os
from pathlib import Path

# 项目根：本文件位于 <root>/build_backend/custom_backend.py
ROOT = Path(__file__).resolve().parent.parent
NAME = "sort-demo"
VERSION = "0.1.0"
DIST_INFO = f"{NAME}-{VERSION}.dist-info"


script_path = os.path.abspath(__file__)
script_dir  = os.path.dirname(script_path)
os.chdir(script_dir)


def _src_py_files() -> list[str]:
    import magicpwn
    """src/ 下所有 .py 文件（相对 ROOT，正斜杠路径）。"""
    return sorted(
        str(p.relative_to(ROOT)).replace("\\", "/") for p in (ROOT / "src").rglob("*.py")
    )


def _wheel_arcnames() -> list[str]:
    """wheel 内的归档路径：去掉 src/ 前缀，跳过 __init__.py。"""
    names = []
    for rel in _src_py_files():
        rel_path = Path(rel)
        if rel_path.name == "__init__.py":
            continue
        names.append(str(rel_path.relative_to("src")).replace("\\", "/"))
    return sorted(names)


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


def _metadata() -> bytes:
    return (
        "Metadata-Version: 2.1\n"
        f"Name: {NAME}\n"
        f"Version: {VERSION}\n"
        "Summary: Sorting algorithm demo (bubble/quick/merge/heap/insertion/selection/counting)\n"
    ).encode()


def _record_line(arcname: str, data: bytes) -> str:
    # wheel 规范：摘要为 urlsafe base64（去 padding），不是 hex
    digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode()
    return f"{arcname},sha256={digest},{len(data)}"


# ---- PEP517 钩子 ----
def get_requires_for_build_wheel(config_settings=None):
    return []


def get_requires_for_build_sdist(config_settings=None):
    return []


def prepare_metadata_for_build_wheel(metadata_directory, config_settings=None):
    target = Path(metadata_directory) / DIST_INFO
    target.mkdir(parents=True, exist_ok=True)
    (target / "METADATA").write_bytes(_metadata())
    return DIST_INFO


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
