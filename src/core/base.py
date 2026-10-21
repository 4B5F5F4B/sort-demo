"""排序算法统一接口。

所有排序算法必须实现 :class:`SortAlgorithm` 协议，以保证可运行、可对比：
- 提供 ``name`` 属性（算法名称，用于展示与对比）；
- 提供 ``sort()`` 方法：**纯函数风格**，返回排序后的新列表，不修改原始输入。
"""

from collections.abc import Sequence
from typing import Any, Protocol, TypeVar


class SupportsRichComparison(Protocol):
    """支持完整大小比较运算的类型（int/str/float 等内置类型天然满足）。"""

    def __lt__(self, other: Any, /) -> bool: ...

    def __gt__(self, other: Any, /) -> bool: ...

    def __le__(self, other: Any, /) -> bool: ...

    def __ge__(self, other: Any, /) -> bool: ...


T = TypeVar("T", bound=SupportsRichComparison)


class SortAlgorithm(Protocol[T]):
    """所有排序算法必须实现的统一接口。

    实现要求：
    - 提供 ``name`` 属性（算法名称，用于展示与对比）；
    - 提供 ``sort()`` 方法：**纯函数风格**，返回排序后的新列表，
      不修改原始输入。
    """

    name: str

    def sort(self, data: Sequence[T]) -> list[T]:
        """返回排序后的新列表，不修改原始输入。

        Args:
            data: 待排序的序列（元素需支持大小比较）。

        Returns:
            排序后的新列表（升序）。
        """
        ...
