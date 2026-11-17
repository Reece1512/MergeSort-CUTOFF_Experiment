package cutoff.data;

import java.io.BufferedInputStream;
import java.io.DataInputStream;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;

public final class DatasetIO {

    private static final int BUFFER_SIZE = 1 << 20;

    private DatasetIO() {
    }

    public static Path pathOf(String datasetId) {
        return Path.of("data", datasetId + ".bin");
    }

    public static int[] read(Path file) throws IOException {
        try (DataInputStream in = new DataInputStream(
                new BufferedInputStream(Files.newInputStream(file), BUFFER_SIZE))) {
            int n = in.readInt();
            if (n < 0) {
                throw new IOException("Negative length in " + file + ": " + n);
            }
            int[] values = new int[n];
            for (int i = 0; i < n; i++) {
                values[i] = in.readInt();
            }
            if (in.read() != -1) {
                throw new IOException("Trailing data in " + file);
            }
            return values;
        }
    }

    public static Integer[] readBoxed(String datasetId) throws IOException {
        int[] values = read(pathOf(datasetId));
        Integer[] boxed = new Integer[values.length];
        for (int i = 0; i < values.length; i++) {
            boxed[i] = values[i];
        }
        return boxed;
    }
}
