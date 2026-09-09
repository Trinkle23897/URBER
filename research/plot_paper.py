"""Plot published Table II results beside measurements of the same cases."""

import argparse
import json
import os
from pathlib import Path

from research.experiment import ROOT
from research.paper import published_cases

os.environ.setdefault("MPLCONFIGDIR", str(ROOT / "results/matplotlib"))
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--results", type=Path, default=ROOT / "benchmarks/paper/reproduced_ii.jsonl"
    )
    args = parser.parse_args()
    cases = published_cases("ii")
    measured = {
        (r["N"], r["M"], r["method"]): r
        for r in map(json.loads, args.results.read_text().splitlines())
    }
    x = np.arange(len(cases))
    labels = [f"{r['N']} x {r['M']}" for r in cases]
    colors = dict(
        published="#718096", paper="#2563a6", geometric="#14856d", mcf="#b3693d"
    )
    plt.rcParams.update({"svg.hashsalt": "urber-paper", "font.size": 10})
    fig = plt.figure(figsize=(15, 10), facecolor="#fafbf9")
    grid = fig.add_gridspec(
        2, 2, left=0.07, right=0.98, top=0.84, bottom=0.15, hspace=0.55, wspace=0.2
    )
    quality = fig.add_subplot(grid[0, :])
    published = [r["urber_length"] - r["mcf_length"] for r in cases]
    paper = [
        measured[r["N"], r["M"], "paper"]["total_length"] - r["mcf_length"]
        for r in cases
    ]
    geometric = [
        measured[r["N"], r["M"], "geometric"]["total_length"] - r["mcf_length"]
        for r in cases
    ]
    for offset, values, color, label in [
        (-0.24, published, colors["published"], "Published URBER"),
        (0, paper, colors["paper"], "Paper-method reconstruction"),
        (0.24, geometric, colors["geometric"], "Improved geometric replay"),
    ]:
        quality.bar(x + offset, values, width=0.22, color=color, label=label)
        quality.scatter(x + offset, values, color=color, s=18, zorder=3)
        for i, value in enumerate(values):
            if value:
                quality.annotate(
                    str(value),
                    (i + offset, value),
                    xytext=(0, 5),
                    textcoords="offset points",
                    ha="center",
                    fontsize=9,
                )
    quality.set(
        title="Wire length: excess over the paper's MCF optimum (zero is optimal)",
        ylabel="Extra grid steps",
        xticks=x,
        xticklabels=labels,
    )
    quality.set_ylim(-0.35, max(published + paper + geometric + [1]) * 1.35)
    quality.legend(loc="upper left", ncol=3, frameon=False)
    original = fig.add_subplot(grid[1, 0])
    local = fig.add_subplot(grid[1, 1])
    for key, label in [("mcf", "Published MCF"), ("urber", "Published URBER")]:
        original.semilogy(
            x,
            [r[f"{key}_seconds"] for r in cases],
            "o-",
            color=colors["mcf" if key == "mcf" else "published"],
            label=label,
        )
    for key, label in [
        ("paper", "Paper-method reconstruction"),
        ("geometric", "Geometric replay"),
    ]:
        local.semilogy(
            x,
            [measured[r["N"], r["M"], key]["wall_seconds"] for r in cases],
            "o-",
            color=colors[key],
            label=label,
        )
    for ax, title, ylabel in [
        (original, "Published timings: Table II", "CPU seconds (original Xeon system)"),
        (local, "Local reproduction timings", "Wall seconds (current machine)"),
    ]:
        ax.set(title=title, ylabel=ylabel, xticks=x, xticklabels=labels)
        ax.tick_params(axis="x", rotation=45)
        ax.legend(frameon=False)
    for ax in (quality, original, local):
        ax.set_facecolor("#fafbf9")
        ax.grid(axis="y", alpha=0.2)
        ax.spines[["top", "right"]].set_visible(False)
    fig.text(
        0.07,
        0.94,
        "URBER: comparison on the paper's published cases",
        fontsize=23,
        color="#173c36",
    )
    fig.text(
        0.07,
        0.89,
        "All methods use Table II's exact (N, M, d). Published values and local measurements are kept distinct.",
        fontsize=12,
    )
    fig.text(
        0.07,
        0.035,
        "Timing panels use different systems and measurement boundaries; do not divide across panels to claim speedup.",
        fontsize=11,
        color="#586b66",
    )
    for ext in ("png", "svg"):
        path = ROOT / f"assets/paper-comparison.{ext}"
        fig.savefig(path, dpi=160, metadata={"Date": None} if ext == "svg" else None)
        if ext == "svg":
            path.write_text(
                "\n".join(line.rstrip() for line in path.read_text().splitlines())
                + "\n"
            )
    plt.close(fig)


if __name__ == "__main__":
    main()
