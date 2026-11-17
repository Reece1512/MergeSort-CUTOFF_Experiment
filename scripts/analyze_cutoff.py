from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_experiment import tree_signature

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"
FIGURES = ROOT / "report" / "figures"
TEXTBOOK = (7, 10)
BOOTSTRAP_ROUNDS = 2000
BOOTSTRAP_SEED = 20261115
PRACTICAL_PCT = 2.0

SURFACE, INK, INK_2, MUTED, GRID, AXIS = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300"]
MARKERS = ["o", "s", "^", "D", "v", "P"]
BLUE_RAMP = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]

def parse_dataset(name: str) -> tuple[str, int, int]:
    parts = name.split("_")
    seed = 0
    if parts[-1].startswith("s") and parts[-1][1:].isdigit():
        seed = int(parts[-1][1:])
        parts = parts[:-1]
    return "_".join(parts[:-1]), int(parts[-1]), seed

def load_iterations(campaign: str) -> pd.DataFrame:
    rows = []
    for name in campaign.split(","):
        rows += load_campaign_rows(name)
    if not rows:
        sys.exit(f"No single-shot results in results/{campaign}")
    return pd.DataFrame(rows, columns=["campaign", "variant", "dataset", "distribution", "n", "seed", "cutoff",
                                       "fork", "iteration", "ms"])

def load_campaign_rows(campaign: str) -> list[tuple]:
    runs_dir = RESULTS / campaign / "runs"
    rows = []
    for path in sorted(runs_dir.glob("*.json")):
        result = json.loads(path.read_text(encoding="utf-8"))[0]
        if result["mode"] != "ss" or "cutoff" not in result["params"]:
            continue
        parts = path.stem.split("__")
        variant = parts[0] if len(parts) == 3 else ""
        dataset = result["params"]["dataset"]
        distribution, n, seed = parse_dataset(dataset)
        unit = result["primaryMetric"]["scoreUnit"]
        to_ms = {"ns/op": 1e-6, "us/op": 1e-3, "ms/op": 1.0, "s/op": 1e3}[unit]
        for fork, values in enumerate(result["primaryMetric"]["rawData"]):
            for iteration, value in enumerate(values):
                rows.append((campaign, variant, dataset, distribution, n, seed, int(result["params"]["cutoff"]),
                             fork, iteration, value * to_ms))
    return rows

def fork_means(iterations: pd.DataFrame) -> pd.DataFrame:
    keys = ["campaign", "variant", "dataset", "distribution", "n", "seed", "cutoff", "fork"]
    return iterations.groupby(keys, as_index=False).ms.mean()

def t_interval(logs: np.ndarray) -> tuple[float, float, float, float]:
    mean = float(np.mean(logs))
    if len(logs) < 2 or np.allclose(logs, logs[0]):
        return math.exp(mean), math.nan, math.nan, math.nan
    sem = stats.sem(logs)
    half = stats.t.ppf(0.975, len(logs) - 1) * sem
    p_value = float(stats.ttest_1samp(logs, 0.0).pvalue)
    return math.exp(mean), math.exp(mean - half), math.exp(mean + half), p_value

def markdown_table(frame: pd.DataFrame, digits: int = 3) -> str:
    def cell(value) -> str:
        if isinstance(value, float):
            return "" if math.isnan(value) else f"{value:.{digits}f}"
        return str(value)

    header = "| " + " | ".join(str(column) for column in frame.columns) + " |"
    rule = "|" + "|".join("---" for _ in frame.columns) + "|"
    body = ["| " + " | ".join(cell(value) for value in row) + " |" for row in frame.itertuples(index=False)]
    return "\n".join([header, rule, *body])

def ranges(values: list[int]) -> str:
    values = sorted(values)
    if not values:
        return "–"
    parts, start, previous = [], values[0], values[0]
    for value in values[1:] + [None]:
        if value is not None and value == previous + 1:
            previous = value
            continue
        parts.append(str(start) if start == previous else f"{start}–{previous}")
        if value is not None:
            start = previous = value
    return ", ".join(parts)

