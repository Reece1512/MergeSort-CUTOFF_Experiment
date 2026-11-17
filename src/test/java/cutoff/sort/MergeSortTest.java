package cutoff.sort;

import static org.junit.jupiter.api.Assertions.assertArrayEquals;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertThrows;

import java.util.Arrays;
import java.util.Random;
import org.junit.jupiter.api.Test;

class MergeSortTest {

    private static final int[] CUTOFFS = {0, 1, 2, 3, 7, 10, 16, 64};

    @Test
    void negativeCutoffIsRejected() {
        assertThrows(IllegalArgumentException.class, () -> MergeSort.sort(new Integer[] {2, 1}, -1));
        assertThrows(IllegalArgumentException.class, () -> MergeSort.sort(new Integer[0], -1));
    }

    @Test
    void emptyAndSingleElementArrays() {
        for (int cutoff : CUTOFFS) {
            assertSorted(new Integer[0], cutoff);
            assertSorted(new Integer[] {42}, cutoff);
        }
    }

    @Test
    void cutoffLargerThanArray() {
        Integer[] input = {5, 1, 4, 2, 3};
        assertSorted(input, 1_000);
    }

    @Test
    void sizesAroundTheCutoffBoundary() {
        for (int cutoff : CUTOFFS) {
            int[] sizes = {
                cutoff - 1, cutoff, cutoff + 1,
                2 * cutoff - 1, 2 * cutoff, 2 * cutoff + 1, 2 * cutoff + 2,
                4 * cutoff + 1
            };
            for (int n : sizes) {
                if (n >= 0) {
                    assertSorted(randomArray(n, 1_000L * cutoff + n, 50), cutoff);
                }
            }
        }
    }

    @Test
    void structuredInputs() {
        int n = 1_000;
        Integer[] ascending = new Integer[n];
        Integer[] descending = new Integer[n];
        Integer[] allEqual = new Integer[n];
        Integer[] organPipe = new Integer[n];
        for (int i = 0; i < n; i++) {
            ascending[i] = i;
            descending[i] = n - i;
            allEqual[i] = 7;
            organPipe[i] = Math.min(i, n - 1 - i);
        }
        Integer[] extremes = {Integer.MAX_VALUE, 0, Integer.MIN_VALUE, -1, 1, Integer.MIN_VALUE};
        for (int cutoff : CUTOFFS) {
            assertSorted(ascending, cutoff);
            assertSorted(descending, cutoff);
            assertSorted(allEqual, cutoff);
            assertSorted(organPipe, cutoff);
            assertSorted(extremes, cutoff);
        }
    }

    @Test
    void randomArraysMatchReferenceSort() {
        Random random = new Random(20261108L);
        for (int round = 0; round < 1_000; round++) {
            int n = random.nextInt(501);
            int keyRange = round % 2 == 0 ? 10 : 1_000_000;
            int cutoff = CUTOFFS[round % CUTOFFS.length];
            assertSorted(randomArray(n, random.nextLong(), keyRange), cutoff);
        }
    }

    @Test
    void sortIsStable() {
        int[] sizes = {2, 3, 7, 8, 9, 10, 11, 16, 17, 100, 1_000, 20_000};
        for (int cutoff : CUTOFFS) {
            for (int n : sizes) {
                Random random = new Random(31L * cutoff + n);
                Item[] items = new Item[n];
                for (int i = 0; i < n; i++) {
                    items[i] = new Item(random.nextInt(4), i);
                }
                Item[] expected = items.clone();
                Arrays.sort(expected);

                MergeSort.sort(items, cutoff);

                for (int i = 0; i < n; i++) {
                    assertSame(expected[i], items[i],
                            "Not stable at i=" + i + ", n=" + n + ", cutoff=" + cutoff);
                }
            }
        }
    }

    @Test
    void cutoffBoundaryIsInclusiveAndNoEarlyExit() {
        int[][] cutoffAndExpected = {{0, 32}, {1, 32}, {7, 28}, {8, 22}, {15, 22}, {16, 15}, {100, 15}};
        for (int[] testCase : cutoffAndExpected) {
            long[] counter = new long[1];
            Counted[] input = new Counted[16];
            for (int i = 0; i < input.length; i++) {
                input[i] = new Counted(i, counter);
            }

            MergeSort.sort(input, testCase[0]);

            assertEquals(testCase[1], counter[0],
                    "Wrong compare count for cutoff=" + testCase[0]
                            + ". Check the cutoff condition (length <= cutoff)"
                            + " and do not add the 'stop if already sorted' improvement.");
        }
    }

    private static Integer[] randomArray(int n, long seed, int keyRange) {
        return new Random(seed).ints(n, -keyRange, keyRange).boxed().toArray(Integer[]::new);
    }

    private static void assertSorted(Integer[] input, int cutoff) {
        Integer[] expected = input.clone();
        Arrays.sort(expected);
        Integer[] actual = input.clone();

        MergeSort.sort(actual, cutoff);

        assertArrayEquals(expected, actual, "Wrong result for n=" + input.length + ", cutoff=" + cutoff);
    }

    private record Item(int key, int originalIndex) implements Comparable<Item> {
        @Override
        public int compareTo(Item other) {
            return Integer.compare(key, other.key);
        }
    }

    private record Counted(int key, long[] counter) implements Comparable<Counted> {
        @Override
        public int compareTo(Counted other) {
            counter[0]++;
            return Integer.compare(key, other.key);
        }
    }
}
