from __future__ import annotations

import argparse
import json
import random
import subprocess
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_experiment import JAR, ROOT, prevent_idle_sleep

FORKS = 4
CUTOFF = 10
DATASETS = ["random_100000_s1", "random_1000000_s1"]
SETTINGS = {
    "hien_tai": ("-Xms1g -Xmx1g -XX:+AlwaysPreTouch -XX:+UseParallelGC", "reuse"),
    "tuan": ("-Xms2g -Xmx2g -XX:+UseParallelGC", "reuse"),
    "tuan_clone": ("-Xms2g -Xmx2g -XX:+UseParallelGC", "clone"),
}
SPIN_ARGS = "-Xms2g -Xmx2g -XX:+UseParallelGC"

def plan() -> list[tuple[str, str, int]]:
    jobs = [(setting, dataset, fork) for setting in SETTINGS for dataset in DATASETS for fork in range(FORKS)]
    jobs += [("spin", "", fork) for fork in range(FORKS)]
    random.Random(20261116).shuffle(jobs)
    return jobs

def command(setting: str, dataset: str, output: Path) -> list[str]:
    common = ["-bm", "ss", "-f", "1", "-foe", "true", "-rf", "json", "-rff", str(output)]
    if setting == "spin":
        return ["java", "-jar", str(JAR), "^cutoff.bench.SpinBench.spin$", "-wi", "10", "-i", "60",
                *common, "-jvmArgsAppend", SPIN_ARGS]
    jvm_args, copy_mode = SETTINGS[setting]
    return ["java", "-jar", str(JAR), "^cutoff.bench.SortBench.sort$",
            "-p", f"dataset={dataset}", "-p", f"cutoff={CUTOFF}", "-p", f"copyMode={copy_mode}",
            "-wi", "20", "-i", "30", *common, "-jvmArgsAppend", jvm_args]

def series(path: Path) -> np.ndarray:
    return np.array(json.loads(path.read_text(encoding="utf-8"))[0]["primaryMetric"]["rawData"][0]) / 1000

def autocorrelation(values: np.ndarray, lag: int) -> float:
    centered = values - values.mean()
    return float(np.dot(centered[:-lag], centered[lag:]) / np.dot(centered, centered))

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", default="noise_check")
    args = parser.parse_args()
    out = ROOT / "results" / args.name
    out.mkdir(parents=True, exist_ok=True)
    prevent_idle_sleep()

    jobs = plan()
    for index, (setting, dataset, fork) in enumerate(jobs, start=1):
        path = out / f"{setting}__{dataset or 'spin'}__r{fork}.json"
        if path.exists():
            continue
        with (out / "console.log").open("ab") as log:
            code = subprocess.run(command(setting, dataset, path), cwd=ROOT, stdout=log,
                                  stderr=subprocess.STDOUT).returncode
        if code != 0:
            sys.exit(f"JMH failed: {path.name} (exit {code}), see {out / 'console.log'}")
        print(f"[{index}/{len(jobs)}] {path.stem}", flush=True)

    print(f"\n{'thiết lập':<12}{'dataset':<20}{'ms':>9}{'CV trong JVM':>14}{'CV giữa JVM':>13}"
          f"{'tự tương quan max (độ trễ)':>30}")
    for setting in [*SETTINGS, "spin"]:
        for dataset in (DATASETS if setting != "spin" else [""]):
            runs = [series(path) for path in sorted(out.glob(f"{setting}__{dataset or 'spin'}__r*.json"))]
            if not runs:
                continue
            within = np.median([100 * run.std(ddof=1) / run.mean() for run in runs])
            means = np.array([run.mean() for run in runs])
            between = 100 * means.std(ddof=1) / means.mean() if len(means) > 1 else float("nan")
            lags = range(2, min(16, min(len(run) for run in runs) // 2))
            correlations = {lag: np.mean([autocorrelation(run, lag) for run in runs]) for lag in lags}
            best_lag = max(correlations, key=correlations.get)
            print(f"{setting:<12}{dataset or 'spin':<20}{means.mean():>9.2f}{within:>13.2f}%{between:>12.2f}%"
                  f"{correlations[best_lag]:>24.2f} ({best_lag})")
    spin_runs = sorted(out.glob("spin__spin__r*.json"))
    if spin_runs:
        print("\nspin, fork đầu tiên (ms):", " ".join(f"{value:.1f}" for value in series(spin_runs[0])))
    return 0

if __name__ == "__main__":
    sys.exit(main())
