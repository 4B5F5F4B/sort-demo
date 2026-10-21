"""各排序算法统一测试入口。

所有算法遵循 :class:`core.base.SortAlgorithm` 统一契约：
- 返回排序后的新列表；
- 不修改原始输入；
- 结果与内置 sorted() 一致。

覆盖：空列表、单元素、已排序、逆序、重复元素、负数、随机列表。

新增算法实现后，将实例加入 ALGORITHMS 列表即可自动参与全部测试。
"""

import random

import pytest

from bubble_sort import bubble_sort
from core.base import SortAlgorithm


class BubbleSortAdapter:
    """把原地修改的 bubble_sort 包装为「返回新列表」的契约实现。"""

    name = "冒泡排序 Bubble Sort"

    def sort(self, data):
        return bubble_sort(list(data))


ALGORITHMS: list[SortAlgorithm] = [
    BubbleSortAdapter(),
]

ALGORITHM_IDS = [f"{algorithm.name}（{type(algorithm).__name__}）" for algorithm in ALGORITHMS]

CASES = [
    ([], []),
    ([42], [42]),
    ([1, 2, 3, 4, 5], [1, 2, 3, 4, 5]),
    ([9, 8, 7, 6, 5, 4], [4, 5, 6, 7, 8, 9]),
    ([5, 2, 5, 1, 2, 5, 1], [1, 1, 2, 2, 5, 5, 5]),
    ([-3, 0, -1, 7, -2, 4], [-3, -2, -1, 0, 4, 7]),
    ([64, 34, 25, 12, 22, 11, 90], [11, 12, 22, 25, 34, 64, 90]),
]


@pytest.mark.parametrize("algorithm", ALGORITHMS, ids=ALGORITHM_IDS)
@pytest.mark.parametrize("data,expected", CASES)
def test_algorithm_cases(algorithm, data, expected):
    assert algorithm.sort(list(data)) == expected


@pytest.mark.parametrize("algorithm", ALGORITHMS, ids=ALGORITHM_IDS)
def test_random_matches_sorted(algorithm):
    """随机列表结果与内置 sorted() 一致。"""
    random.seed(42)
    for _ in range(20):
        data = [random.randint(-50, 50) for _ in range(random.randint(0, 60))]
        assert algorithm.sort(data) == sorted(data)


@pytest.mark.parametrize("algorithm", ALGORITHMS, ids=ALGORITHM_IDS)
def test_does_not_mutate_input(algorithm):
    """sort() 不修改原始输入。"""
    data = [5, 3, 8, 1, 9, 2, 7]
    original = list(data)
    algorithm.sort(data)
    assert data == original


@pytest.mark.parametrize("algorithm", ALGORITHMS, ids=ALGORITHM_IDS)
def test_name_attribute(algorithm):
    """每个算法都提供非空的 name 属性。"""
    assert isinstance(algorithm.name, str) and algorithm.name
