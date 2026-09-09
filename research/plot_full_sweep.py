"""Plot complete full-square sweep shards, or explicitly labeled progress."""

import argparse
import gzip
import json
import os
from pathlib import Path

from research.benchmark import ROOT
from research.full_sweep import classify

os.environ.setdefault("MPLCONFIGDIR", str(ROOT / "results/matplotlib"))
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import ListedColormap
from matplotlib.patches import Patch


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--max-n", type=int, default=400)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--allow-incomplete", action="store_true")
    parser.add_argument("--method-kind", choices=("replay", "rules"), default="replay")
    args = parser.parse_args()
    rows = {}
    for path in args.inputs:
        text = (
            gzip.decompress(path.read_bytes()).decode()
            if path.suffix == ".gz"
            else path.read_text()
        )
        for line in text.splitlines():
            row = json.loads(line)
            if args.method_kind == "rules":
                if not row["constructor"].get("verified"):
                    raise ValueError("Unverified deterministic construction")
                row = dict(
                    row,
                    paper={"verified": True, "total_length": row["paper_length"]},
                    geometric=row["constructor"],
                    legacy={
                        "verified": True,
                        "total_length": row["legacy_replay_length"],
                    },
                )
            key = row["N"], row["M"]
            if key in rows or not all(1 <= x <= args.max_n for x in key):
                raise ValueError(f"Duplicate or out-of-domain case: {key}")
            rows[key] = row
    total = args.max_n**2
    if not args.allow_incomplete and len(rows) != total:
        raise ValueError(f"Incomplete sweep: {len(rows)}/{total}")
    statuses = {
        "untested": 0,
        "optimal": 1,
        "nonoptimal": 2,
        "unknown": 3,
        "construction_failed": 4,
    }
    colors = ["#e9edeb", "#70bda8", "#bd6d62", "#edcb8b", "#9b8ab2"]
    fig, axes = plt.subplots(1, 2, figsize=(13, 7), facecolor="#fafbf9")
    for ax, method, other, title in zip(
        axes,
        ["paper", "geometric"],
        ["geometric", "paper"],
        [
            "Paper-method reconstruction",
            "Revised deterministic rules"
            if args.method_kind == "rules"
            else "Improved geometric replay",
        ],
    ):
        grid = np.zeros((args.max_n, args.max_n), dtype=np.uint8)
        count = 0
        for (n, m), row in rows.items():
            witness = row[other]
            if args.method_kind == "rules":
                witness = min((witness, row["legacy"]), key=lambda v: v["total_length"])
            status = classify(row[method], row["lower_bound"], witness)
            grid[n - 1, m - 1] = statuses[status]
            count += status == "optimal"
        ax.imshow(
            grid,
            origin="lower",
            extent=(0.5, args.max_n + 0.5, 0.5, args.max_n + 0.5),
            cmap=ListedColormap(colors),
            vmin=0,
            vmax=4,
            interpolation="nearest",
        )
        ax.set(
            title=f"{title}\n{count:,} proven optimal / {len(rows):,} evaluated",
            xlabel="M",
            ylabel="N",
        )
    qualifier = "PROGRESS — " if len(rows) != total else ""
    fig.suptitle(
        f"{qualifier}is_optimal(N,M): {len(rows):,}/{total:,} ordered pairs evaluated",
        fontsize=16,
    )
    fig.legend(
        handles=[
            Patch(color=colors[i], label=s.replace("_", " ").capitalize())
            for s, i in statuses.items()
        ],
        ncol=5,
        loc="lower center",
        frameon=False,
    )
    fig.tight_layout(rect=(0, 0.07, 1, 0.93))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.output, dpi=170)
    plt.close(fig)
    if args.output.suffix == ".svg":
        args.output.write_text(
            "\n".join(line.rstrip() for line in args.output.read_text().splitlines())
            + "\n"
        )


if __name__ == "__main__":
    main()
