import re
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


RESULTS_DIR = Path(__file__).resolve().parent
PLOTS_DIR = RESULTS_DIR / "plots"
PLOTS_DIR.mkdir(parents=True, exist_ok=True)


def normalize(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(s).strip().lower())


def find_col(df: pd.DataFrame, candidates: list[str]) -> str:
    normalized_map = {normalize(c): c for c in df.columns}
    for cand in candidates:
        key = normalize(cand)
        if key in normalized_map:
            return normalized_map[key]
    raise KeyError(f"Cannot find any of columns {candidates} in {list(df.columns)}")


def safe_read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


def parse_prefix(prefix: str):
    m = re.match(r"^lf_w(\d+)_r(\d+)_ratio_(\d+)_(\d+)$", prefix)
    if m:
        w, r, wr, rr = m.groups()
        return {
            "system": "Leader-Follower",
            "w": int(w),
            "r": int(r),
            "write_pct": int(wr),
            "read_pct": int(rr),
            "label": f"LF W={w} R={r} {wr}/{rr}",
        }

    m = re.match(r"^leaderless_w(\d+)_r(\d+)_ratio_(\d+)_(\d+)$", prefix)
    if m:
        w, r, wr, rr = m.groups()
        return {
            "system": "Leaderless",
            "w": int(w),
            "r": int(r),
            "write_pct": int(wr),
            "read_pct": int(rr),
            "label": f"Leaderless W={w} R={r} {wr}/{rr}",
        }

    return {
        "system": "Unknown",
        "w": None,
        "r": None,
        "write_pct": None,
        "read_pct": None,
        "label": prefix,
    }


def discover_prefixes():
    prefixes = []
    for path in RESULTS_DIR.glob("*_stats.csv"):
        name = path.name
        if name.endswith("_stats_history.csv"):
            continue
        prefix = name[:-10]  # remove "_stats.csv"
        prefixes.append(prefix)
    return sorted(set(prefixes))


def get_request_row(stats_df: pd.DataFrame, method: str):
    if stats_df.empty:
        return None

    type_col = None
    name_col = None

    try:
        type_col = find_col(stats_df, ["Type", "Method"])
    except KeyError:
        pass

    try:
        name_col = find_col(stats_df, ["Name"])
    except KeyError:
        return None

    df = stats_df.copy()
    if type_col is not None:
        method_mask = df[type_col].astype(str).str.upper() == method.upper()
        name_mask = df[name_col].astype(str).str.contains("/kv/{key}", regex=False, na=False)
        rows = df[method_mask & name_mask]
        if not rows.empty:
            return rows.iloc[0]

    rows = df[df[name_col].astype(str).str.upper().str.startswith(method.upper())]
    if not rows.empty:
        return rows.iloc[0]

    rows = df[df[name_col].astype(str).str.contains("/kv/{key}", regex=False, na=False)]
    if not rows.empty:
        return rows.iloc[0]

    return None


def metric_from_row(row, candidates, default=0.0):
    if row is None:
        return default
    for cand in candidates:
        for col in row.index:
            if normalize(col) == normalize(cand):
                try:
                    return float(row[col])
                except Exception:
                    return default
    return default


def make_interval_hist(prefix: str):
    path = RESULTS_DIR / f"{prefix}_read_write_intervals.csv"
    df = safe_read_csv(path)
    if df.empty or "delta_ms" not in df.columns:
        return

    series = pd.to_numeric(df["delta_ms"], errors="coerce").dropna()
    if series.empty:
        return

    plt.figure(figsize=(10, 6))
    plt.hist(series, bins=60)
    plt.yscale("log")
    plt.xlabel("Read-after-write interval (ms)")
    plt.ylabel("Count (log scale)")
    plt.title(f"{prefix} - Read/Write interval distribution")
    plt.tight_layout()
    plt.savefig(PLOTS_DIR / f"{prefix}_interval_hist.png", dpi=200)
    plt.close()


