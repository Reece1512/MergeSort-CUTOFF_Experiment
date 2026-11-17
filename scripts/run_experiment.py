from __future__ import annotations

import argparse
import csv
import ctypes
import fnmatch
import hashlib
import json
import math
import os
import random
import subprocess
import sys
import time
import tomllib
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

import sysinfo

ROOT = Path(__file__).resolve().parent.parent
JAR = ROOT / "target" / "benchmarks.jar"
BENCHMARKS = {
    "sort": "cutoff.bench.SortBench.sort",
    "copy": "cutoff.bench.CopyOnlyBench.copy",
}
FORK_STARTUP_SECONDS = 1.5
SORT_SECONDS_PER_NLGN = 1.5e-8

@dataclass(frozen=True)
class Run:
    dataset: str
    cutoff: int | None
    forks: int
    warmup: int
    measurements: int
    n: int
    variant: str = ""

    @property
    def kind(self) -> str:
        return "copy" if self.cutoff is None else "sort"

    @property
    def key(self) -> str:
        suffix = "copy" if self.cutoff is None else f"c{self.cutoff}"
        prefix = f"{self.variant}__" if self.variant else ""
        return f"{prefix}{self.dataset}__{suffix}"

@lru_cache(maxsize=None)
def tree_signature(length: int, cutoff: int) -> tuple[int, int, int, int]:
    if length <= 1:
        return 1, 0, 0, 0
    if length <= cutoff:
        return 1, 0, 0, 1
    left = tree_signature((length + 1) // 2, cutoff)
    right = tree_signature(length // 2, cutoff)
    return 1 + left[0] + right[0], 1 + left[1] + right[1], length + left[2] + right[2], left[3] + right[3]

def representatives(n: int, cutoffs: list[int]) -> list[int]:
    kept, seen = [], set()
    for cutoff in sorted(cutoffs):
        signature = tree_signature(n, cutoff)
        if signature not in seen:
            seen.add(signature)
            kept.append(cutoff)
    return kept

def dataset_sizes() -> dict[str, int]:
    with (ROOT / "data" / "manifest.csv").open(encoding="utf-8") as handle:
        return {row["id"]: int(row["n"]) for row in csv.DictReader(handle)}

def iteration_settings(jmh: dict, n: int) -> tuple[int, int, int]:
    chosen = next((tier for tier in jmh.get("tiers", []) if n <= tier["max_n"]), {})
    return (
        chosen.get("warmup_iterations", jmh["warmup_iterations"]),
        chosen.get("measurement_iterations", jmh["measurement_iterations"]),
        chosen.get("forks", jmh["forks"]),
    )

def match_datasets(patterns: list[str], sizes: dict[str, int]) -> list[str]:
    matched: list[str] = []
    for pattern in patterns:
        hits = sorted(name for name in sizes if fnmatch.fnmatchcase(name, pattern))
        if not hits:
            sys.exit(f"No dataset in data/manifest.csv matches {pattern!r} (run scripts/gen_data.py)")
        matched += [name for name in hits if name not in matched]
    return matched

def expand_grid(config: dict) -> list[Run]:
    variants = list(config.get("variants", {})) or [""]
    sizes = dataset_sizes()
    runs: dict[str, Run] = {}
    for entry in config["grid"]:
        for dataset in match_datasets(entry["datasets"], sizes):
            n = sizes[dataset]
            warmup, measurements, forks = iteration_settings(config["jmh"], n)
            forks = entry.get("forks", forks)
            cutoffs = entry.get("cutoffs", [None])
            if entry.get("dedupe") and None not in cutoffs:
                kept = set(representatives(n, cutoffs)) | set(entry.get("controls", []))
                cutoffs = sorted(kept)
            for cutoff in cutoffs:
                for variant in variants:
                    run = Run(dataset, cutoff, forks, warmup, measurements, n, variant)
                    runs[run.key] = run
    ordered = [runs[key] for key in sorted(runs)]
    random.Random(config["shuffle_seed"]).shuffle(ordered)
    return ordered

def jmh_command(run: Run, jmh: dict, output: Path, jvm_args: str | None) -> list[str]:
    command = [
        "java", "-jar", str(JAR),
        f"^{BENCHMARKS[run.kind]}$",
        "-p", f"dataset={run.dataset}",
        "-bm", jmh.get("mode", "ss"),
        "-wi", str(run.warmup),
        "-i", str(run.measurements),
        "-f", str(run.forks),
        "-foe", "true",
        "-rf", "json",
        "-rff", str(output),
    ]
    if jmh.get("mode", "ss") != "ss":
        command += ["-w", f"{jmh['warmup_time_ms']}ms", "-r", f"{jmh['measurement_time_ms']}ms"]
    if run.cutoff is not None:
        command += ["-p", f"cutoff={run.cutoff}"]
    if jvm_args is not None:
        command += ["-jvmArgsAppend", jvm_args]
    return command

def check_inputs(runs: list[Run]) -> None:
    missing = sorted({run.dataset for run in runs if not (ROOT / "data" / f"{run.dataset}.bin").exists()})
    if missing:
        sys.exit(f"Missing datasets (run scripts/gen_data.py): {', '.join(missing)}")
    if not JAR.exists():
        sys.exit(f"Missing {JAR} (run: mvn package)")
    sources = [ROOT / "pom.xml", *(ROOT / "src").rglob("*.java")]
    newest = max(sources, key=lambda path: path.stat().st_mtime)
    if newest.stat().st_mtime > JAR.stat().st_mtime:
        sys.exit(f"{JAR.name} is older than {newest.name}, so it would measure old code (run: mvn package)")

def check_fingerprint(path: Path, config_text: str) -> None:
    current = {
        "config_sha256": hashlib.sha256(config_text.encode("utf-8")).hexdigest(),
        "sources_sha256": sysinfo.collect()["sources_sha256"],
    }
    if path.exists():
        if json.loads(path.read_text(encoding="utf-8")) != current:
            sys.exit(
                f"The config or the measured code changed since {path.parent} was started. "
                "Move that folder away to start a new run."
            )
        return
    path.write_text(json.dumps(current, indent=2) + "\n", encoding="utf-8")

def write_schedule(path: Path, runs: list[Run]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["order", "variant", "benchmark", "dataset", "cutoff", "forks", "warmup", "measurements"])
        for order, run in enumerate(runs, start=1):
            cutoff = "" if run.cutoff is None else run.cutoff
            writer.writerow([order, run.variant, run.kind, run.dataset, cutoff, run.forks, run.warmup, run.measurements])

def format_duration(seconds: float) -> str:
    minutes, rest = divmod(int(round(seconds)), 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h{minutes:02d}m{rest:02d}s" if hours else f"{minutes}m{rest:02d}s"

def estimate_seconds(run: Run, jmh: dict) -> float:
    iterations = run.warmup + run.measurements
    if jmh.get("mode", "ss") == "ss":
        per_iteration = SORT_SECONDS_PER_NLGN * run.n * math.log2(max(run.n, 2))
        return run.forks * (iterations * per_iteration + FORK_STARTUP_SECONDS)
    per_iteration = (run.warmup * jmh["warmup_time_ms"] + run.measurements * jmh["measurement_time_ms"]) / 1000
    return run.forks * (per_iteration + FORK_STARTUP_SECONDS)

def jvm_args_for(run: Run, config: dict) -> str | None:
    variants = config.get("variants", {})
    return variants[run.variant] if run.variant else config.get("jvm_args")

def dry_run(runs: list[Run], done: set[str], config: dict, run_dir: Path) -> None:
    jmh = config["jmh"]
    pending = [run for run in runs if run.key not in done]
    print(f"{len(runs)} configurations, {len(pending)} pending, {sum(run.forks for run in pending)} JVM forks")
    by_size: dict[int, list[Run]] = {}
    for run in pending:
        by_size.setdefault(run.n, []).append(run)
    for n in sorted(by_size):
        group = by_size[n]
        seconds = sum(estimate_seconds(run, jmh) for run in group)
        print(f"  N = {n:>9,}: {len(group):>4} configurations, about {format_duration(seconds)}")
    print(f"Estimate: about {format_duration(sum(estimate_seconds(run, jmh) for run in pending))}")
    for run in pending[:3]:
        command = jmh_command(run, jmh, run_dir / "runs" / f"{run.key}.json", jvm_args_for(run, config))
        print(subprocess.list2cmdline(command))

def execute(run: Run, jmh: dict, runs_dir: Path, log_path: Path, jvm_args: str | None) -> None:
    final = runs_dir / f"{run.key}.json"
    partial = runs_dir / f"{run.key}.partial"
    with log_path.open("ab") as log:
        log.write(f"\n===== {run.key} =====\n".encode("utf-8"))
        log.flush()
        code = subprocess.run(
            jmh_command(run, jmh, partial, jvm_args), cwd=ROOT, stdout=log, stderr=subprocess.STDOUT
        ).returncode
    if code != 0:
        sys.exit(f"JMH failed for {run.key} with exit code {code}. See {log_path}")
    if not json.loads(partial.read_text(encoding="utf-8")):
        sys.exit(f"JMH produced no results for {run.key}. See {log_path}")
    os.replace(partial, final)

def prevent_idle_sleep() -> None:
    if sys.platform == "win32":
        es_continuous, es_system_required = 0x80000000, 0x00000001
        ctypes.windll.kernel32.SetThreadExecutionState(es_continuous | es_system_required)

def main() -> int:
    parser = argparse.ArgumentParser(description="Run one JMH measurement campaign from a TOML config.")
    parser.add_argument("config", type=Path)
    parser.add_argument("--dry-run", action="store_true", help="print the plan without measuring")
    args = parser.parse_args()

    config_text = args.config.read_text(encoding="utf-8")
    config = tomllib.loads(config_text)
    runs = expand_grid(config)
    jmh = config["jmh"]
    check_inputs(runs)

    run_dir = ROOT / "results" / config["name"]
    runs_dir = run_dir / "runs"
    done = {path.stem for path in runs_dir.glob("*.json")}
    if args.dry_run:
        dry_run(runs, done, config, run_dir)
        return 0

    prevent_idle_sleep()
    runs_dir.mkdir(parents=True, exist_ok=True)
    check_fingerprint(run_dir / "fingerprint.json", config_text)
    write_schedule(run_dir / "schedule.csv", runs)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    sysinfo_data = sysinfo.collect()
    (run_dir / f"sysinfo-{stamp}.json").write_text(json.dumps(sysinfo_data, indent=2) + "\n", encoding="utf-8")

    power = sysinfo_data.get("power", {})
    if power and not power["ac_online"]:
        print("WARNING: running on battery, so CPU speed may be throttled.")

    timing_path = run_dir / "timing.csv"
    if not timing_path.exists():
        timing_path.write_text("key,started_at_utc,seconds\n", encoding="utf-8")

    pending = [run for run in runs if run.key not in done]
    print(f"{config['name']}: {len(runs)} configurations, {len(pending)} pending")
    elapsed: list[float] = []
    for index, run in enumerate(pending, start=1):
        started_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        started = time.perf_counter()
        execute(run, jmh, runs_dir, run_dir / "console.log", jvm_args_for(run, config))
        elapsed.append(time.perf_counter() - started)
        with timing_path.open("a", encoding="utf-8") as handle:
            handle.write(f"{run.key},{started_at},{elapsed[-1]:.1f}\n")
        remaining = (len(pending) - index) * sum(elapsed) / len(elapsed)
        print(f"[{index}/{len(pending)}] {run.key}: {elapsed[-1]:.1f}s, ETA {format_duration(remaining)}", flush=True)

    print(f"Done: {run_dir}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
