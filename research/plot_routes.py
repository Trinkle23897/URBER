"""Render comparable routing examples from exported path JSON files."""

import argparse
import json
import os
from pathlib import Path

from research.experiment import ROOT

os.environ.setdefault("MPLCONFIGDIR", str(ROOT / "results/matplotlib"))
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from matplotlib.patches import Patch


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--labels", nargs="+")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = [json.loads(p.read_text()) for p in args.paths]
    dimensions = {(r["N"], r["M"], r["d"]) for r in rows}
    if len(dimensions) != 1:
        parser.error("all plots must use the same N, M, and d")
    n, m, d = dimensions.pop()
    labels = args.labels or [p.stem for p in args.paths]
    if len(labels) != len(rows):
        parser.error("provide one label per input file")
    vertical = n > 2 * m
    fig, axes = plt.subplots(
        len(rows) if vertical else 1,
        1 if vertical else len(rows),
        figsize=(14, 3 * len(rows)) if vertical else (5 * len(rows), 6),
        squeeze=False,
        facecolor="#fafbf9",
    )
    colors = ["#2563a6", "#8b5ba6", "#c28432", "#14856d"]
    width, height = (n + 1) * d, (m + 1) * d
    for ax, row, label in zip(axes.flat, rows, labels):
        palette = []
        for path in row["paths"]:
            x, y = path[0]
            side = 0 if y == 0 else 1 if x == 0 else 2 if y == height else 3
            palette.append(colors[side])
        ax.add_collection(
            LineCollection(
                row["paths"],
                colors=palette,
                linewidths=0.65 if n * m < 1000 else 0.4,
                alpha=0.85,
            )
        )
        ax.scatter(
            [x * d for x in range(1, n + 1) for y in range(1, m + 1)],
            [y * d for x in range(1, n + 1) for y in range(1, m + 1)],
            s=2.4,
            color="#173c36",
            zorder=3,
        )
        ax.set(
            xlim=(0, width),
            ylim=(0, height),
            aspect="equal",
            title=f"{label} | L = {row['total_length']:,}",
            xticks=[],
            yticks=[],
        )
        ax.set_facecolor("white")
        for spine in ax.spines.values():
            spine.set_color("#81938b")
    fig.suptitle(f"{n} x {m} terminals, pitch d = {d}", fontsize=19, color="#173c36")
    fig.legend(
        handles=[
            Patch(color=c, label=label)
            for c, label in zip(
                colors, ["Bottom exit", "Left exit", "Top exit", "Right exit"]
            )
        ],
        ncol=4,
        loc="lower center",
        frameon=False,
    )
    fig.tight_layout(rect=(0.01, 0.055, 0.99, 0.95))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.output, dpi=180, facecolor=fig.get_facecolor())
    plt.close(fig)


if __name__ == "__main__":
    main()