def build_summary(prefix: str):
    meta = parse_prefix(prefix)

    stats_path = RESULTS_DIR / f"{prefix}_stats.csv"
    stale_path = RESULTS_DIR / f"{prefix}_stale_reads.csv"
    interval_path = RESULTS_DIR / f"{prefix}_read_write_intervals.csv"

    stats_df = safe_read_csv(stats_path)
    stale_df = safe_read_csv(stale_path)
    interval_df = safe_read_csv(interval_path)

    get_row = get_request_row(stats_df, "GET")
    put_row = get_request_row(stats_df, "PUT")

    read_count = metric_from_row(get_row, ["Request Count"], 0.0)
    write_count = metric_from_row(put_row, ["Request Count"], 0.0)

    summary = {
        "prefix": prefix,
        "label": meta["label"],
        "system": meta["system"],
        "W": meta["w"],
        "R": meta["r"],
        "write_pct": meta["write_pct"],
        "read_pct": meta["read_pct"],

        "read_requests": int(read_count),
        "write_requests": int(write_count),

        "read_avg_ms": metric_from_row(get_row, ["Average Response Time"], 0.0),
        "read_median_ms": metric_from_row(get_row, ["Median Response Time"], 0.0),
        "read_p95_ms": metric_from_row(get_row, ["95%"], 0.0),
        "read_p99_ms": metric_from_row(get_row, ["99%"], 0.0),
        "read_max_ms": metric_from_row(get_row, ["Max Response Time"], 0.0),

        "write_avg_ms": metric_from_row(put_row, ["Average Response Time"], 0.0),
        "write_median_ms": metric_from_row(put_row, ["Median Response Time"], 0.0),
        "write_p95_ms": metric_from_row(put_row, ["95%"], 0.0),
        "write_p99_ms": metric_from_row(put_row, ["99%"], 0.0),
        "write_max_ms": metric_from_row(put_row, ["Max Response Time"], 0.0),

        "stale_reads": int(len(stale_df)) if not stale_df.empty else 0,
        "stale_rate_pct": (len(stale_df) / read_count * 100.0) if read_count else 0.0,

        "avg_interval_ms": float(pd.to_numeric(interval_df.get("delta_ms", pd.Series(dtype=float)), errors="coerce").dropna().mean()) if not interval_df.empty else 0.0,
        "median_interval_ms": float(pd.to_numeric(interval_df.get("delta_ms", pd.Series(dtype=float)), errors="coerce").dropna().median()) if not interval_df.empty else 0.0,
        "p95_interval_ms": float(pd.to_numeric(interval_df.get("delta_ms", pd.Series(dtype=float)), errors="coerce").dropna().quantile(0.95)) if not interval_df.empty else 0.0,
    }

    return summary


def plot_bar(df: pd.DataFrame, value_col: str, title: str, ylabel: str, filename: str):
    plot_df = df.sort_values(["system", "W", "R", "write_pct"]).copy()

    plt.figure(figsize=(16, 7))
    plt.bar(plot_df["label"], plot_df[value_col])
    plt.xticks(rotation=45, ha="right")
    plt.ylabel(ylabel)
    plt.title(title)
    plt.tight_layout()
    plt.savefig(PLOTS_DIR / filename, dpi=200)
    plt.close()


def main():
    prefixes = discover_prefixes()
    if not prefixes:
        print("No *_stats.csv files found in results/")
        return

    summaries = []
    for prefix in prefixes:
        summaries.append(build_summary(prefix))
        make_interval_hist(prefix)

    summary_df = pd.DataFrame(summaries)
    summary_df.to_csv(RESULTS_DIR / "experiment_summary.csv", index=False)

    plot_bar(summary_df, "read_avg_ms", "Read average latency comparison", "Average latency (ms)", "read_avg_latency.png")
    plot_bar(summary_df, "read_p95_ms", "Read p95 latency comparison", "p95 latency (ms)", "read_p95_latency.png")
    plot_bar(summary_df, "read_p99_ms", "Read p99 latency comparison", "p99 latency (ms)", "read_p99_latency.png")

    plot_bar(summary_df, "write_avg_ms", "Write average latency comparison", "Average latency (ms)", "write_avg_latency.png")
    plot_bar(summary_df, "write_p95_ms", "Write p95 latency comparison", "p95 latency (ms)", "write_p95_latency.png")
    plot_bar(summary_df, "write_p99_ms", "Write p99 latency comparison", "p99 latency (ms)", "write_p99_latency.png")

    plot_bar(summary_df, "stale_reads", "Stale read count comparison", "Stale reads", "stale_reads.png")
    plot_bar(summary_df, "stale_rate_pct", "Stale read rate comparison", "Stale read rate (%)", "stale_read_rate.png")
    plot_bar(summary_df, "avg_interval_ms", "Average read/write interval comparison", "Average interval (ms)", "avg_interval.png")
    plot_bar(summary_df, "p95_interval_ms", "p95 read/write interval comparison", "p95 interval (ms)", "p95_interval.png")

    print("Done.")
    print(f"Summary CSV: {RESULTS_DIR / 'experiment_summary.csv'}")
    print(f"Plots dir:    {PLOTS_DIR}")


if __name__ == "__main__":
    main()
