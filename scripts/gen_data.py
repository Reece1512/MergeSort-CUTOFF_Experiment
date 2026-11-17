from __future__ import annotations

import argparse
import csv
import hashlib
import struct
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
MANIFEST = DATA_DIR / "manifest.csv"

BASE_SEED = 20261108

VALUE_OFFSET = 1_000_000
DISTINCT_KEYS = 16

MAIN_SIZES = (10_000, 100_000, 1_000_000)
SEEDS = (1, 2, 3, 4, 5)
DOUBLING_SIZES = (15_625, 31_250, 62_500, 125_000, 250_000, 500_000, 2_000_000)

DISTRIBUTION_CODES = {"random": 1, "duplicates": 2, "nearly_sorted": 3}

@dataclass(frozen=True)
class Dataset:
    distribution: str
    n: int
    seed: int | None = None

    @property
    def id(self) -> str:
        suffix = f"_s{self.seed}" if self.seed is not None else ""
        return f"{self.distribution}_{self.n}{suffix}"

def catalog() -> list[Dataset]:
    datasets: list[Dataset] = []
    for n in MAIN_SIZES:
        for distribution in ("random", "duplicates", "nearly_sorted"):
            datasets += [Dataset(distribution, n, seed) for seed in SEEDS]
        datasets.append(Dataset("ascending", n))
        datasets.append(Dataset("descending", n))
    for n in DOUBLING_SIZES:
        datasets.append(Dataset("random", n, 1))
    return datasets

def values_of(dataset: Dataset) -> np.ndarray:
    n = dataset.n
    if dataset.distribution == "ascending":
        return np.arange(n, dtype=np.int32) + VALUE_OFFSET
    if dataset.distribution == "descending":
        return np.arange(n - 1, -1, -1, dtype=np.int32) + VALUE_OFFSET

    code = DISTRIBUTION_CODES[dataset.distribution]
    rng = np.random.Generator(np.random.PCG64(np.random.SeedSequence([BASE_SEED, code, n, dataset.seed])))

    if dataset.distribution == "random":
        return rng.integers(-(2**31), 2**31, size=n, dtype=np.int32)
    if dataset.distribution == "duplicates":
        return rng.integers(0, DISTINCT_KEYS, size=n, dtype=np.int32) + VALUE_OFFSET

    values = np.arange(n, dtype=np.int32) + VALUE_OFFSET
    swaps = n // 100
    first = rng.integers(0, n, size=swaps)
    second = rng.integers(0, n, size=swaps)
    for i, j in zip(first, second):
        values[i], values[j] = values[j], values[i]
    return values

def encode(values: np.ndarray) -> bytes:
    return struct.pack(">i", len(values)) + values.astype(">i4").tobytes()

def generate() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    total_bytes = 0
    with MANIFEST.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["id", "distribution", "n", "seed", "bytes", "sha256"])
        for dataset in catalog():
            payload = encode(values_of(dataset))
            (DATA_DIR / f"{dataset.id}.bin").write_bytes(payload)
            seed = "" if dataset.seed is None else dataset.seed
            digest = hashlib.sha256(payload).hexdigest()
            writer.writerow([dataset.id, dataset.distribution, dataset.n, seed, len(payload), digest])
            total_bytes += len(payload)
            print(f"{dataset.id}: {len(payload):,} bytes")
    print(f"Wrote {len(catalog())} datasets, {total_bytes / 1e6:.1f} MB. Manifest: {MANIFEST}")

def verify() -> int:
    if not MANIFEST.exists():
        print(f"Missing manifest: {MANIFEST}")
        return 1
    with MANIFEST.open(newline="", encoding="utf-8") as handle:
        rows = {row["id"]: row for row in csv.DictReader(handle)}

    problems = []
    datasets = catalog()
    for dataset in datasets:
        row = rows.get(dataset.id)
        path = DATA_DIR / f"{dataset.id}.bin"
        if row is None:
            problems.append(f"{dataset.id}: not in manifest")
        elif not path.exists():
            problems.append(f"{dataset.id}: file is missing")
        elif hashlib.sha256(path.read_bytes()).hexdigest() != row["sha256"]:
            problems.append(f"{dataset.id}: file does not match manifest")
        elif hashlib.sha256(encode(values_of(dataset))).hexdigest() != row["sha256"]:
            problems.append(f"{dataset.id}: regenerating from the seed gives different data")
    extra = set(rows) - {dataset.id for dataset in datasets}
    problems += [f"{dataset_id}: in manifest but not in catalog" for dataset_id in sorted(extra)]

    for problem in problems:
        print(problem)
    print(f"Checked {len(datasets)} datasets, {len(problems)} problem(s).")
    return 1 if problems else 0

def main() -> int:
    parser = argparse.ArgumentParser(description="Generate or verify the experiment datasets.")
    parser.add_argument("--verify", action="store_true", help="check files against the manifest and the seeds")
    args = parser.parse_args()
    if args.verify:
        return verify()
    generate()
    return 0

if __name__ == "__main__":
    sys.exit(main())