def style_axes(axis, title: str, xlabel: str, ylabel: str) -> None:
    axis.set_facecolor(SURFACE)
    axis.set_title(title, color=INK, fontsize=11, loc="left")
    axis.set_xlabel(xlabel, color=INK_2, fontsize=9)
    axis.set_ylabel(ylabel, color=INK_2, fontsize=9)
    axis.grid(True, color=GRID, linewidth=0.6)
    axis.set_axisbelow(True)
    for side in ("top", "right"):
        axis.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        axis.spines[side].set_color(AXIS)
    axis.tick_params(colors=MUTED, labelsize=8)

def save(figure, name: str) -> Path:
    FIGURES.mkdir(parents=True, exist_ok=True)
    path = FIGURES / name
    figure.patch.set_facecolor(SURFACE)
    figure.tight_layout()
    figure.savefig(path, dpi=170)
    plt.close(figure)
    return path

def size_label(n: int) -> str:
    exponent = round(math.log10(n))
    return f"N = 10^{exponent}" if 10**exponent == n else f"N = {n:,}".replace(",", ".")

def analyze_pilot(campaign: str) -> None:
    data = load_iterations(campaign)
    out = RESULTS / f"analysis_{campaign.replace(',', '+')}"
    out.mkdir(parents=True, exist_ok=True)
    lines = [f"# Pilot `{campaign}`", ""]

    warmup_rows, cv_rows = [], []
    for (variant, n), group in data.groupby(["variant", "n"]):
        iterations = int(group.iteration.max()) + 1
        window = max(iterations // 5, 3)
        candidates = [w for w in (0, 5, 10, 15, 20, 30, 40, 50, 75, 100) if w + window <= iterations - window]
        deviations = {w: [] for w in candidates}
        for _, series in group.groupby(["cutoff", "fork"]):
            times = series.sort_values("iteration").ms.to_numpy()
            steady = times[-window:].mean()
            for w in candidates:
                deviations[w].append(abs(times[w:w + window].mean() / steady - 1) * 100)
        enough = next((w for w in candidates if np.percentile(deviations[w], 90) <= PRACTICAL_PCT), None)
        for w in candidates:
            warmup_rows.append({"variant": variant, "n": n, "w": w, "mean_dev_pct": np.mean(deviations[w]),
                                "p90_dev_pct": np.percentile(deviations[w], 90), "max_dev_pct": np.max(deviations[w]),
                                "enough": w == enough})
        for cutoff, series in group.groupby("cutoff"):
            last = series[series.iteration >= iterations - window].groupby("fork").ms.mean()
            cv_rows.append({"variant": variant, "n": n, "cutoff": cutoff, "forks": len(last),
                            "mean_ms": last.mean(), "cv_pct": 100 * last.std(ddof=1) / last.mean(),
                            "fork_means_ms": " ".join(f"{value:.3f}" for value in sorted(last))})

    warmup = pd.DataFrame(warmup_rows)
    cv = pd.DataFrame(cv_rows)
    warmup.to_csv(out / "warmup.csv", index=False)
    cv.to_csv(out / "fork_cv.csv", index=False)

    lines += ["## Warm-up", "",
              f"Độ lệch (%) của trung bình M vòng bắt đầu từ vòng w so với M vòng cuối; đủ khi p90 ≤ {PRACTICAL_PCT:g}%.", ""]
    for (variant, n), group in warmup.groupby(["variant", "n"]):
        chosen = group[group.enough]
        verdict = f"đủ từ w = {int(chosen.w.iloc[0])}" if len(chosen) else "chưa đủ trong khoảng đã thử"
        lines += [f"**{variant or 'mặc định'}, {size_label(n)}**: {verdict}", "",
                  markdown_table(group.drop(columns=["variant", "n", "enough"]), 2), ""]

    lines += ["## Độ lệch giữa các fork (CV, %)", "", markdown_table(cv, 3), ""]
    summary = cv.groupby("variant").cv_pct.median()
    lines += ["Trung vị CV theo GC: " + ", ".join(f"{name} {value:.2f}%" for name, value in summary.items()), ""]
    if {"g1", "parallel"} <= set(summary.index):
        gap = summary["g1"] - summary["parallel"]
        choice = "ParallelGC" if gap >= 1.0 else "G1"
        lines += [f"**Quyết định:** dùng {choice} (quy tắc: đổi sang ParallelGC chỉ khi trung vị CV thấp hơn G1 "
                  f"ít nhất 1 điểm phần trăm; chênh lệch đo được {gap:+.2f}).", ""]
    speed = cv.pivot_table(index=["n", "cutoff"], columns="variant", values="mean_ms")
    if {"g1", "parallel"} <= set(speed.columns):
        speed["parallel/g1"] = speed["parallel"] / speed["g1"]
        lines += ["Thời gian trung bình (ms) theo GC:", "", markdown_table(speed.reset_index(), 3), ""]

    figure = plot_warmup(data)
    lines += [f"![Warm-up](../../report/figures/{figure.name})", ""]
    (out / "summary.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

def plot_warmup(data: pd.DataFrame) -> Path:
    sizes = sorted(data.n.unique())
    variants = sorted(data.variant.unique())
    cutoff = 10 if 10 in set(data.cutoff) else int(data.cutoff.min())
    figure, axes = plt.subplots(1, len(sizes), figsize=(4.2 * len(sizes), 3.4))
    axes = np.atleast_1d(axes)
    for axis, n in zip(axes, sizes):
        subset = data[(data.n == n) & (data.cutoff == cutoff)]
        steady = subset[subset.iteration >= subset.iteration.max() * 0.8].ms.median()
        for index, variant in enumerate(variants):
            for fork, series in subset[subset.variant == variant].groupby("fork"):
                series = series.sort_values("iteration")
                axis.plot(series.iteration, series.ms / steady, color=SERIES[index], linewidth=1.2, alpha=0.85,
                          label=(variant or "mặc định") if fork == 0 else None)
        axis.set_ylim(0.8, 2.0)
        style_axes(axis, f"{size_label(n)}, cutoff {cutoff}", "vòng", "thời gian / mức ổn định")
    axes[0].legend(frameon=False, fontsize=8, labelcolor=INK_2)
    return save(figure, "pilot_warmup.png")

def class_table(forks: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for dataset, group in forks.groupby("dataset"):
        distribution, n, seed = parse_dataset(dataset)
        by_class: dict[tuple, list[float]] = {}
        for cutoff, values in group.groupby("cutoff").ms:
            by_class.setdefault(tree_signature(n, cutoff), []).extend(values.tolist())
        measured = set(group.cutoff)
        for cutoff in range(int(forks.cutoff.max()) + 1):
            values = by_class.get(tree_signature(n, cutoff))
            if values is None:
                continue
            rows.append({"dataset": dataset, "distribution": distribution, "n": n, "seed": seed, "cutoff": cutoff,
                         "ms": float(np.mean(values)), "forks": len(values), "measured": cutoff in measured})
    return pd.DataFrame(rows)

def wide(table: pd.DataFrame) -> pd.DataFrame:
    return table.pivot(index="dataset", columns="cutoff", values="ms").dropna(axis=1)

def curve(table: pd.DataFrame) -> tuple[pd.Series, int]:
    logs = np.log(wide(table))
    logs = logs.sub(logs.mean(axis=1), axis=0)
    relative = np.exp(logs.mean(axis=0))
    best = int(relative.idxmin())
    return relative / relative[best], best

def paired(table: pd.DataFrame, a: int, b: int) -> dict:
    wide_ms = wide(table)
    if a not in wide_ms.columns or b not in wide_ms.columns:
        return {"so_sanh": f"{a} vs {b}", "datasets": 0}
    logs = np.log(wide_ms[a] / wide_ms[b]).to_numpy()
    ratio, low, high, p_value = t_interval(logs)
    return {"so_sanh": f"{a} vs {b}", "datasets": len(logs), "ti_so": ratio, "ci95_thap": low, "ci95_cao": high,
            "p": p_value, "cham_hon_o": f"{int((logs > 0).sum())}/{len(logs)}"}

def near_best(table: pd.DataFrame, best: int) -> tuple[list[int], list[int]]:
    wide_ms = wide(table)
    statistical, practical = [], []
    for cutoff in wide_ms.columns:
        logs = np.log(wide_ms[cutoff] / wide_ms[best]).to_numpy()
        ratio, low, _, _ = t_interval(logs)
        if cutoff == best or math.isnan(low) or low <= 1.0:
            statistical.append(int(cutoff))
        if ratio <= 1 + PRACTICAL_PCT / 100:
            practical.append(int(cutoff))
    return statistical, practical

def bootstrap_best(table: pd.DataFrame) -> pd.Series:
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    logs = np.log(wide(table))
    logs = logs.sub(logs.mean(axis=1), axis=0)
    groups = [logs.loc[sorted(set(table[table.n == n].dataset))].to_numpy() for n in sorted(table.n.unique())]
    cutoffs = logs.columns.to_numpy()
    winners = []
    for _ in range(BOOTSTRAP_ROUNDS):
        sample = np.vstack([group[rng.integers(0, len(group), len(group))] for group in groups])
        winners.append(int(cutoffs[np.argmin(sample.mean(axis=0))]))
    return pd.Series(winners).value_counts(normalize=True).sort_index()

def analyze_grid(campaign: str) -> None:
    iterations = load_iterations(campaign)
    forks = fork_means(iterations)
    table = class_table(forks)
    out = RESULTS / f"analysis_{campaign.replace(',', '+')}"
    out.mkdir(parents=True, exist_ok=True)
    table.to_csv(out / "time_by_cutoff.csv", index=False)
    lines = [f"# Lưới cutoff `{campaign}`", ""]

    grouped = forks.groupby(["distribution", "n", "dataset", "cutoff"]).ms
    fork_cv = (100 * grouped.std(ddof=1) / grouped.mean()).rename("cv").reset_index()
    quality = fork_cv.groupby(["distribution", "n"]).cv.describe(percentiles=[0.5, 0.9])[["count", "50%", "90%", "max"]]
    quality = quality.reset_index().rename(columns={"count": "cau_hinh", "50%": "cv_trung_vi", "90%": "cv_p90",
                                                    "max": "cv_max"})
    quality.to_csv(out / "fork_cv.csv", index=False)
    lines += ["## Độ lệch giữa các fork (CV, %)", "", markdown_table(quality, 2), ""]

    direct = forks.groupby(["dataset", "cutoff"]).ms.mean().unstack()
    if {0, 1} <= set(direct.columns):
        control = (direct[1] / direct[0]).dropna()
        control.rename("t1_over_t0").to_csv(out / "control_1_vs_0.csv")
        lines += ["## Đối chứng nhiễu: t(1)/t(0)", "",
                  f"{len(control)} dataset: trung vị {control.median():.3f}, nhỏ nhất {control.min():.3f}, "
                  f"lớn nhất {control.max():.3f}. Lý tưởng là 1,000.", ""]

    summary_rows, pair_rows, curves = [], [], {}
    for (distribution, n), subset in table.groupby(["distribution", "n"]):
        relative, best = curve(subset)
        curves[(distribution, n)] = relative
        statistical, practical = near_best(subset, best)
        datasets = subset.dataset.nunique()
        best_class = [c for c in sorted(subset.cutoff.unique()) if tree_signature(n, c) == tree_signature(n, best)]
        summary_rows.append({"phan_bo": distribution, "N": n, "datasets": datasets,
                             "nhom_tot_nhat": ranges(best_class),
                             "khong_khac_biet_thong_ke": ranges(statistical) if datasets >= 3 else "(cần ≥ 3 seed)",
                             f"cham_hon_<=_{PRACTICAL_PCT:g}%": ranges(practical),
                             "rel_0": relative.get(0, math.nan), "rel_7": relative.get(7, math.nan), "rel_10": relative.get(10, math.nan),
                             "ms_tot_nhat": subset[subset.cutoff == best].ms.mean()})
        for a, b in [(0, best), (7, best), (10, best), (7, 10)]:
            if a != b and datasets >= 2:
                pair_rows.append({"phan_bo": distribution, "N": n, **paired(subset, a, b)})
    summary = pd.DataFrame(summary_rows)
    summary.to_csv(out / "best_by_group.csv", index=False)
    lines += ["## CUTOFF tốt nhất theo phân bố và N", "",
              "`rel_X` = thời gian của cutoff X chia cho thời gian của cutoff tốt nhất.", "",
              markdown_table(summary, 3), ""]

    random_table = table[table.distribution == "random"]
    if not random_table.empty and random_table.n.nunique() > 1:
        relative, best = curve(random_table)
        statistical, practical = near_best(random_table, best)
        frequencies = bootstrap_best(random_table)
        order = frequencies.sort_values(ascending=False)
        covered = order.index[: int(np.searchsorted(order.cumsum().to_numpy(), 0.9) + 1)].tolist()
        lines += ["## Kết luận gộp: dữ liệu ngẫu nhiên, mọi N", "",
                  f"- CUTOFF tốt nhất: **{best}**",
                  f"- Không khác biệt có ý nghĩa thống kê với {best}: {ranges(statistical)}",
                  f"- Chậm hơn {best} không quá {PRACTICAL_PCT:g}%: {ranges(practical)}",
                  f"- Bootstrap ({BOOTSTRAP_ROUNDS} lần): {best} thắng {frequencies.get(best, 0):.0%} số lần; "
                  f"các cutoff chiếm 90% số lần thắng: {ranges(covered)}",
                  f"- Thời gian tương đối: cutoff 0 = {relative.get(0, math.nan):.3f}, 7 = {relative.get(7, math.nan):.3f}, 10 = {relative.get(10, math.nan):.3f}", ""]
        frequencies.rename("ti_le_thang").to_csv(out / "bootstrap_best.csv")
        for a, b in [(0, best), (7, best), (10, best), (7, 10)]:
            if a != b:
                pair_rows.append({"phan_bo": "random (mọi N)", "N": "", **paired(random_table, a, b)})
    pairs = pd.DataFrame(pair_rows)
    pairs.to_csv(out / "pairs.csv", index=False)
    lines += ["## So sánh cặp", "", "Tỉ số > 1 nghĩa là cutoff đứng trước chậm hơn.", "",
              markdown_table(pairs, 4), ""]

    figures = [plot_curves(curves, table, campaign)]
    if table.distribution.nunique() > 1:
        figures.append(plot_heatmap(curves, campaign))
    lines += [f"![{path.stem}](../../report/figures/{path.name})" for path in figures] + [""]
    (out / "summary.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

def plot_curves(curves: dict, table: pd.DataFrame, campaign: str) -> Path:
    distributions = sorted({distribution for distribution, _ in curves})
    figure, axes = plt.subplots(len(distributions), 1, figsize=(8.5, 3.6 * len(distributions)), squeeze=False)
    for axis, distribution in zip(axes[:, 0], distributions):
        sizes = sorted(n for d, n in curves if d == distribution)
        widest = max(int(curves[(distribution, n)].index.max()) for n in sizes)
        extended = widest > 64
        top = 1.0
        for index, n in enumerate(sizes):
            relative = curves[(distribution, n)]
            subset = table[(table.distribution == distribution) & (table.n == n)]
            best = int(relative.idxmin())
            table_ms = wide(subset)
            logs = np.log(table_ms.div(table_ms[best], axis=0))
            spread = np.exp(logs.std(axis=0, ddof=1) / np.sqrt(len(table_ms))) if len(table_ms) > 1 else None
            color = SERIES[index]
            axis.plot(relative.index, relative.values, color=color, linewidth=2, marker=MARKERS[index],
                      markersize=0 if extended else 4, label=size_label(n))
            if spread is not None:
                axis.fill_between(relative.index, relative / spread, relative * spread, color=color, alpha=0.12,
                                  linewidth=0)
            axis.annotate(size_label(n), (relative.index[-1], relative.iloc[-1]), xytext=(4, 0), textcoords="offset points",
                          color=INK_2, fontsize=8, va="center")
            top = max(top, float(relative.max()))
        for cutoff, side in zip(TEXTBOOK, ("right", "left")):
            axis.axvline(cutoff, color=AXIS, linewidth=1, linestyle="--")
            axis.annotate(str(cutoff), (cutoff, 1.0), xycoords=("data", "axes fraction"),
                          xytext=(-3 if side == "right" else 3, -10), textcoords="offset points",
                          ha=side, color=MUTED, fontsize=8)
        if extended:
            axis.set_xscale("symlog", base=2, linthresh=1)
            ticks = [0] + [2**k for k in range(int(math.log2(widest)) + 1)]
            axis.set_xticks(ticks, [str(tick) for tick in ticks])
            axis.set_xlim(0, widest * 1.6)
            axis.set_ylim(0.98, top * 1.04)
        else:
            axis.set_xlim(0, 70)
            axis.set_ylim(0.98, min(top * 1.02, 1.6))
        style_axes(axis, f"{distribution}: thời gian so với cutoff tốt nhất (nét đứt: 7 và 10 của giáo trình; dải mờ: ±1 sai số chuẩn)", "CUTOFF",
                   "thời gian tương đối")
        if len(sizes) > 1:
            axis.legend(frameon=False, fontsize=8, labelcolor=INK_2, loc="upper left" if extended else "upper center",
                        ncol=1 if extended else len(sizes))
    return save(figure, f"{campaign.replace(',', '+')}_curves.png")

def plot_heatmap(curves: dict, campaign: str) -> Path:
    keys = sorted(curves)
    span = range(int(max(curve.index.max() for curve in curves.values())) + 1)
    matrix = np.vstack([curves[key].reindex(span).to_numpy() for key in keys])
    colormap = LinearSegmentedColormap.from_list("blue_ramp", BLUE_RAMP)
    figure, axis = plt.subplots(figsize=(10, 0.45 * len(keys) + 1.4))
    image = axis.imshow(matrix, aspect="auto", cmap=colormap, vmin=1.0, vmax=1.3, interpolation="nearest")
    axis.set_yticks(range(len(keys)), [f"{distribution}, {size_label(n)}" for distribution, n in keys])
    axis.set_xticks(range(0, 65, 4))
    style_axes(axis, "Thời gian so với cutoff tốt nhất của từng dòng (đậm hơn = chậm hơn)", "CUTOFF", "")
    axis.grid(False)
    for row, key in enumerate(keys):
        best = int(curves[key].idxmin())
        axis.plot(best, row, marker="o", markersize=5, color=SURFACE, markeredgecolor=INK, markeredgewidth=0.8)
    bar = figure.colorbar(image, ax=axis, fraction=0.03, pad=0.01)
    bar.ax.tick_params(labelsize=8, colors=MUTED)
    bar.set_label("thời gian tương đối (cắt ở 1,3)", color=INK_2, fontsize=8)
    return save(figure, f"{campaign.replace(',', '+')}_heatmap.png")

def analyze_doubling(campaign: str) -> None:
    forks = fork_means(load_iterations(campaign))
    times = forks.groupby(["n", "cutoff"]).ms.mean().unstack()
    out = RESULTS / f"analysis_{campaign.replace(',', '+')}"
    out.mkdir(parents=True, exist_ok=True)
    times.to_csv(out / "time_ms.csv")
    lines = [f"# Doubling test `{campaign}`", "", "## Thời gian (ms)", "", markdown_table(times.reset_index(), 3), ""]

    sizes = times.index.to_numpy()
    ratio_rows = []
    for small, large in zip(sizes[:-1], sizes[1:]):
        row = {"N -> 2N": f"{small:,} -> {large:,}".replace(",", "."),
               "N lg N": (large * math.log2(large)) / (small * math.log2(small))}
        row.update({f"c={cutoff}": times.loc[large, cutoff] / times.loc[small, cutoff] for cutoff in times.columns})
        ratio_rows.append(row)
    ratios = pd.DataFrame(ratio_rows)
    ratios.to_csv(out / "ratios.csv", index=False)
    lines += ["## Tỉ số T(2N)/T(N)", "", "Cột `N lg N` là tỉ số lý thuyết nếu T(N) = a·N·lg N.", "",
              markdown_table(ratios, 3), ""]

    halves = {"mọi N": sizes, "nửa nhỏ": sizes[: len(sizes) // 2 + 1], "nửa lớn": sizes[len(sizes) // 2:]}
    fit_rows = []
    for label, chosen in halves.items():
        row = {"khoang": f"{label} ({chosen[0]:,}–{chosen[-1]:,})".replace(",", ".")}
        log_n = np.log2(chosen)
        row["b (N lg N)"] = float(np.polyfit(log_n, np.log2(chosen * np.log2(chosen)), 1)[0])
        for cutoff in times.columns:
            row[f"b c={cutoff}"] = float(np.polyfit(log_n, np.log2(times.loc[chosen, cutoff]), 1)[0])
        fit_rows.append(row)
    fits = pd.DataFrame(fit_rows)
    fits.to_csv(out / "power_law.csv", index=False)
    lines += ["## Mô hình T(N) ≈ a·N^b", "", markdown_table(fits, 3), ""]

    figure = plot_doubling(times, campaign)
    lines += [f"![doubling](../../report/figures/{figure.name})", ""]
    (out / "summary.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

def plot_doubling(times: pd.DataFrame, campaign: str) -> Path:
    figure, (left, right) = plt.subplots(1, 2, figsize=(11, 4))
    sizes = times.index.to_numpy()
    if len(times.columns) > len(SERIES):
        sys.exit(f"At most {len(SERIES)} cutoffs can be drawn with distinct colors")
    ends = []
    for index, cutoff in enumerate(times.columns):
        color, marker = SERIES[index], MARKERS[index]
        left.plot(sizes, times[cutoff], color=color, marker=marker, markersize=5, linewidth=2, label=f"cutoff {cutoff}")
        per_op = times[cutoff] / (sizes * np.log2(sizes)) * 1e6
        right.plot(sizes, per_op, color=color, marker=marker, markersize=5, linewidth=2, label=f"cutoff {cutoff}")
        ends.append([float(per_op.iloc[-1]), str(cutoff)])
    ends.sort()
    low, high = right.get_ylim()
    gap = (high - low) * 0.04
    original = [value for value, _ in ends]
    for position in range(1, len(ends)):
        ends[position][0] = max(ends[position][0], ends[position - 1][0] + gap)
    shift = np.mean([value for value, _ in ends]) - np.mean(original)
    for entry in ends:
        entry[0] -= shift
    for value, label in ends:
        right.annotate(label, (sizes[-1], value), xytext=(6, 0), textcoords="offset points", color=INK_2,
                       fontsize=8, va="center", annotation_clip=False)
    reference = times.iloc[0, 0] * (sizes * np.log2(sizes)) / (sizes[0] * math.log2(sizes[0]))
    left.plot(sizes, reference, color=MUTED, linestyle="--", linewidth=1, label="tỉ lệ N lg N")
    for axis in (left, right):
        axis.set_xscale("log", base=2)
    left.set_yscale("log", base=2)
    style_axes(left, "T(N) trên thang log–log", "N", "thời gian (ms)")
    style_axes(right, "T(N) / (N lg N): hằng số a của mô hình", "N", "ns cho mỗi N lg N")
    left.legend(frameon=False, fontsize=8, labelcolor=INK_2)
    return save(figure, f"{campaign}_doubling.png")

def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze single-shot cutoff campaigns.")
    parser.add_argument("kind", choices=["pilot", "grid", "doubling"])
    parser.add_argument("--campaign", help="folder under results/ (default: pilot_ss, e1 or e4)")
    args = parser.parse_args()
    default = {"pilot": "pilot_ss", "grid": "e1", "doubling": "e4"}[args.kind]
    campaign = args.campaign or default
    {"pilot": analyze_pilot, "grid": analyze_grid, "doubling": analyze_doubling}[args.kind](campaign)
    return 0

if __name__ == "__main__":
    sys.exit(main())
