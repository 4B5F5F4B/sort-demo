def bubble_sort(arr):
    """冒泡排序（基础版）：每次把最大的元素“冒泡”到末尾。"""
    n = len(arr)
    for i in range(n - 1):
        for j in range(n - 1 - i):
            if arr[j] > arr[j + 1]:
                arr[j], arr[j + 1] = arr[j + 1], arr[j]
    return arr


def bubble_sort_optimized(arr):
    """
    冒泡排序（优化版）：
    1. 若某一轮没有发生交换，说明已经有序，提前结束。
    2. 记录最后一次交换的位置，后续区间已有序，无需再比较。
    """
    n = len(arr)
    last_swap = n - 1
    for i in range(n - 1):
        swapped = False
        for j in range(last_swap):
            if arr[j] > arr[j + 1]:
                arr[j], arr[j + 1] = arr[j + 1], arr[j]
                swapped = True
                last_swap = j  # 记录最后一次交换的位置
        if not swapped:
            break
    return arr


if __name__ == "__main__":
    data = [64, 34, 25, 12, 22, 11, 90]
    print("原始数组:", data)
    print("基础版排序:", bubble_sort(data.copy()))
    print("优化版排序:", bubble_sort_optimized(data.copy()))
