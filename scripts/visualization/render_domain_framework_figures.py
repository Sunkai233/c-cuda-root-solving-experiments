#!/usr/bin/env python3
"""Render four data-driven 2-D application figures for the non-BEM domains."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import BoundaryNorm, LogNorm
from matplotlib.patches import Arc, Circle, FancyArrowPatch, Polygon, Rectangle


ROOT = Path(__file__).resolve().parents[2]
OUT_DEFAULT = ROOT / "paper_figures" / "domain_frameworks_v1"


COLORS = {
    "blue": "#2166ac",
    "cyan": "#2a9d8f",
    "orange": "#d97706",
    "red": "#b2182b",
    "purple": "#6a51a3",
    "gray": "#5b6573",
    "light": "#edf2f7",
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def set_paper_style() -> None:
    mpl.rcParams.update(
        {
            "font.family": "serif",
            "font.serif": ["Times New Roman", "DejaVu Serif"],
            "mathtext.fontset": "stix",
            "axes.linewidth": 0.8,
            "axes.labelsize": 9,
            "axes.titlesize": 10,
            "xtick.labelsize": 7.5,
            "ytick.labelsize": 7.5,
            "legend.fontsize": 7.2,
            "savefig.dpi": 400,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "axes.spines.top": False,
            "axes.spines.right": False,
        }
    )


def panel(ax, label: str, title: str) -> None:
    ax.text(-0.11, 1.06, label, transform=ax.transAxes, fontsize=11, fontweight="bold",
            va="bottom", ha="left", clip_on=False)
    ax.set_title(title, loc="left", pad=8)


def style_axis(ax, grid: bool = True) -> None:
    if grid:
        ax.grid(True, color="#d7dde5", lw=0.45, alpha=0.75)
    ax.tick_params(direction="out", length=3, width=0.7)


def audit_layout(fig, named_axes: dict[str, object]) -> dict:
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    boxes = {}
    outside = []
    for name, artist in named_axes.items():
        bb = artist.get_tightbbox(renderer).transformed(fig.transFigure.inverted())
        boxes[name] = [float(bb.x0), float(bb.y0), float(bb.x1), float(bb.y1)]
        if bb.x0 < -0.01 or bb.y0 < -0.01 or bb.x1 > 1.01 or bb.y1 > 1.01:
            outside.append(name)
    overlaps = []
    names = list(boxes)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            aa, bb = boxes[a], boxes[b]
            w = max(0.0, min(aa[2], bb[2]) - max(aa[0], bb[0]))
            h = max(0.0, min(aa[3], bb[3]) - max(aa[1], bb[1]))
            if w * h > 1e-5:
                overlaps.append({"elements": [a, b], "normalized_area": float(w * h)})
    return {"tight_bboxes_xyxy": boxes, "pairwise_overlaps": overlaps, "outside_figure": outside}


def save_figure(fig, out: Path, stem: str, axes: dict[str, object]) -> dict:
    paths = []
    for ext in ("png", "pdf", "svg"):
        path = out / f"{stem}.{ext}"
        fig.savefig(path, bbox_inches="tight", facecolor="white")
        paths.append(path)
    audit = audit_layout(fig, axes)
    plt.close(fig)
    return {
        "files": [{"name": p.name, "sha256": sha256(p), "bytes": p.stat().st_size} for p in paths],
        "layout_audit": audit,
    }


def pivot_grid(df: pd.DataFrame, row: str, col: str, value: str):
    p = df.pivot(index=row, columns=col, values=value).sort_index().sort_index(axis=1)
    return p.columns.to_numpy(float), p.index.to_numpy(float), p.to_numpy(float)


def arrow(ax, start, end, color="#273444", lw=1.2, ms=10, zorder=6):
    ax.add_patch(FancyArrowPatch(start, end, arrowstyle="-|>", mutation_scale=ms,
                                 color=color, linewidth=lw, zorder=zorder))


def render_geometry_plate(out: Path, meta: dict) -> None:
    """A data-coupled structural plate that explains where each root batch lives."""
    kepler = pd.read_csv(out / "data" / "kepler_orekit_grid.csv", float_precision="round_trip")
    pv = pd.read_csv(out / "data" / "pvlib_cec_operating_surface.csv")
    cstr = pd.read_csv(out / "data" / "cantera_cstr_hot_branch_surface.csv")
    pr = pd.read_csv(out / "data" / "coolprop_pr_root_map.csv")

    fig, axs = plt.subplots(2, 2, figsize=(15.2, 9.2), layout="constrained")
    ax0, ax1, ax2, ax3 = axs.ravel()

    # Kepler: actual solved ellipse, perifocal frame and anomaly construction.
    panel(ax0, "a", "Kepler propagation: one root at every orbital state")
    e = 0.72
    sub = kepler.iloc[(kepler["e"] - e).abs().argsort()[:180]].sort_values("M_rad")
    x = sub.x_over_a.to_numpy(); y = sub.y_over_a.to_numpy()
    ax0.plot(x, y, color=COLORS["blue"], lw=2.0)
    ax0.plot(x, -y, color=COLORS["blue"], lw=2.0)
    ids = np.linspace(0, len(sub) - 1, 24).astype(int)
    ax0.scatter(x[ids], y[ids], s=15, color="white", edgecolor=COLORS["blue"], lw=0.75,
                zorder=5, label="batched propagation states")
    ax0.add_patch(Circle((0, 0), 0.055, fc="#3b82c4", ec="#153b5b", lw=0.8, zorder=7))
    ax0.add_patch(Circle((-e, 0), 0.028, fc=COLORS["orange"], ec="white", lw=0.7, zorder=7))
    k = 54
    px, py = x[k], y[k]
    ax0.plot([0, px], [0, py], color=COLORS["red"], lw=1.45)
    ax0.plot([0, px], [0, 0], color=COLORS["gray"], lw=0.8, ls="--")
    ax0.plot([px, px], [0, py], color=COLORS["gray"], lw=0.8, ls="--")
    ax0.scatter([px], [py], s=30, fc=COLORS["red"], ec="white", lw=0.7, zorder=8)
    arrow(ax0, (px, py), (px - 0.34, py + 0.16), COLORS["cyan"], 1.3, 9)
    ax0.add_patch(Arc((0, 0), 0.75, 0.75, theta1=0, theta2=np.degrees(np.arctan2(py, px)),
                      color=COLORS["red"], lw=1.0))
    ax0.text(0.24, 0.08, "$E$", color=COLORS["red"], fontsize=9)
    ax0.annotate("central focus", (0, 0), (0.10, -0.25), fontsize=7.4,
                 arrowprops={"arrowstyle": "->", "lw": 0.7})
    ax0.annotate("empty focus", (-e, 0), (-1.08, -0.28), fontsize=7.4,
                 arrowprops={"arrowstyle": "->", "lw": 0.7})
    ax0.annotate("state $(x,y)$\nsolve $E-e\\sin E=M$", (px, py), (0.38, 0.74), fontsize=7.6,
                 arrowprops={"arrowstyle": "->", "lw": 0.75})
    ax0.text(-1.72, 0.91, "24 shown / 3,000 frozen cases", fontsize=7.4,
             bbox={"fc": "white", "ec": "#9aa3ad", "lw": 0.6, "pad": 2.5})
    ax0.set_aspect("equal"); ax0.set_xlim(-1.86, 1.05); ax0.set_ylim(-1.05, 1.05)
    ax0.set_xlabel("perifocal coordinate $x/a$"); ax0.set_ylabel("perifocal coordinate $y/a$")
    ax0.legend(frameon=False, loc="lower right"); style_axis(ax0)

    # PV: module geometry and the exact one-diode electrical structure.
    panel(ax1, "b", "PV module: cell lattice, environmental batch and one-diode solve")
    module = Rectangle((0.04, 0.13), 0.43, 0.73, fc="#102a43", ec="#0b1f33", lw=1.3)
    ax1.add_patch(module)
    rows, cols = 12, 8
    for rr in range(rows):
        for cc in range(cols):
            xx = 0.055 + cc * 0.049; yy = 0.145 + rr * 0.0578
            ax1.add_patch(Rectangle((xx, yy), 0.044, 0.052, fc="#2369a8", ec="#b9d7ee", lw=0.32))
            ax1.plot([xx + 0.022, xx + 0.022], [yy + 0.004, yy + 0.048], color="#83b7dc", lw=0.22)
    ax1.add_patch(Rectangle((0.19, 0.085), 0.13, 0.042, fc="#303840", ec="black", lw=0.7))
    for xx in (0.225, 0.285):
        ax1.plot([xx, xx], [0.085, 0.04], color="#303840", lw=1.2)
    # Incoming irradiance and thermal boundary.
    for xx in np.linspace(0.09, 0.43, 5):
        arrow(ax1, (xx - 0.06, 0.98), (xx, 0.88), COLORS["orange"], 1.0, 8)
    ax1.text(0.055, 0.965, "$G=100$–$1100$ W m$^{-2}$", fontsize=7.5, color=COLORS["orange"])
    ax1.annotate("96 series-connected cells", (0.26, 0.50), (0.49, 0.72), fontsize=7.4,
                 arrowprops={"arrowstyle": "->", "lw": 0.7})
    ax1.annotate("junction box / terminals", (0.255, 0.105), (0.47, 0.08), fontsize=7.2,
                 arrowprops={"arrowstyle": "->", "lw": 0.7})
    # One-diode equivalent circuit, tied directly to the module terminals.
    x0, y0 = 0.58, 0.50
    ax1.plot([x0, 0.95], [y0 + 0.20, y0 + 0.20], color="#273444", lw=1.2)
    ax1.plot([x0, 0.95], [y0 - 0.20, y0 - 0.20], color="#273444", lw=1.2)
    ax1.add_patch(Circle((x0 + 0.05, y0), 0.065, fc="white", ec="#273444", lw=1.0))
    arrow(ax1, (x0 + 0.05, y0 - 0.035), (x0 + 0.05, y0 + 0.04), COLORS["blue"], 1.0, 8)
    ax1.plot([x0 + 0.05, x0 + 0.05], [y0 + 0.065, y0 + 0.20], color="#273444", lw=1.0)
    ax1.plot([x0 + 0.05, x0 + 0.05], [y0 - 0.065, y0 - 0.20], color="#273444", lw=1.0)
    # Diode branch.
    dx = x0 + 0.17
    ax1.plot([dx, dx], [y0 + 0.20, y0 + 0.05], color="#273444", lw=1.0)
    ax1.add_patch(Polygon([[dx - 0.035, y0 + 0.05], [dx + 0.035, y0 + 0.05], [dx, y0 - 0.03]],
                          closed=True, fc="white", ec="#273444", lw=0.9))
    ax1.plot([dx - 0.04, dx + 0.04], [y0 - 0.045, y0 - 0.045], color="#273444", lw=1.0)
    ax1.plot([dx, dx], [y0 - 0.045, y0 - 0.20], color="#273444", lw=1.0)
    # Shunt and series resistors.
    rx = x0 + 0.27
    ax1.plot([rx, rx], [y0 + 0.20, y0 + 0.12], color="#273444", lw=1.0)
    zigy = np.linspace(y0 + 0.12, y0 - 0.12, 9)
    zigx = rx + 0.018 * np.array([0, 1, -1, 1, -1, 1, -1, 1, 0])
    ax1.plot(zigx, zigy, color="#273444", lw=1.0)
    ax1.plot([rx, rx], [y0 - 0.12, y0 - 0.20], color="#273444", lw=1.0)
    sx = np.linspace(x0 + 0.30, 0.90, 9)
    sy = y0 + 0.20 + 0.018 * np.array([0, 1, -1, 1, -1, 1, -1, 1, 0])
    ax1.plot(sx, sy, color="#273444", lw=1.0)
    ax1.plot([0.90, 0.95], [y0 + 0.20, y0 + 0.20], color="#273444", lw=1.0)
    ax1.text(x0 + 0.01, y0 - 0.10, "$I_L$", fontsize=7.2)
    ax1.text(dx - 0.018, y0 + 0.10, "$I_D$", fontsize=7.2)
    ax1.text(rx + 0.018, y0, "$R_{sh}$", fontsize=7.2)
    ax1.text(0.78, y0 + 0.24, "$R_s$", fontsize=7.2)
    ax1.text(0.69, 0.15, "357 $(G,T_c)$ states\nroot: terminal current $I(V)$", fontsize=7.7,
             ha="center", bbox={"fc": "white", "ec": "#9aa3ad", "lw": 0.6, "pad": 2.5})
    ax1.text(0.965, y0 + 0.20, "+", fontsize=9, ha="left", va="center")
    ax1.text(0.965, y0 - 0.20, "−", fontsize=9, ha="left", va="center")
    ax1.set_xlim(0, 1); ax1.set_ylim(0, 1); ax1.set_aspect("equal"); ax1.axis("off")

    # CSTR: dimensioned vessel, jacket, mixing and residence-time batch.
    panel(ax2, "c", "CSTR: well-stirred reactor geometry and coupled thermal balance")
    ax2.add_patch(Rectangle((0.22, 0.16), 0.42, 0.63, fc="#eef5f7", ec="#2d4858", lw=1.5))
    ax2.add_patch(Rectangle((0.18, 0.12), 0.50, 0.71, fc="none", ec=COLORS["cyan"], lw=2.0))
    ax2.add_patch(Rectangle((0.22, 0.16), 0.42, 0.42, fc="#f4b183", ec="none", alpha=0.72))
    ax2.plot([0.22, 0.64], [0.58, 0.58], color="#2d4858", lw=0.8)
    ax2.plot([0.43, 0.43], [0.92, 0.30], color="#2d4858", lw=1.8)
    ax2.add_patch(Rectangle((0.31, 0.29), 0.24, 0.025, angle=0, fc="#657786", ec="#2d4858", lw=0.7))
    ax2.add_patch(Rectangle((0.34, 0.43), 0.18, 0.022, fc="#657786", ec="#2d4858", lw=0.7))
    ax2.add_patch(Circle((0.43, 0.92), 0.045, fc="#657786", ec="#2d4858", lw=0.8))
    arrow(ax2, (0.04, 0.69), (0.22, 0.69), COLORS["blue"], 1.5, 10)
    arrow(ax2, (0.64, 0.33), (0.82, 0.33), COLORS["red"], 1.5, 10)
    arrow(ax2, (0.18, 0.18), (0.18, 0.73), COLORS["cyan"], 1.2, 9)
    arrow(ax2, (0.68, 0.74), (0.68, 0.19), COLORS["cyan"], 1.2, 9)
    for cy in (0.36, 0.49):
        ax2.add_patch(Arc((0.43, cy), 0.25, 0.17, theta1=20, theta2=330,
                          color="white", lw=1.25))
        arrow(ax2, (0.51, cy + 0.065), (0.54, cy + 0.015), "white", 1.0, 7)
    ax2.text(0.035, 0.74, "$T_{in}$, $\\dot m$, composition", fontsize=7.6, color=COLORS["blue"])
    ax2.text(0.69, 0.28, "$T$, species", fontsize=7.6, color=COLORS["red"])
    ax2.text(0.14, 0.47, "cooling\njacket", fontsize=7.2, ha="right", color=COLORS["cyan"])
    ax2.text(0.43, 0.20, "perfectly mixed control volume $V$", fontsize=7.2, ha="center")
    ax2.annotate("impeller", (0.53, 0.44), (0.76, 0.57), fontsize=7.4,
                 arrowprops={"arrowstyle": "->", "lw": 0.7})
    ax2.text(0.75, 0.79, "$\\tau=V/\\dot V$", fontsize=9)
    ax2.text(0.73, 0.67, "21 $T_{in}$ × 72 $\\tau$\n= 1,512 steady solves", fontsize=7.7,
             bbox={"fc": "white", "ec": "#9aa3ad", "lw": 0.6, "pad": 2.5})
    ax2.text(0.74, 0.45, "root state:\n$T$, $Y_k$, $\\dot q$", fontsize=7.7)
    ax2.set_xlim(0, 1); ax2.set_ylim(0, 1); ax2.set_aspect("equal"); ax2.axis("off")

    # Peng-Robinson: physical control volume and three algebraic volume roots.
    panel(ax3, "d", "Peng–Robinson fluid cell: phase geometry behind the cubic roots")
    ax3.add_patch(Rectangle((0.09, 0.12), 0.38, 0.70, fc="white", ec="#273444", lw=1.5))
    ax3.add_patch(Rectangle((0.07, 0.77), 0.42, 0.07, fc="#657786", ec="#273444", lw=1.0))
    ax3.plot([0.28, 0.28], [0.84, 0.95], color="#273444", lw=2.0)
    arrow(ax3, (0.28, 0.97), (0.28, 0.86), COLORS["red"], 1.4, 10)
    ax3.add_patch(Rectangle((0.09, 0.12), 0.38, 0.31, fc="#5aa9e6", ec="none", alpha=0.78))
    ax3.plot([0.09, 0.47], [0.43, 0.43], color="#1c6ba0", lw=1.1)
    rng = np.random.default_rng(7)
    for xx, yy in zip(rng.uniform(0.115, 0.445, 58), rng.uniform(0.145, 0.405, 58)):
        ax3.add_patch(Circle((xx, yy), 0.008, fc="#0b5f9a", ec="white", lw=0.25))
    for xx, yy in zip(rng.uniform(0.12, 0.44, 20), rng.uniform(0.47, 0.74, 20)):
        ax3.add_patch(Circle((xx, yy), 0.008, fc=COLORS["orange"], ec="white", lw=0.25))
    ax3.text(0.285, 0.28, "dense liquid", fontsize=7.5, color="white", ha="center")
    ax3.text(0.285, 0.60, "dilute vapor", fontsize=7.5, ha="center")
    ax3.text(0.13, 0.89, "piston pressure $P$", fontsize=7.5)
    ax3.annotate("phase interface", (0.43, 0.43), (0.50, 0.50), fontsize=7.3,
                 arrowprops={"arrowstyle": "->", "lw": 0.7})
    # Root structure at the same T,P state.
    bx = [0.61, 0.75, 0.89]
    heights = [0.22, 0.43, 0.72]
    labels = ["liquid root\n$Z_L$", "unstable root\n$Z_U$", "vapor root\n$Z_V$"]
    colors = [COLORS["blue"], COLORS["gray"], COLORS["red"]]
    for xx, hh, label, color in zip(bx, heights, labels, colors):
        ax3.add_patch(Rectangle((xx - 0.045, 0.15), 0.09, hh, fc=color, ec="white", lw=0.7, alpha=0.88))
        ax3.text(xx, 0.11, label, fontsize=7.0, ha="center", va="top")
    ax3.plot([0.55, 0.96], [0.15, 0.15], color="#273444", lw=0.8)
    ax3.text(0.755, 0.91, "same $(P_r,T_r)$ → cubic in $Z$", fontsize=8.2, ha="center")
    ax3.text(0.755, 0.82, f"{pr.shape[0]:,} batched phase states", fontsize=7.5, ha="center",
             bbox={"fc": "white", "ec": "#9aa3ad", "lw": 0.6, "pad": 2.5})
    ax3.text(0.755, 0.72, "one root outside dome\nthree roots inside dome", fontsize=7.4, ha="center")
    ax3.set_xlim(0, 1); ax3.set_ylim(0, 1); ax3.set_aspect("equal"); ax3.axis("off")

    meta["geometry_structures"] = save_figure(
        fig, out, "fig8_multidomain_geometry_structures_2d",
        {"kepler_geometry": ax0, "pv_structure": ax1, "cstr_structure": ax2, "pr_structure": ax3},
    )


def render_kepler(out: Path, meta: dict) -> None:
    data = pd.read_csv(out / "data" / "kepler_orekit_grid.csv", float_precision="round_trip")
    check = pd.read_csv(out / "data" / "kepler_orekit_reference_check.csv", float_precision="round_trip")
    egrid, mgrid, E = pivot_grid(data, "M_rad", "e", "E_rad")
    _, _, condition = pivot_grid(data, "M_rad", "e", "condition_dE_dM")

    fig, axs = plt.subplots(2, 2, figsize=(14.8, 8.5), layout="constrained")
    ax0, ax1, ax2, ax3 = axs.ravel()

    panel(ax0, "a", "Orekit-propagated elliptic orbit family")
    cmap = mpl.colormaps["viridis"]
    for j, e in enumerate((0.0, 0.6, 0.9, 0.99)):
        sub = data.iloc[(data["e"] - e).abs().argsort()[:180]].sort_values("M_rad")
        # The benchmark exploits Kepler symmetry and stores M in [0, pi].
        # Reflecting the same solved samples draws the complete physical orbit.
        ax0.plot(sub.x_over_a, sub.y_over_a, lw=1.6, color=cmap(j / 3), label=fr"$e={e:g}$")
        ax0.plot(sub.x_over_a, -sub.y_over_a, lw=1.6, color=cmap(j / 3))
        ids = np.linspace(0, len(sub) - 1, 13).astype(int)
        ax0.scatter(sub.x_over_a.iloc[ids], sub.y_over_a.iloc[ids], s=12, color=cmap(j / 3),
                    edgecolor="white", linewidth=0.3, zorder=3)
        ax0.plot(-e, 0, marker="+", ms=7, mew=1.2, color=cmap(j / 3))
    earth = Circle((0, 0), 0.055, color="#3b82c4", ec="#153b5b", lw=0.6, zorder=5)
    ax0.add_patch(earth)
    ax0.annotate("focus", (0, 0), (0.12, -0.18), arrowprops={"arrowstyle": "->", "lw": 0.7}, fontsize=7.5)
    ax0.set_aspect("equal", adjustable="box")
    ax0.set_xlabel(r"$x/a=\cos E-e$")
    ax0.set_ylabel(r"$y/a=\sqrt{1-e^2}\sin E$")
    ax0.set_xlim(-2.08, 1.1)
    ax0.set_ylim(-1.12, 1.12)
    ax0.legend(loc="upper left", frameon=False, ncol=2)
    style_axis(ax0)

    panel(ax1, "b", "Eccentric anomaly over the batched input plane")
    im1 = ax1.pcolormesh(mgrid, egrid, E.T, shading="auto", cmap="viridis", rasterized=True)
    levels_e = [0.25, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0]
    ce = ax1.contour(mgrid, egrid, E.T, levels=levels_e, colors="white", linewidths=0.55, alpha=0.9)
    ax1.clabel(ce, inline=True, fontsize=6.2, fmt=lambda x: f"E={x:g}")
    # Show the actual two-dimensional sampling lattice without turning the
    # panel into a decorative gradient.
    ax1.scatter(mgrid[::12], np.full_like(mgrid[::12], 0.985), s=7, marker="|",
                color="white", alpha=0.9, linewidths=0.7)
    ax1.axhline(0.9, color="white", ls="--", lw=0.75, alpha=0.8)
    ax1.text(0.04, 0.88, "high-e band", color="white", fontsize=7.2,
             transform=ax1.transAxes, ha="left", va="top")
    c1 = fig.colorbar(im1, ax=ax1, pad=0.02, aspect=28)
    c1.set_label(r"$E$ [rad]")
    ax1.set_xlabel(r"mean anomaly $M$ [rad]")
    ax1.set_ylabel(r"eccentricity $e$")
    ax1.set_ylim(0, 1.0)
    style_axis(ax1, False)

    panel(ax2, "c", "Sensitivity resolved across the near-parabolic corner")
    positive_m = mgrid > 0
    im2 = ax2.pcolormesh(mgrid[positive_m], egrid, np.log10(condition.T[:, positive_m]), shading="auto", cmap="magma",
                         vmin=0, vmax=9, rasterized=True)
    logcond = np.log10(condition.T[:, positive_m])
    cc = ax2.contour(mgrid[positive_m], egrid, logcond, levels=[1, 3, 5, 7],
                     colors="white", linewidths=0.65, alpha=0.9)
    ax2.clabel(cc, inline=True, fontsize=6.2, fmt=lambda x: fr"$10^{{{int(x)}}}$")
    ax2.plot([1e-8], [0.9999999], marker="o", ms=4.5, mfc="none", mec="cyan", mew=1.0)
    ax2.annotate("hard-corner sampling", xy=(1e-8, 0.9999999), xytext=(3e-7, 0.99999998),
                 color="white", fontsize=7.0,
                 arrowprops={"arrowstyle": "->", "color": "white", "lw": 0.7})
    c2 = fig.colorbar(im2, ax=ax2, pad=0.02, aspect=28)
    c2.set_label(r"$\log_{10}|\partial E/\partial M|$")
    ax2.set_xlabel(r"mean anomaly $M$ [rad]")
    ax2.set_ylabel(r"eccentricity $e$")
    ax2.set_ylim(0.90, 1.0001)
    ax2.set_xscale("log")
    ax2.set_xlim(1e-10, 1e-1)
    ax2.set_yscale("function", functions=(lambda y: -np.log10(np.clip(1-y, 1e-10, None)),
                                           lambda y: 1-10**(-y)))
    ax2.set_yticks([0.9, 0.99, 0.9999, 0.999999, 0.99999999])
    ax2.set_yticklabels(["0.9", "0.99", "0.9999", "0.999999", "0.99999999"])
    style_axis(ax2, False)

    panel(ax3, "d", "Production-library agreement across all 3,000 frozen cases")
    branch_order = ["ordinary", "high_e", "difficult"]
    labels = ["ordinary", "high eccentricity", "difficult corner"]
    for k, (branch, label) in enumerate(zip(branch_order, labels)):
        v = check.loc[check.branch == branch, "absolute_error"].to_numpy()
        v = np.maximum(v, 1e-18)
        ax3.scatter(np.full_like(v, k) + np.linspace(-0.18, 0.18, len(v)), v, s=4.5, alpha=0.32,
                    color=[COLORS["blue"], COLORS["cyan"], COLORS["red"]][k], rasterized=True)
        ax3.boxplot(v, positions=[k], widths=0.34, showfliers=False, patch_artist=True,
                    boxprops={"facecolor": "white", "edgecolor": COLORS["gray"], "linewidth": 0.9},
                    medianprops={"color": "black", "linewidth": 1.1},
                    whiskerprops={"color": COLORS["gray"]}, capprops={"color": COLORS["gray"]})
    ax3.set_yscale("log")
    ax3.set_xticks(range(3), labels)
    ax3.set_ylabel("|Orekit E - 80-digit reference| [rad]")
    ax3.axhline(np.finfo(float).eps, color=COLORS["orange"], ls="--", lw=0.9, label="binary64 epsilon")
    ax3.legend(frameon=False, loc="upper left")
    style_axis(ax3)
    meta["kepler"] = save_figure(fig, out, "fig4_kepler_orekit_batch_2d",
                                  {"orbit": ax0, "root_surface": ax1, "condition": ax2, "agreement": ax3})


def render_pv(out: Path, meta: dict) -> None:
    surface = pd.read_csv(out / "data" / "pvlib_cec_operating_surface.csv")
    curves = pd.read_csv(out / "data" / "pvlib_cec_iv_curves.csv")
    frozen = pd.read_csv(ROOT / "references" / "pv_extended_ref_v1_20260824" / "pv_extended.csv",
                         float_precision="round_trip")
    check = pd.read_csv(out / "data" / "pvlib_benchmark_reference_check.csv", float_precision="round_trip")
    G, T, pmp = pivot_grid(surface, "cell_temperature_C", "effective_irradiance_W_m2", "p_mp")

    fig, axs = plt.subplots(2, 2, figsize=(14.8, 8.5), layout="constrained")
    ax0, ax1, ax2, ax3 = axs.ravel()
    panel(ax0, "a", "CEC module I-V and P-V curves from pvlib")
    for (g, t), grp in curves.groupby(["effective_irradiance_W_m2", "cell_temperature_C"]):
        color = mpl.colormaps["plasma"]((g - 200) / 800)
        ls = "-" if t == 10 else "--"
        label = fr"{g:.0f} W m$^{{-2}}$, {t:.0f}$^\circ$C"
        ax0.plot(grp.V, grp.I, color=color, ls=ls, lw=1.35, label=label)
    ax0.set_xlabel("module voltage [V]")
    ax0.set_ylabel("module current [A]")
    ax0.legend(frameon=False, ncol=2, loc="lower left")
    style_axis(ax0)
    power_ax = ax0.twinx()
    ref = curves[(curves.effective_irradiance_W_m2 == 1000) & (curves.cell_temperature_C == 10)]
    power_ax.plot(ref.V, ref.P, color=COLORS["red"], lw=1.0, alpha=0.9)
    power_ax.set_ylabel("power at 1000 W m$^{-2}$ [W]", color=COLORS["red"])
    power_ax.tick_params(axis="y", colors=COLORS["red"])
    power_ax.spines["right"].set_visible(True)

    panel(ax1, "b", "Maximum-power surface: 357 independent operating points")
    im = ax1.pcolormesh(T, G, pmp.T, shading="auto", cmap="inferno", rasterized=True)
    cs = ax1.contour(T, G, pmp.T, levels=[50, 100, 150, 200, 250], colors="white", linewidths=0.55)
    ax1.clabel(cs, inline=True, fontsize=6.5, fmt="%g W")
    tt, gg = np.meshgrid(T, G)
    ax1.scatter(tt.ravel(), gg.ravel(), s=5, marker="o", facecolors="none",
                edgecolors="white", linewidths=0.28, alpha=0.65, rasterized=True)
    stc = surface.iloc[((surface.cell_temperature_C - 25).abs()
                        + (surface.effective_irradiance_W_m2 - 1000).abs() / 50).argmin()]
    ax1.plot(stc.cell_temperature_C, stc.effective_irradiance_W_m2, marker="*", ms=8,
             color="cyan", mec="black", mew=0.35, zorder=4)
    ax1.annotate(f"near STC\n{stc.p_mp:.1f} W",
                 (stc.cell_temperature_C, stc.effective_irradiance_W_m2), (43, 1045),
                 color="white", fontsize=7.0, ha="left",
                 arrowprops={"arrowstyle": "->", "color": "white", "lw": 0.7})
    cb = fig.colorbar(im, ax=ax1, pad=0.02, aspect=28)
    cb.set_label(r"$P_{mp}$ [W]")
    ax1.set_xlabel(r"cell temperature [$^\circ$C]")
    ax1.set_ylabel("effective irradiance [W m$^{-2}$]")
    style_axis(ax1, False)

    panel(ax2, "c", "Frozen benchmark coverage in normalized electrical coordinates")
    region_colors = {"short_circuit": COLORS["blue"], "open_circuit": COLORS["red"],
                     "mpp_near": COLORS["orange"], "interior": COLORS["cyan"]}
    for region, grp in frozen.groupby("region"):
        ax2.scatter(grp.V / grp.Voc, grp.I / grp.IL, s=7, alpha=0.48, color=region_colors[region],
                    label=region.replace("_", " "), rasterized=True)
    ax2.set_xlabel(r"normalized voltage $V/V_{oc}$")
    ax2.set_ylabel(r"normalized current $I/I_L$")
    ax2.set_xlim(-0.02, 1.02)
    ax2.set_ylim(-0.03, 1.03)
    ax2.legend(frameon=False, ncol=2, loc="lower left")
    style_axis(ax2)

    panel(ax3, "d", "Independent pvlib Brent check against the 70-digit oracle")
    values = [np.maximum(check.loc[check.region == r, "absolute_error"], 1e-16) for r in region_colors]
    vp = ax3.violinplot(values, positions=np.arange(4), showmeans=False, showextrema=False, widths=0.72)
    for body, color in zip(vp["bodies"], region_colors.values()):
        body.set_facecolor(color)
        body.set_edgecolor("none")
        body.set_alpha(0.65)
    for i, vals in enumerate(values):
        ax3.scatter(i, np.median(vals), marker="D", s=24, color="black", zorder=3)
    ax3.set_yscale("log")
    ax3.set_xticks(range(4), [r.replace("_", "\n") for r in region_colors])
    ax3.set_ylabel("|pvlib current - 70-digit current| [A]")
    ax3.text(0.02, 0.97, f"max = {check.absolute_error.max():.2e} A",
             transform=ax3.transAxes, va="top", ha="left", fontsize=7.5)
    style_axis(ax3)
    meta["pv"] = save_figure(fig, out, "fig5_pvlib_module_batch_2d",
                              {"iv": ax0, "power_surface": ax1, "coverage": ax2, "agreement": ax3})


def render_cstr(out: Path, meta: dict) -> None:
    field = pd.read_csv(out / "data" / "cantera_cstr_hot_branch_surface.csv")
    cont = pd.read_csv(ROOT / "references" / "cstr_fold_ref_v2_20260824" / "cstr_continuation.csv",
                       float_precision="round_trip")
    tau, tin, temp = pivot_grid(field, "inlet_temperature_K", "residence_time_s", "steady_temperature_K")
    _, _, qdot = pivot_grid(field, "inlet_temperature_K", "residence_time_s", "heat_release_rate_W_m3")

    fig, axs = plt.subplots(2, 2, figsize=(14.8, 8.5), layout="constrained")
    ax0, ax1, ax2, ax3 = axs.ravel()
    panel(ax0, "a", "Cantera well-stirred combustor: steady temperature field")
    im0 = ax0.pcolormesh(tau, tin, temp, shading="auto", cmap="inferno", rasterized=True)
    # One strong regime boundary plus two unobtrusive interior contours is more
    # readable than labeling every temperature level along the discontinuity.
    ax0.contour(tau, tin, temp, levels=[1000], colors="cyan", linewidths=1.05)
    ax0.contour(tau, tin, temp, levels=[1400, 1700], colors="white", linewidths=0.55, alpha=0.8)
    # A sparse subset of the solved lattice makes the batch density explicit.
    ttau, ttin = np.meshgrid(tau[::6], tin[::2])
    ax0.scatter(ttau, ttin, s=5, facecolors="none", edgecolors="white",
                linewidths=0.3, alpha=0.6, rasterized=True)
    ax0.text(1.7e-4, 340, "extinguished branch", color="white", fontsize=7.2,
             ha="left", va="bottom")
    ax0.text(1.8e-2, 730, "reacting branch", color="#3b1d00", fontsize=7.2,
             ha="center", va="center")
    ax0.annotate("extinction boundary", xy=(5.3e-4, 455), xytext=(1.6e-4, 535),
                 color="white", fontsize=7.0,
                 arrowprops={"arrowstyle": "->", "color": "white", "lw": 0.7})
    cb0 = fig.colorbar(im0, ax=ax0, pad=0.02, aspect=28)
    cb0.set_label("steady reactor temperature [K]")
    ax0.set_xscale("log")
    ax0.set_xlabel(r"residence time $\tau$ [s]")
    ax0.set_ylabel("inlet temperature [K]")
    style_axis(ax0, False)

    panel(ax1, "b", "Heat-release field reveals the extinction boundary")
    positive = np.maximum(qdot, 1e-2)
    im1 = ax1.pcolormesh(tau, tin, positive, shading="auto", cmap="magma",
                         norm=LogNorm(vmin=1e2, vmax=max(1e6, np.nanmax(positive))), rasterized=True)
    cb1 = fig.colorbar(im1, ax=ax1, pad=0.02, aspect=28)
    cb1.set_label("heat release rate [W m$^{-3}$]")
    ignition = ax1.contour(tau, tin, temp, levels=[1000], colors="cyan", linewidths=1.1)
    ax1.clabel(ignition, inline=True, fontsize=6.5, fmt={1000: "T=1000 K"})
    hlevels = [1e4, 1e6, 1e8]
    hcs = ax1.contour(tau, tin, positive, levels=hlevels, colors="white", linewidths=0.5, alpha=0.8)
    ax1.clabel(hcs, inline=True, fontsize=6.0,
               fmt={1e4: r"$10^4$", 1e6: r"$10^6$", 1e8: r"$10^8$"})
    ax1.scatter(ttau, ttin, s=5, facecolors="none", edgecolors="white",
                linewidths=0.3, alpha=0.55, rasterized=True)
    ax1.text(1.6e-4, 330, "negligible heat release", color="white", fontsize=7.0,
             ha="left", va="bottom")
    ax1.set_xscale("log")
    ax1.set_xlabel(r"residence time $\tau$ [s]")
    ax1.set_ylabel("inlet temperature [K]")
    style_axis(ax1, False)

    panel(ax2, "c", "Hot-branch continuation for selected inlet states")
    for k, target in enumerate((300, 400, 500, 600, 700, 800)):
        grp = field[field.inlet_temperature_K == target].sort_values("residence_time_s")
        ax2.plot(grp.residence_time_s, grp.steady_temperature_K, lw=1.35,
                 color=mpl.colormaps["viridis"](k / 5), label=f"{target} K")
    ax2.set_xscale("log")
    ax2.set_xlabel(r"residence time $\tau$ [s]")
    ax2.set_ylabel("steady reactor temperature [K]")
    ax2.legend(frameon=False, ncol=2, loc="upper left")
    style_axis(ax2)

    panel(ax3, "d", "Exact reduced-model folds require branch history")
    case = cont[cont.history_id.str.startswith("case0_")].copy()
    base = case[case.direction == "cold_up"]
    roots_by_branch = {0: ([], []), 1: ([], []), 2: ([], [])}
    for _, row in base.iterrows():
        roots = [float(x) for x in str(row.roots).split(";")]
        for j, root in enumerate(roots):
            roots_by_branch[j][0].append(row.Da)
            roots_by_branch[j][1].append(root)
    for j, (xs, ys) in roots_by_branch.items():
        if xs:
            ax3.plot(xs, ys, ["-", "--", "-"][j], lw=1.5,
                     color=[COLORS["blue"], COLORS["gray"], COLORS["red"]][j],
                     label=["low root", "middle root", "high root"][j])
    for direction, color, marker in (("cold_up", COLORS["blue"], "o"), ("hot_down", COLORS["red"], "s")):
        grp = case[case.direction == direction].sort_values("Da")
        ax3.scatter(grp.Da, grp.selected_root, s=9, marker=marker, color=color, alpha=0.65,
                    label=direction.replace("_", " "), rasterized=True)
    ax3.set_xscale("log")
    ax3.set_xlabel(r"Damk\"ohler number $Da$")
    ax3.set_ylabel("conversion root $x$")
    ax3.set_ylim(-0.03, 1.03)
    ax3.legend(frameon=False, ncol=2, loc="center right")
    style_axis(ax3)
    meta["cstr"] = save_figure(fig, out, "fig6_cantera_cstr_batch_2d",
                                {"temperature": ax0, "heat_release": ax1, "continuation": ax2, "folds": ax3})


def render_pr(out: Path, meta: dict) -> None:
    root_map = pd.read_csv(out / "data" / "coolprop_pr_root_map.csv")
    isotherms = pd.read_csv(out / "data" / "coolprop_pr_isotherms.csv")
    sat = pd.read_csv(out / "data" / "coolprop_pr_propane_saturation.csv")
    Pr, Tr, counts = pivot_grid(root_map, "Tr", "Pr", "root_count")

    fig, axs = plt.subplots(2, 2, figsize=(14.8, 8.5), layout="constrained")
    ax0, ax1, ax2, ax3 = axs.ravel()
    panel(ax0, "a", "Peng-Robinson propane isotherms")
    for k, (tr, grp) in enumerate(isotherms.groupby("Tr")):
        valid = (grp.P_over_Pc > -0.5) & (grp.P_over_Pc < 3.0)
        ax0.plot(grp.loc[valid, "v_over_b"], grp.loc[valid, "P_over_Pc"], lw=1.35,
                 color=mpl.colormaps["turbo"](k / 4), label=fr"$T_r={tr:.2f}$")
    ax0.axhline(0, color="#9aa3ad", lw=0.6)
    ax0.set_xscale("log")
    ax0.set_ylim(-0.35, 2.4)
    ax0.set_xlabel(r"reduced molar volume $v/b$")
    ax0.set_ylabel(r"reduced pressure $P/P_c$")
    ax0.legend(frameon=False, ncol=2)
    style_axis(ax0)

    panel(ax1, "b", "Cubic root-count map: the batched phase-classification plane")
    cmap = mpl.colors.ListedColormap(["#dbeafe", "#f59e0b"])
    norm = BoundaryNorm([0.5, 2.0, 3.5], cmap.N)
    im = ax1.pcolormesh(Pr, Tr, counts, shading="auto", cmap=cmap, norm=norm, rasterized=True)
    cb = fig.colorbar(im, ax=ax1, pad=0.02, aspect=28, ticks=[1, 3])
    cb.ax.set_yticklabels(["one real root", "three real roots"])
    ax1.plot(sat.P_Pa / 4251200.0, sat.T_K / 369.89, color="black", lw=1.2,
             label="CoolProp PR saturation")
    ax1.scatter([1], [1], marker="*", s=70, color=COLORS["red"], edgecolor="white", linewidth=0.5)
    ax1.set_xlabel(r"reduced pressure $P_r$")
    ax1.set_ylabel(r"reduced temperature $T_r$")
    ax1.legend(frameon=False, loc="lower right")
    style_axis(ax1, False)

    panel(ax2, "c", "Liquid, unstable and vapor Z branches at $T_r=0.90$")
    cut = root_map[np.isclose(root_map.Tr, 0.90)].sort_values("Pr")
    for z, label, color, ls in (("Z0", "liquid", COLORS["blue"], "-"),
                                ("Z1", "unstable", COLORS["gray"], "--"),
                                ("Z2", "vapor", COLORS["red"], "-")):
        ax2.plot(cut.Pr, cut[z], color=color, ls=ls, lw=1.55, label=label)
    ax2.set_xlabel(r"reduced pressure $P_r$")
    ax2.set_ylabel("compressibility root Z")
    ax2.set_ylim(0, 1.15)
    ax2.legend(frameon=False)
    style_axis(ax2)

    panel(ax3, "d", "CoolProp PR saturation dome in density-temperature space")
    ax3.fill_betweenx(sat.T_K, sat.rho_vap_mol_m3, sat.rho_liq_mol_m3,
                      color="#dbeafe", alpha=0.75, label="two-phase region")
    ax3.plot(sat.rho_vap_mol_m3, sat.T_K, color=COLORS["red"], lw=1.5, label="saturated vapor")
    ax3.plot(sat.rho_liq_mol_m3, sat.T_K, color=COLORS["blue"], lw=1.5, label="saturated liquid")
    ax3.set_xscale("log")
    ax3.set_xlabel(r"molar density [mol m$^{-3}$]")
    ax3.set_ylabel("temperature [K]")
    ax3.legend(frameon=False, loc="lower center", ncol=2)
    style_axis(ax3)
    meta["peng_robinson"] = save_figure(fig, out, "fig7_coolprop_peng_robinson_batch_2d",
                                         {"isotherms": ax0, "root_map": ax1, "branches": ax2, "dome": ax3})


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=OUT_DEFAULT)
    args = ap.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    set_paper_style()
    meta = {
        "description": "Four framework-backed, data-driven 2-D publication figures",
        "input_manifests": {
            "orekit": "data/kepler_orekit_manifest.json",
            "pv_cantera_coolprop": "data/framework_experiment_manifest.json",
        },
    }
    render_kepler(out, meta)
    render_pv(out, meta)
    render_cstr(out, meta)
    render_pr(out, meta)
    render_geometry_plate(out, meta)
    manifest = out / "render_manifest.json"
    manifest.write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in meta.items() if k not in ("description", "input_manifests")}, indent=2))


if __name__ == "__main__":
    main()
