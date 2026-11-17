package cutoff.bench;

import cutoff.data.DatasetIO;
import cutoff.sort.MergeSort;
import java.io.IOException;
import java.util.Arrays;
import java.util.concurrent.TimeUnit;
import org.openjdk.jmh.annotations.Benchmark;
import org.openjdk.jmh.annotations.BenchmarkMode;
import org.openjdk.jmh.annotations.Fork;
import org.openjdk.jmh.annotations.Level;
import org.openjdk.jmh.annotations.Measurement;
import org.openjdk.jmh.annotations.Mode;
import org.openjdk.jmh.annotations.OutputTimeUnit;
import org.openjdk.jmh.annotations.Param;
import org.openjdk.jmh.annotations.Scope;
import org.openjdk.jmh.annotations.Setup;
import org.openjdk.jmh.annotations.State;
import org.openjdk.jmh.annotations.TearDown;
import org.openjdk.jmh.annotations.Warmup;

@State(Scope.Thread)
@BenchmarkMode(Mode.SingleShotTime)
@OutputTimeUnit(TimeUnit.MICROSECONDS)
@Warmup(iterations = 20)
@Measurement(iterations = 10)
@Fork(value = 3, jvmArgsAppend = {"-Xms2g", "-Xmx2g", "-XX:+UseParallelGC"})
public class SortBench {

    @Param({"random_10000_s1"})
    public String dataset;

    @Param({"0"})
    public int cutoff;

    private Integer[] original;
    private int[] sortedValues;
    private Integer[] work;

    @Setup(Level.Trial)
    public void load() throws IOException {
        int[] values = DatasetIO.read(DatasetIO.pathOf(dataset));
        original = new Integer[values.length];
        for (int i = 0; i < values.length; i++) {
            original[i] = values[i];
        }
        sortedValues = values.clone();
        Arrays.sort(sortedValues);
        work = new Integer[original.length];
    }

    @Param({"reuse"})
    public String copyMode;

    @Setup(Level.Iteration)
    public void freshCopy() {
        if (copyMode.equals("clone")) {
            work = original.clone();
        } else {
            System.arraycopy(original, 0, work, 0, original.length);
        }
    }

    @Benchmark
    public Integer[] sort() {
        MergeSort.sort(work, cutoff);
        return work;
    }

    @TearDown(Level.Iteration)
    public void verify() {
        for (int i = 0; i < work.length; i++) {
            if (work[i] != sortedValues[i]) {
                throw new IllegalStateException(
                        "Incorrect sort result at index " + i + ": dataset=" + dataset + ", cutoff=" + cutoff);
            }
        }
    }
}
