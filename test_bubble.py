"""bubble_sort 的单元测试（仅使用 Python 标准库 unittest）。

覆盖基础版 bubble_sort 与优化版 bubble_sort_optimized：
普通乱序、已排序、逆序、重复元素、负数、空数组、单元素、双元素，
以及两版结果一致性与原地修改语义。

注意：共用断言放在不继承 TestCase 的 Mixin 中，避免被 unittest 收集。
"""
import unittest

from bubble_sort import bubble_sort, bubble_sort_optimized


class SortCases:
    """排序用例 Mixin（非 TestCase，不会被 loader 收集）。"""

    def sort_fn(self, arr):
        raise NotImplementedError

    def assert_sorted(self, arr, expected):
        src = list(arr)
        result = self.sort_fn(src)
        # 返回值即传入的列表（原地修改），且内容等于期望升序结果
        self.assertIs(result, src)
        self.assertEqual(result, expected)
        # 原数组已被原地改写
        self.assertEqual(src, expected)

    def test_unsorted(self):
        self.assert_sorted([64, 34, 25, 12, 22, 11, 90],
                          [11, 12, 22, 25, 34, 64, 90])

    def test_already_sorted(self):
        self.assert_sorted([1, 2, 3, 4, 5], [1, 2, 3, 4, 5])

    def test_reverse_sorted(self):
        self.assert_sorted([9, 8, 7, 6, 5, 4], [4, 5, 6, 7, 8, 9])

    def test_duplicates(self):
        self.assert_sorted([5, 2, 5, 1, 2, 5, 1], [1, 1, 2, 2, 5, 5, 5])

    def test_negative_numbers(self):
        self.assert_sorted([-3, 0, -1, 7, -2, 4], [-3, -2, -1, 0, 4, 7])

    def test_empty(self):
        self.assert_sorted([], [])

    def test_single(self):
        self.assert_sorted([42], [42])

    def test_two_elements(self):
        self.assert_sorted([2, 1], [1, 2])
        self.assert_sorted([1, 2], [1, 2])


class TestBasicBubbleSort(SortCases, unittest.TestCase):
    def sort_fn(self, arr):
        return bubble_sort(arr)


class TestOptimizedBubbleSort(SortCases, unittest.TestCase):
    def sort_fn(self, arr):
        return bubble_sort_optimized(arr)


class TestConsistency(unittest.TestCase):
    def test_versions_agree_on_many_cases(self):
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
            with self.subTest(case=case):
                expected = sorted(case)
                self.assertEqual(bubble_sort(list(case)), expected)
                self.assertEqual(bubble_sort_optimized(list(case)), expected)


if __name__ == "__main__":
    unittest.main(verbosity=2)
