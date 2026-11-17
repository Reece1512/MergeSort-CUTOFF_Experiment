package cutoff.sort;

@SuppressWarnings({"rawtypes", "unchecked"})

public final class MergeSort {
    private static void merge(Comparable[] a, Comparable[] tmp, int low, int mid, int high) {
        for (int k = low; k <= high; k++) {
            tmp[k] = a[k];
        }
        int i = low;
        int j = mid + 1;
        for (int k = low; k <= high; k++) {
            if (i > mid) {
                a[k] = tmp[j++];
            } else if (j > high) {
                a[k] = tmp[i++];
            } else if (less(tmp[j], tmp[i])) {
                a[k] = tmp[j++];
            } else {
                a[k] = tmp[i++];
            }
        }
    }

    private static void mergeSort(Comparable[] a, Comparable[] tmp, int low, int high, int cutoff) {
        if (low >= high) {
            return;
        }
        if (high - low + 1 <= cutoff) {
            insertionSort(a, low, high);
            return;
        }
        int mid = low + (high - low) / 2;
        mergeSort(a, tmp, low, mid, cutoff);
        mergeSort(a, tmp, mid + 1, high, cutoff);
        merge(a, tmp, low, mid, high);
    }

    public static void sort(Comparable[] a, int cutoff) {
        if (cutoff < 0) {
            throw new IllegalArgumentException("Cutoff must be not negative");
        }
        Comparable[] tmp = new Comparable[a.length];
        mergeSort(a, tmp, 0, a.length - 1, cutoff);
    }

    private static void insertionSort(Comparable[] a, int low, int high) {
        for (int i = low + 1; i <= high; i++) {
            for (int j = i; j > low; j--) {
                if (less(a[j], a[j - 1])) {
                    exch(a, j, j - 1);
                } else {
                    break;
                }
            }
        }
    }

    private static boolean less(Comparable x, Comparable y) {
        if (x.compareTo(y) < 0) {
            return true;
        }
        return false;
    }

    private static void exch(Comparable[] a, int i, int j) {
        Comparable tmp = a[i];
        a[i] = a[j];
        a[j] = tmp;
    }
}
