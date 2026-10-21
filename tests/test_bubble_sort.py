"""冒泡排序（Bubble Sort）的单元测试。

覆盖基础版 bubble_sort 与优化版 bubble_sort_optimized：
普通乱序、已排序、逆序、重复元素、负数、空列表、单元素、双元素，
以及两版结果一致性。
"""

import pytest

from bubble_sort import bubble_sort, bubble_sort_optimized

VERSIONS = [bubble_sort, bubble_sort_optimized]

CASES = [
    ([], []),
    ([42], [42]),
    ([2, 1], [1, 2]),
    ([1, 2], [1, 2]),
    ([64, 34, 25, 12, 22, 11, 90], [11, 12, 22, 25, 34, 64, 90]),
    ([1, 2, 3, 4, 5], [1, 2, 3, 4, 5]),
    ([9, 8, 7, 6, 5, 4], [4, 5, 6, 7, 8, 9]),
    ([5, 2, 5, 1, 2, 5, 1], [1, 1, 2, 2, 5, 5, 5]),
    ([-3, 0, -1, 7, -2, 4], [-3, -2, -1, 0, 4, 7]),
]


@pytest.mark.parametrize("sort_fn", VERSIONS, ids=lambda fn: fn.__name__)
@pytest.mark.parametrize("data,expected", CASES)
def test_bubble_sort_cases(sort_fn, data, expected):
    assert sort_fn(list(data)) == expected


@pytest.mark.parametrize("sort_fn", VERSIONS, ids=lambda fn: fn.__name__)
def test_bubble_sort_in_place(sort_fn):
    """基础版与优化版均为原地修改并返回原列表。"""
    src = [3, 1, 2]
    result = sort_fn(src)
    assert result is src
    assert result == [1, 2, 3]


def test_versions_agree():
    cases = [
        [],
        [1],
        [3, 1],
        [64, 34, 25, 12, 22, 11, 90],
        [5, 2, 5, 1, 2, 5, 1],
        [-3, 0, -1, 7, -2, 4],
        list(range(20, 0, -1)),
    ]
    for case in cases:
        expected = sorted(case)
        assert bubble_sort(list(case)) == expected
        assert bubble_sort_optimized(list(case)) == expected
