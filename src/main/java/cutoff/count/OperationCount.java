package cutoff.count;

import cutoff.data.DatasetIO;
import cutoff.sort.MergeSort;
import java.io.BufferedWriter;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Set;

public final class OperationCount {

    private static final Set<Integer> E1_SIZES = Set.of(10_000, 100_000, 1_000_000);
    private static final Set<Integer> E2_SIZES = Set.of(100_000, 1_000_000);
    private static final int MAX_E1_CUTOFF = 64;
    private static final int[] E2_CUTOFFS = {0, 2, 4, 6, 8, 10, 12, 16, 20, 24, 32, 48, 64};

    private static long compareToCalls;

    private OperationCount() {
    }

    private record Counted(int value) implements Comparable<Counted> {
        @Override
        public int compareTo(Counted other) {
            compareToCalls++;
            return Integer.compare(value, other.value);
        }
    }

    private static final class Counting {
        private final int cutoff;
        private long sortCalls;
        private long mergeCalls;
        private long mergeElements;
        private long mergeCompares;
        private long insertionCalls;
        private long insertionCompares;
        private long exchanges;

        Counting(int[] a, int cutoff) {
            this.cutoff = cutoff;
            sort(a, new int[a.length], 0, a.length - 1);
        }

        private void sort(int[] a, int[] tmp, int low, int high) {
            sortCalls++;
            if (low >= high) {
                return;
            }
            if (high - low + 1 <= cutoff) {
                insertionSort(a, low, high);
                return;
            }
            int mid = low + (high - low) / 2;
            sort(a, tmp, low, mid);
            sort(a, tmp, mid + 1, high);
            merge(a, tmp, low, mid, high);
        }

        private void merge(int[] a, int[] tmp, int low, int mid, int high) {
            mergeCalls++;
            mergeElements += high - low + 1;
            System.arraycopy(a, low, tmp, low, high - low + 1);
            int i = low;
            int j = mid + 1;
            for (int k = low; k <= high; k++) {
                if (i > mid) {
                    a[k] = tmp[j++];
                } else if (j > high) {
                    a[k] = tmp[i++];
                } else {
                    mergeCompares++;
                    a[k] = tmp[j] < tmp[i] ? tmp[j++] : tmp[i++];
                }
            }
        }

        private void insertionSort(int[] a, int low, int high) {
            insertionCalls++;
            for (int i = low + 1; i <= high; i++) {
                for (int j = i; j > low; j--) {
                    insertionCompares++;
                    if (a[j] >= a[j - 1]) {
                        break;
                    }
                    int swap = a[j];
                    a[j] = a[j - 1];
                    a[j - 1] = swap;
                    exchanges++;
                }
            }
        }

        long totalCompares() {
            return mergeCompares + insertionCompares;
        }

        String csvCounts() {
            return String.join(",",
                    Long.toString(sortCalls), Long.toString(mergeCalls), Long.toString(mergeElements),
                    Long.toString(mergeCompares), Long.toString(insertionCalls),
                    Long.toString(insertionCompares), Long.toString(exchanges),
                    Long.toString(totalCompares()));
        }
    }

    private record Dataset(String id, String distribution, int n) {
    }

    private static List<Dataset> readManifest() throws IOException {
        List<String> lines = Files.readAllLines(Path.of("data", "manifest.csv"));
        List<Dataset> datasets = new ArrayList<>();
        for (String line : lines.subList(1, lines.size())) {
            String[] fields = line.split(",");
            datasets.add(new Dataset(fields[0], fields[1], Integer.parseInt(fields[2])));
        }
        return datasets;
    }

    private static int[] cutoffsFor(Dataset dataset) {
        if (dataset.distribution().equals("random")) {
            if (!E1_SIZES.contains(dataset.n())) {
                return new int[0];
            }
            int[] all = new int[MAX_E1_CUTOFF + 1];
            Arrays.setAll(all, c -> c);
            return all;
        }
        return E2_SIZES.contains(dataset.n()) ? E2_CUTOFFS : new int[0];
    }

    private static Counting countAndVerify(Dataset dataset, int[] values, int[] expected, int cutoff) {
        int[] mirrored = values.clone();
        Counting counting = new Counting(mirrored, cutoff);

        Counted[] real = new Counted[values.length];
        Arrays.setAll(real, i -> new Counted(values[i]));
        compareToCalls = 0;
        MergeSort.sort(real, cutoff);

        String where = dataset.id() + " cutoff=" + cutoff;
        if (compareToCalls != counting.totalCompares()) {
            throw new IllegalStateException("Compare count differs for " + where + ": real="
                    + compareToCalls + ", counted=" + counting.totalCompares());
        }
        if (!Arrays.equals(mirrored, expected)) {
            throw new IllegalStateException("Counting sort gave a wrong result for " + where);
        }
        for (int i = 0; i < real.length; i++) {
            if (real[i].value() != expected[i]) {
                throw new IllegalStateException("MergeSort gave a wrong result for " + where);
            }
        }
        return counting;
    }

    public static void main(String[] args) throws IOException {
        if (args.length != 1) {
            throw new IllegalArgumentException("Usage: OperationCount <output.csv>");
        }
        Path output = Path.of(args[0]);
        Files.createDirectories(output.toAbsolutePath().getParent());
        int rows = 0;
        try (BufferedWriter writer = Files.newBufferedWriter(output)) {
            writer.write("dataset,distribution,n,cutoff,sort_calls,merge_calls,merge_elements,"
                    + "merge_compares,insertion_calls,insertion_compares,exchanges,total_compares\n");
            for (Dataset dataset : readManifest()) {
                int[] cutoffs = cutoffsFor(dataset);
                if (cutoffs.length == 0) {
                    continue;
                }
                int[] values = DatasetIO.read(DatasetIO.pathOf(dataset.id()));
                int[] expected = values.clone();
                Arrays.sort(expected);
                for (int cutoff : cutoffs) {
                    Counting counting = countAndVerify(dataset, values, expected, cutoff);
                    writer.write(dataset.id() + "," + dataset.distribution() + "," + dataset.n() + ","
                            + cutoff + "," + counting.csvCounts() + "\n");
                    rows++;
                }
                writer.flush();
                System.out.println(dataset.id() + ": " + cutoffs.length + " cutoffs verified");
            }
        }
        System.out.println("Done: " + rows + " rows, all verified against MergeSort");
    }
}
