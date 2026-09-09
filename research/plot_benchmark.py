"""Render the complete recorded optimality comparison with English labels."""

import os
import argparse
import csv
import json
from pathlib import Path

from research.benchmark import ROOT, load_cases

os.environ.setdefault("MPLCONFIGDIR", str(ROOT / "results" / "matplotlib"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from matplotlib.patches import Patch
import numpy as np


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--paper-results",
        type=Path,
        default=ROOT / "benchmarks/paper_method_thin_400.csv",
    )
    args = parser.parse_args()
    plt.rcParams["svg.hashsalt"] = "urber-optimality"
    rows = load_cases()
    domain = {(n, m) for n in range(1, 401) for m in range(1, n // 5 + 1)}
    if len(rows) != len(domain) or {(r["N"], r["M"]) for r in rows} != domain:
        raise ValueError("The plot requires the full 15,880-case domain")
    grids = [np.zeros((400, 80), dtype=np.uint8) for _ in range(2)]
    counts = [0, 0]
    if args.paper_results.suffix == ".jsonl":
        paper = {
            (r["N"], r["M"]): r["constructor"]
            for r in (
                json.loads(line) for line in args.paper_results.read_text().splitlines()
            )
        }
    else:
        with args.paper_results.open() as stream:
            paper = {
                (int(r["N"]), int(r["M"])): dict(
                    d=int(r["d"]),
                    verified=r["verified"] == "1",
                    total_length=int(r["total_length"]) if r["total_length"] else None,
                )
                for r in csv.DictReader(stream)
            }
    if set(paper) != domain:
        raise ValueError("The paper-method comparison requires the complete domain")
    failed = 0
    for row in rows:
        reference = paper[row["N"], row["M"]]
        if reference["d"] != row["d"]:
            raise ValueError("Cannot compare different pitches")
        if row["total_length"] != row["lower_bound"]:
            raise ValueError("An uncertified final result cannot be colored optimal")
        for i, length in enumerate((reference["total_length"], row["total_length"])):
            if i == 0 and not reference["verified"]:
                grids[i][row["N"] - 1, row["M"] - 1] = 3
                failed += 1
                continue
            optimal = length == row["lower_bound"]
            if length < row["lower_bound"]:
                raise ValueError("A recorded length is below its lower bound")
            grids[i][row["N"] - 1, row["M"] - 1] = 2 if optimal else 1
            counts[i] += optimal
    colors = ["#e9edeb", "#bd6d62", "#70bda8", "#edcb8b"]
    fig, axes = plt.subplots(1, 2, figsize=(14, 8))
    fig.patch.set_facecolor("#fafbf9")
    fig.subplots_adjust(left=0.07, right=0.98, bottom=0.16, top=0.78, wspace=0.18)
    for i, ax in enumerate(axes):
        ax.imshow(
            grids[i],
            origin="lower",
            extent=(0.5, 80.5, 0.5, 400.5),
            aspect="auto",
            interpolation="nearest",
            cmap=ListedColormap(colors),
            vmin=0,
            vmax=3,
        )
        title = ("Paper-method reconstruction", "Improved geometric replay")[i]
        ax.set(
            title=f"{title}\n{counts[i]:,} / {len(rows):,} optimal ({100 * counts[i] / len(rows):.2f}%)",
            xlabel="M (short side)",
            ylabel="N (long side)",
            xticks=[1, 20, 40, 60, 80],
            yticks=[1, 100, 200, 300, 400],
        )
        ax.tick_params(length=0, pad=7)
        for spine in ax.spines.values():
            spine.set_color("#aebcb7")
    fig.text(
        0.07, 0.93, "is_optimal(N, M): every integer pair", size=24, color="#173c36"
    )
    fig.text(
        0.07,
        0.875,
        "1 <= N <= 400, 1 <= M <= floor(N/5). Fixed pitch per case; no runtime residual search.",
        size=12,
        color="#586b66",
    )
    fig.legend(
        handles=[
            Patch(facecolor=colors[2], label="Proved optimal"),
            Patch(facecolor=colors[1], label="Proved nonoptimal"),
            Patch(facecolor=colors[3], label="No verified routing"),
            Patch(facecolor=colors[0], label="Outside this benchmark"),
        ],
        ncol=4,
        frameon=False,
        loc="lower center",
        bbox_to_anchor=(0.5, 0.035),
    )
    target = ROOT / "assets"
    target.mkdir(exist_ok=True)
    for extension in ("png", "svg"):
        output = target / f"optimality.{extension}"
        fig.savefig(
            output,
            dpi=160,
            facecolor=fig.get_facecolor(),
            metadata={"Date": None} if extension == "svg" else None,
        )
        if extension == "svg":
            output.write_text(
                "\n".join(line.rstrip() for line in output.read_text().splitlines())
                + "\n"
            )
    plt.close(fig)
    print(
        json.dumps(
            dict(
                cases=len(rows),
                paper_method_optimal=counts[0],
                paper_method_failed=failed,
                geometric_optimal=counts[1],
            )
        )
    )


if __name__ == "__main__":
    main()
