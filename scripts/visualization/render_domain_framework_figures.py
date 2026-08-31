#!/usr/bin/env python3
"""Render data-driven 2-D application figures for the non-BEM domains."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
import numpy as np
import pandas as pd
from matplotlib.colors import BoundaryNorm, LogNorm
from matplotlib.patches import Arc, Circle, FancyArrowPatch, Polygon, Rectangle
from mpl_toolkits.axes_grid1.inset_locator import inset_axes


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


def inset_colorbar(fig, ax, mappable, label: str, width: str = "37%"):
    """Compact Nature-style color key embedded in the data field."""
    cax = inset_axes(ax, width=width, height="4.5%", loc="upper right", borderpad=0.7)
    cb = fig.colorbar(mappable, cax=cax, orientation="horizontal")
    cax.xaxis.set_ticks_position("top")
    cax.xaxis.set_label_position("top")
    cax.tick_params(labelsize=6.4, pad=1.0, length=2.0, width=0.55)
    cb.set_label(label, fontsize=7.0, labelpad=1.2)
    return cb


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

    # Near-square panels let the physical objects fill the page instead of
    # leaving the unused side margins produced by equal-aspect geometry.
    fig, axs = plt.subplots(2, 2, figsize=(12.2, 10.4), layout="constrained")
    fig.set_constrained_layout_pads(w_pad=0.025, h_pad=0.025, wspace=0.035, hspace=0.045)
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
    ax0.annotate("central focus", (0, 0), (0.10, -0.25), fontsize=9.0,
                 arrowprops={"arrowstyle": "->", "lw": 0.7})
    ax0.annotate("empty focus", (-e, 0), (-1.08, -0.28), fontsize=9.0,
                 arrowprops={"arrowstyle": "->", "lw": 0.7})
    ax0.annotate("state $(x,y)$\nsolve $E-e\\sin E=M$", (px, py), (0.38, 0.74), fontsize=9.1,
                 arrowprops={"arrowstyle": "->", "lw": 0.75})
    ax0.text(-1.72, 0.91,
             "72 $e$ values  ×  180 $M$ values  ×  1 root/state"
             "\n$\\mathbf{=12,960}$ Kepler solves  +  3,000 oracle checks",
             fontsize=8.5, va="top",
             bbox={"fc": "white", "ec": COLORS["blue"], "lw": 0.8, "pad": 3.0})
    ax0.set_aspect("equal"); ax0.set_xlim(-1.86, 1.05); ax0.set_ylim(-1.05, 1.05)
    ax0.set_xlabel("perifocal coordinate $x/a$"); ax0.set_ylabel("perifocal coordinate $y/a$")
    ax0.legend(frameon=False, loc="lower right", fontsize=8.8); style_axis(ax0)
    ax0.tick_params(labelsize=8.8)
    ax0.xaxis.label.set_size(10.0); ax0.yaxis.label.set_size(10.0)

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
    ax1.text(0.055, 0.965, "$G=100$–$1100$ W m$^{-2}$", fontsize=9.1, color=COLORS["orange"])
    ax1.annotate("96 series-connected cells", (0.26, 0.50), (0.49, 0.72), fontsize=8.8,
                 arrowprops={"arrowstyle": "->", "lw": 0.7})
    ax1.annotate("junction box / terminals", (0.255, 0.105), (0.47, 0.08), fontsize=8.6,
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
    ax1.text(x0 + 0.01, y0 - 0.10, "$I_L$", fontsize=8.7)
    ax1.text(dx - 0.018, y0 + 0.10, "$I_D$", fontsize=8.7)
    ax1.text(rx + 0.018, y0, "$R_{sh}$", fontsize=8.7)
    ax1.text(0.78, y0 + 0.24, "$R_s$", fontsize=8.7)
    ax1.text(0.72, 0.15,
             "21 $G$ levels  ×  17 $T_c$ levels  ×  1 root/state"
             "\n$\\mathbf{=357}$ module-current solves",
             fontsize=8.5, ha="center",
             bbox={"fc": "white", "ec": COLORS["blue"], "lw": 0.8, "pad": 3.0})
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
    ax2.text(0.035, 0.74, "$T_{in}$, $\\dot m$, composition", fontsize=9.0, color=COLORS["blue"])
    ax2.text(0.69, 0.28, "$T$, species", fontsize=9.0, color=COLORS["red"])
    ax2.text(0.14, 0.47, "cooling\njacket", fontsize=8.7, ha="right", color=COLORS["cyan"])
    ax2.text(0.43, 0.20, "perfectly mixed control volume $V$", fontsize=8.5, ha="center")
    ax2.annotate("impeller", (0.53, 0.44), (0.76, 0.57), fontsize=9.0,
                 arrowprops={"arrowstyle": "->", "lw": 0.7})
    ax2.text(0.75, 0.79, "$\\tau=V/\\dot V$", fontsize=10.5)
    ax2.text(0.69, 0.67,
             "21 $T_{in}$ levels  ×  72 $\\tau$ levels  ×  1 steady root/state"
             "\n$\\mathbf{=1,512}$ coupled reactor solves",
             fontsize=8.4,
             bbox={"fc": "white", "ec": COLORS["blue"], "lw": 0.8, "pad": 3.0})
    ax2.text(0.74, 0.45, "root state:\n$T$, $Y_k$, $\\dot q$", fontsize=9.1)
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
    ax3.text(0.285, 0.28, "dense liquid", fontsize=9.0, color="white", ha="center")
    ax3.text(0.285, 0.60, "dilute vapor", fontsize=9.0, ha="center")
    ax3.text(0.13, 0.89, "piston pressure $P$", fontsize=9.0)
    ax3.annotate("phase interface", (0.43, 0.43), (0.50, 0.50), fontsize=8.7,
                 arrowprops={"arrowstyle": "->", "lw": 0.7})
    # Root structure at the same T,P state.
    bx = [0.61, 0.75, 0.89]
    heights = [0.22, 0.43, 0.72]
    labels = ["liquid root\n$Z_L$", "unstable root\n$Z_U$", "vapor root\n$Z_V$"]
    colors = [COLORS["blue"], COLORS["gray"], COLORS["red"]]
    for xx, hh, label, color in zip(bx, heights, labels, colors):
        ax3.add_patch(Rectangle((xx - 0.045, 0.15), 0.09, hh, fc=color, ec="white", lw=0.7, alpha=0.88))
        ax3.text(xx, 0.11, label, fontsize=8.2, ha="center", va="top")
    ax3.plot([0.55, 0.96], [0.15, 0.15], color="#273444", lw=0.8)
    ax3.text(0.755, 0.91, "same $(P_r,T_r)$ → cubic in $Z$", fontsize=9.5, ha="center")
    ax3.text(0.755, 0.82,
             "151 $P_r$ levels  ×  121 $T_r$ levels  ×  1 cubic/state"
             f"\n$\\mathbf{{={pr.shape[0]:,}}}$ phase-root solves",
             fontsize=8.4, ha="center",
             bbox={"fc": "white", "ec": COLORS["blue"], "lw": 0.8, "pad": 3.0})
    ax3.text(0.755, 0.72, "one root outside dome\nthree roots inside dome", fontsize=8.8, ha="center")
    ax3.set_xlim(0, 1); ax3.set_ylim(0, 1); ax3.set_aspect("equal"); ax3.axis("off")

    for ax in axs.ravel():
        ax.title.set_fontsize(11.2)

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
    # Visible sample lattice plus matched orbit slices: the field is both a
    # continuous response and an executed set of individual root problems.
    mm, ee = np.meshgrid(mgrid[::12], egrid[::6])
    ax1.scatter(mm, ee, s=5.0, marker="o", facecolors="none", edgecolors="white",
                alpha=0.48, linewidths=0.30, rasterized=True)
    slice_specs = [(0.60, mpl.colormaps["viridis"](1 / 3), "S1"),
                   (0.90, mpl.colormaps["viridis"](2 / 3), "S2"),
                   (0.99, mpl.colormaps["viridis"](1.0), "S3")]
    for es, color, tag in slice_specs:
        ax1.axhline(es, color=color, ls="--", lw=1.0, alpha=0.95)
        ax1.text(0.56, es - 0.012, f"{tag}  e={es:g}", color="black", fontsize=6.7,
                 ha="right", va="top",
                 bbox={"boxstyle": "round,pad=0.16", "fc": "white", "ec": color,
                       "lw": 0.65, "alpha": 0.88})
    inset_colorbar(fig, ax1, im1, r"eccentric anomaly $E$ [rad]", width="35%")
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
    mms, ees = np.meshgrid(mgrid[positive_m][::14], egrid[::5])
    ax2.scatter(mms, ees, s=3.8, facecolors="none", edgecolors="white",
                linewidths=0.25, alpha=0.34, rasterized=True)
    inset_colorbar(fig, ax2, im2, r"$\log_{10}|\partial E/\partial M|$", width="39%")
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
    pv_cases = [(200, 10), (200, 50), (600, 10), (600, 50), (1000, 10), (1000, 50)]
    pv_tags = {case: chr(ord("A") + i) for i, case in enumerate(pv_cases)}
    for (g, t), grp in curves.groupby(["effective_irradiance_W_m2", "cell_temperature_C"]):
        color = mpl.colormaps["plasma"]((g - 200) / 800)
        ls = "-" if t == 10 else "--"
        tag = pv_tags[(int(g), int(t))]
        label = fr"{tag}: {g:.0f} W m$^{{-2}}$, {t:.0f}$^\circ$C"
        ax0.plot(grp.V, grp.I, color=color, ls=ls, lw=1.35, label=label)
        mpp = grp.iloc[grp.P.argmax()]
        ax0.scatter(mpp.V, mpp.I, marker="o", s=20, facecolor="white",
                    edgecolor=color, linewidth=0.8, zorder=5)
        ax0.text(mpp.V + 0.8, mpp.I + 0.035, tag, fontsize=6.8, color=color,
                 fontweight="bold", zorder=6)
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
                 (stc.cell_temperature_C, stc.effective_irradiance_W_m2), (38, 930),
                 color="white", fontsize=7.0, ha="left",
                 arrowprops={"arrowstyle": "->", "color": "white", "lw": 0.7})
    # Match every highlighted surface state to the labelled I-V/P-V curve in
    # panel (a), as in dense field-plus-station figures.
    for (g, t), tag in pv_tags.items():
        color = mpl.colormaps["plasma"]((g - 200) / 800)
        ax1.scatter(t, g, s=25, marker="o", facecolor="white", edgecolor=color,
                    linewidth=0.9, zorder=6)
        ax1.text(t + 1.4, g + 12, tag, fontsize=6.8, color="black", fontweight="bold",
                 bbox={"boxstyle": "round,pad=0.10", "fc": "white", "ec": color,
                       "lw": 0.6, "alpha": 0.88}, zorder=7)
    inset_colorbar(fig, ax1, im, r"maximum power $P_{mp}$ [W]", width="36%")
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
    # Dense executed nodes and three directly comparable inlet-temperature
    # sections give the field the same measurement-rich grammar as the Nature
    # latitude-depth sections used as the visual reference.
    ttau, ttin = np.meshgrid(tau[::3], tin)
    ax0.scatter(ttau, ttin, s=4.2, facecolors="none", edgecolors="white",
                linewidths=0.25, alpha=0.48, rasterized=True)
    cstr_slices = [(400, COLORS["blue"], "S1"),
                   (600, COLORS["cyan"], "S2"),
                   (800, COLORS["red"], "S3")]
    for tsel, color, tag in cstr_slices:
        ax0.axhline(tsel, color=color, ls="--", lw=0.95, alpha=0.95)
        dy = -8 if tsel == 800 else 6
        ax0.text(1.25e-4, tsel + dy, f"{tag}  {tsel} K", fontsize=6.7, ha="left",
                 va="top" if dy < 0 else "bottom",
                 color="black",
                 bbox={"boxstyle": "round,pad=0.14", "fc": "white", "ec": color,
                       "lw": 0.6, "alpha": 0.88})
    ax0.text(1.7e-4, 340, "extinguished branch", color="white", fontsize=7.2,
             ha="left", va="bottom")
    ax0.text(1.8e-2, 730, "reacting branch", color="#3b1d00", fontsize=7.2,
             ha="center", va="center")
    ax0.annotate("extinction boundary", xy=(5.3e-4, 455), xytext=(1.6e-4, 535),
                 color="white", fontsize=7.0,
                 arrowprops={"arrowstyle": "->", "color": "white", "lw": 0.7})
    inset_colorbar(fig, ax0, im0, "steady reactor temperature [K]", width="39%")
    ax0.set_xscale("log")
    ax0.set_xlabel(r"residence time $\tau$ [s]")
    ax0.set_ylabel("inlet temperature [K]")
    style_axis(ax0, False)

    panel(ax1, "b", "Heat-release field reveals the extinction boundary")
    positive = np.maximum(qdot, 1e-2)
    im1 = ax1.pcolormesh(tau, tin, positive, shading="auto", cmap="magma",
                         norm=LogNorm(vmin=1e2, vmax=max(1e6, np.nanmax(positive))), rasterized=True)
    inset_colorbar(fig, ax1, im1, "heat release rate [W m$^{-3}$]", width="39%")
    ignition = ax1.contour(tau, tin, temp, levels=[1000], colors="cyan", linewidths=1.1)
    ax1.clabel(ignition, inline=True, fontsize=6.5, fmt={1000: "T=1000 K"})
    hlevels = [1e4, 1e6, 1e8]
    hcs = ax1.contour(tau, tin, positive, levels=hlevels, colors="white", linewidths=0.5, alpha=0.8)
    ax1.clabel(hcs, inline=True, fontsize=6.0,
               fmt={1e4: r"$10^4$", 1e6: r"$10^6$", 1e8: r"$10^8$"})
    ax1.scatter(ttau, ttin, s=5, facecolors="none", edgecolors="white",
                linewidths=0.3, alpha=0.55, rasterized=True)
    for tsel, color, tag in cstr_slices:
        ax1.axhline(tsel, color=color, ls="--", lw=0.95, alpha=0.95)
        dy = -8 if tsel == 800 else 6
        ax1.text(1.25e-4, tsel + dy, tag, fontsize=6.7, ha="left", color="black",
                 va="top" if dy < 0 else "bottom",
                 bbox={"boxstyle": "round,pad=0.12", "fc": "white", "ec": color,
                       "lw": 0.6, "alpha": 0.88})
    ax1.text(1.6e-4, 330, "negligible heat release", color="white", fontsize=7.0,
             ha="left", va="bottom")
    ax1.set_xscale("log")
    ax1.set_xlabel(r"residence time $\tau$ [s]")
    ax1.set_ylabel("inlet temperature [K]")
    style_axis(ax1, False)

    panel(ax2, "c", "Hot-branch continuation for selected inlet states")
    selected_lookup = {400: (COLORS["blue"], "S1"),
                       600: (COLORS["cyan"], "S2"),
                       800: (COLORS["red"], "S3")}
    for k, target in enumerate((300, 400, 500, 600, 700, 800)):
        grp = field[field.inlet_temperature_K == target].sort_values("residence_time_s")
        if target in selected_lookup:
            color, tag = selected_lookup[target]
            ax2.plot(grp.residence_time_s, grp.steady_temperature_K, lw=1.65,
                     color=color, label=f"{tag}: {target} K", zorder=4)
        else:
            ax2.plot(grp.residence_time_s, grp.steady_temperature_K, lw=0.8,
                     color="#aab2bd", alpha=0.72, zorder=2)
    ax2.set_xscale("log")
    ax2.set_xlabel(r"residence time $\tau$ [s]")
    ax2.set_ylabel("steady reactor temperature [K]")
    ax2.legend(frameon=False, ncol=3, loc="upper left")
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


def render_dense_field_plate(out: Path, meta: dict) -> None:
    """Full-page field/cut plate with almost no non-data-bearing white area."""
    kepler = pd.read_csv(out / "data" / "kepler_orekit_grid.csv", float_precision="round_trip")
    pv = pd.read_csv(out / "data" / "pvlib_cec_operating_surface.csv", float_precision="round_trip")
    cstr = pd.read_csv(out / "data" / "cantera_cstr_hot_branch_surface.csv", float_precision="round_trip")

    egrid, mgrid, eccentric_anomaly = pivot_grid(kepler, "M_rad", "e", "E_rad")
    irradiance, cell_temp, pmp = pivot_grid(
        pv, "cell_temperature_C", "effective_irradiance_W_m2", "p_mp"
    )
    tau, inlet_temp, reactor_temp = pivot_grid(
        cstr, "inlet_temperature_K", "residence_time_s", "steady_temperature_K"
    )
    _, _, heat_release = pivot_grid(
        cstr, "inlet_temperature_K", "residence_time_s", "heat_release_rate_W_m3"
    )

    fig = plt.figure(figsize=(15.4, 11.2), facecolor="white")
    outer = fig.add_gridspec(
        3, 1, left=0.062, right=0.985, bottom=0.060, top=0.975,
        height_ratios=[1.0, 1.0, 1.05], hspace=0.265,
    )
    row0 = outer[0].subgridspec(1, 2, width_ratios=[3.65, 1.18], wspace=0.13)
    row1 = outer[1].subgridspec(1, 2, width_ratios=[3.65, 1.18], wspace=0.13)
    row2 = outer[2].subgridspec(1, 3, width_ratios=[1.78, 1.78, 1.18], wspace=0.16)
    ax_k = fig.add_subplot(row0[0])
    ax_kcut = fig.add_subplot(row0[1])
    ax_pv = fig.add_subplot(row1[0])
    ax_pvcut = fig.add_subplot(row1[1])
    ax_ct = fig.add_subplot(row2[0])
    ax_cq = fig.add_subplot(row2[1], sharex=ax_ct, sharey=ax_ct)
    ax_ccut = fig.add_subplot(row2[2])

    def field_header(ax, letter: str, title: str, subtitle: str) -> None:
        ax.text(
            0.012, 0.965, letter, transform=ax.transAxes, ha="left", va="top",
            fontsize=10.5, fontweight="bold", color="white", zorder=12,
            bbox={"boxstyle": "round,pad=0.20", "fc": "#111827", "ec": "white",
                  "lw": 0.55, "alpha": 0.92},
        )
        ax.text(
            0.052, 0.965, title, transform=ax.transAxes, ha="left", va="top",
            fontsize=9.2, fontweight="bold", color="white", zorder=12,
            bbox={"boxstyle": "round,pad=0.22", "fc": "#111827", "ec": "none",
                  "alpha": 0.80},
        )
        ax.text(
            0.988, 0.045, subtitle, transform=ax.transAxes, ha="right", va="bottom",
            fontsize=7.2, color="white", zorder=12,
            bbox={"boxstyle": "round,pad=0.22", "fc": "#111827", "ec": "white",
                  "lw": 0.45, "alpha": 0.78},
        )

    def cut_header(ax, letter: str, title: str) -> None:
        ax.set_facecolor("#eef2f6")
        ax.text(0.02, 0.98, letter, transform=ax.transAxes, ha="left", va="top",
                fontsize=10.5, fontweight="bold")
        ax.text(0.12, 0.98, title, transform=ax.transAxes, ha="left", va="top",
                fontsize=8.3, fontweight="bold")

    def knowledge_arrow(ax, start, end, text: str, color: str, text_pos,
                        rad: float = 0.0, align: str = "center") -> None:
        """Reference-style mechanism arrow with a halo that survives any colormap."""
        patch = FancyArrowPatch(
            start, end, transform=ax.transAxes, arrowstyle="-|>", mutation_scale=12,
            connectionstyle=f"arc3,rad={rad}", color=color, linewidth=1.65,
            zorder=10, clip_on=True,
        )
        patch.set_path_effects([pe.Stroke(linewidth=3.7, foreground="white", alpha=0.88),
                                pe.Normal()])
        ax.add_patch(patch)
        txt = ax.text(
            text_pos[0], text_pos[1], text, transform=ax.transAxes, color=color,
            fontsize=7.4, fontweight="bold", ha=align, va="center", zorder=11,
            linespacing=1.05,
        )
        txt.set_path_effects([pe.Stroke(linewidth=2.8, foreground="white", alpha=0.96),
                              pe.Normal()])

    def halo_contours(contour_set, labels) -> None:
        contour_set.set_path_effects([
            pe.Stroke(linewidth=1.65, foreground="#17202a", alpha=0.72), pe.Normal()
        ])
        for label in labels:
            label.set_path_effects([
                pe.Stroke(linewidth=2.3, foreground="#17202a", alpha=0.85), pe.Normal()
            ])

    # Row 1: one root for every (M, e) sample; field and line cuts use identical tags.
    kmap = ax_k.pcolormesh(mgrid, egrid, eccentric_anomaly.T, shading="auto",
                           cmap="viridis", rasterized=True)
    kc = ax_k.contour(mgrid, egrid, eccentric_anomaly.T,
                      levels=[0.25, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0],
                      colors="white", linewidths=0.52, alpha=0.88)
    klabels = ax_k.clabel(kc, inline=True, fontsize=5.9, fmt=lambda x: f"E={x:g}")
    halo_contours(kc, klabels)
    km, ke = np.meshgrid(mgrid[::6], egrid[::3])
    ax_k.scatter(km, ke, s=3.8, facecolors="none", edgecolors="white",
                 linewidths=0.24, alpha=0.52, rasterized=True)
    k_slices = [(0.60, "#26c6da", "S1"), (0.90, "#ffca28", "S2"),
                (0.99, "#ff7043", "S3")]
    for es, color, tag in k_slices:
        ax_k.axhline(es, color=color, ls="--", lw=1.15)
        ax_k.text(0.10, es - 0.020, f"{tag}  e={es:g}", fontsize=6.6,
                  color="#111827", ha="left", va="top",
                  bbox={"boxstyle": "round,pad=0.13", "fc": "white", "ec": color,
                        "lw": 0.65, "alpha": 0.90})
        j = int(np.argmin(np.abs(egrid - es)))
        y = eccentric_anomaly[:, j]
        ax_kcut.plot(mgrid, y, color=color, lw=1.75, label=f"{tag}  e={es:g}")
        ax_kcut.fill_between(mgrid, 0, y, color=color, alpha=0.065)
    knowledge_arrow(ax_k, (0.25, 0.19), (0.70, 0.19),
                    "phase advance\n" r"$M\,\uparrow\;\Rightarrow\;E\,\uparrow$",
                    "#145f82", (0.48, 0.27), rad=-0.08)
    knowledge_arrow(ax_k, (0.19, 0.36), (0.19, 0.76),
                    r"eccentricity $\uparrow$" "\n" r"nonlinear shift $\uparrow$",
                    "#7b2b83", (0.215, 0.56), align="left")
    knowledge_arrow(ax_k, (0.34, 0.77), (0.025, 0.94),
                    "near-parabolic corner\n" r"$|\partial E/\partial M|\gg1$",
                    "#b4232f", (0.355, 0.82), rad=0.16, align="left")
    bulk = ax_k.text(0.55, 0.08, "well-conditioned bulk", transform=ax_k.transAxes,
                     color="#173a5e", fontsize=7.1, fontweight="bold",
                     ha="center", va="center", zorder=11)
    bulk.set_path_effects([pe.Stroke(linewidth=2.8, foreground="white"), pe.Normal()])
    field_header(ax_k, "a", "Kepler eccentric-anomaly field",
                 f"72 eccentricities × 180 anomalies = {len(kepler):,} independent roots")
    inset_colorbar(fig, ax_k, kmap, r"eccentric anomaly $E$ [rad]", width="27%")
    ax_k.set_xlabel(r"mean anomaly $M$ [rad]")
    ax_k.set_ylabel(r"eccentricity $e$")
    ax_k.set_xlim(mgrid.min(), mgrid.max())
    ax_k.set_ylim(egrid.min(), egrid.max())
    style_axis(ax_k, False)
    cut_header(ax_kcut, "b", "matched anomaly cuts")
    ax_kcut.set_xlabel(r"$M$ [rad]")
    ax_kcut.set_ylabel(r"solved $E$ [rad]")
    ax_kcut.set_xlim(mgrid.min(), mgrid.max())
    ax_kcut.set_ylim(0, math.pi * 1.02)
    ax_kcut.legend(frameon=True, facecolor="white", edgecolor="#b9c2cc",
                   framealpha=0.85, loc="lower right", fontsize=6.8)
    style_axis(ax_kcut)

    # Row 2: every module state has a separate implicit single-diode root.
    pvmap = ax_pv.pcolormesh(cell_temp, irradiance, pmp.T, shading="auto",
                             cmap="inferno", rasterized=True)
    pvc = ax_pv.contour(cell_temp, irradiance, pmp.T,
                        levels=[50, 100, 150, 200, 250], colors="white", linewidths=0.55)
    pvlabels = ax_pv.clabel(pvc, inline=True, fontsize=6.0, fmt="%g W")
    halo_contours(pvc, pvlabels)
    pt, pg = np.meshgrid(cell_temp, irradiance)
    ax_pv.scatter(pt, pg, s=6.0, facecolors="none", edgecolors="white",
                  linewidths=0.30, alpha=0.70, rasterized=True)
    pv_slices = [(200, "#31a9ff", "P1"), (600, "#52d273", "P2"),
                 (1000, "#ffd43b", "P3")]
    for gs, color, tag in pv_slices:
        ax_pv.axhline(gs, color=color, ls="--", lw=1.15)
        ax_pv.text(cell_temp.min() + 1.6, gs + 18, f"{tag}  {gs} W m$^{{-2}}$",
                   fontsize=6.6, color="#111827", ha="left", va="bottom",
                   bbox={"boxstyle": "round,pad=0.13", "fc": "white", "ec": color,
                         "lw": 0.65, "alpha": 0.90})
        j = int(np.argmin(np.abs(irradiance - gs)))
        y = pmp[:, j]
        ax_pvcut.plot(cell_temp, y, color=color, lw=1.8,
                      label=f"{tag}  {gs} W m$^{{-2}}$")
        ax_pvcut.fill_between(cell_temp, 0, y, color=color, alpha=0.065)
    ax_pv.plot(25, 1000, marker="*", ms=9.5, mfc="#00e5ff", mec="#14213d",
               mew=0.65, zorder=12)
    stc_text = ax_pv.text(27.5, 968, "reference state\n" r"25$^\circ$C, 1000 W m$^{-2}$",
                          color="#083d56", fontsize=6.8, fontweight="bold",
                          ha="left", va="top", zorder=12)
    stc_text.set_path_effects([pe.Stroke(linewidth=2.7, foreground="white"), pe.Normal()])
    knowledge_arrow(ax_pv, (0.12, 0.19), (0.12, 0.70),
                    r"irradiance $\uparrow$" "\n" r"photocurrent and $P_{mp}\uparrow$",
                    "#16854b", (0.145, 0.45), align="left")
    knowledge_arrow(ax_pv, (0.51, 0.79), (0.83, 0.79),
                    r"cell heating $\rightarrow$" "\n" r"thermal derating, $P_{mp}\downarrow$",
                    "#b4232f", (0.67, 0.70), rad=-0.10)
    low_light = ax_pv.text(0.33, 0.095, "low-light operating region",
                           transform=ax_pv.transAxes, color="#54c7ec", fontsize=7.0,
                           fontweight="bold", ha="center", va="center", zorder=11)
    low_light.set_path_effects([pe.Stroke(linewidth=2.8, foreground="#111827"), pe.Normal()])
    field_header(ax_pv, "c", "PV maximum-power operating surface",
                 f"21 irradiances × 17 temperatures = {len(pv):,} independent roots")
    inset_colorbar(fig, ax_pv, pvmap, r"maximum power $P_{mp}$ [W]", width="27%")
    ax_pv.set_xlabel(r"cell temperature [$^\circ$C]")
    ax_pv.set_ylabel(r"effective irradiance [W m$^{-2}$]")
    style_axis(ax_pv, False)
    cut_header(ax_pvcut, "d", "matched power cuts")
    ax_pvcut.set_xlabel(r"cell temperature [$^\circ$C]")
    ax_pvcut.set_ylabel(r"$P_{mp}$ [W]")
    ax_pvcut.set_xlim(cell_temp.min(), cell_temp.max())
    ax_pvcut.set_ylim(0, np.nanmax(pmp) * 1.05)
    ax_pvcut.legend(frameon=True, facecolor="white", edgecolor="#b9c2cc",
                    framealpha=0.85, loc="upper right", fontsize=6.6)
    style_axis(ax_pvcut)

    # Row 3: two physically complementary fields share the same executed nodes.
    ctmap = ax_ct.pcolormesh(tau, inlet_temp, reactor_temp, shading="auto",
                             cmap="inferno", rasterized=True)
    ctext = ax_ct.contour(tau, inlet_temp, reactor_temp, levels=[1000],
                          colors="cyan", linewidths=1.15)
    ctext.set_path_effects([pe.Stroke(linewidth=2.7, foreground="#102a43"), pe.Normal()])
    cthot = ax_ct.contour(tau, inlet_temp, reactor_temp, levels=[1400, 1700],
                          colors="white", linewidths=0.55, alpha=0.90)
    ctlabels = ax_ct.clabel(cthot, inline=True, fontsize=5.7,
                            fmt=lambda x: f"{int(x)} K")
    halo_contours(cthot, ctlabels)
    qt = np.maximum(heat_release, 1e2)
    cqmap = ax_cq.pcolormesh(tau, inlet_temp, qt, shading="auto", cmap="magma",
                             norm=LogNorm(vmin=1e2, vmax=max(1e6, np.nanmax(qt))),
                             rasterized=True)
    cqext = ax_cq.contour(tau, inlet_temp, reactor_temp, levels=[1000],
                          colors="cyan", linewidths=1.15)
    cqext.set_path_effects([pe.Stroke(linewidth=2.7, foreground="#102a43"), pe.Normal()])
    hlevels = [v for v in (1e4, 1e6, 1e8) if np.nanmin(qt) < v < np.nanmax(qt)]
    if hlevels:
        hc = ax_cq.contour(tau, inlet_temp, qt, levels=hlevels,
                           colors="white", linewidths=0.48, alpha=0.82)
        hclabels = ax_cq.clabel(hc, inline=True, fontsize=5.7,
                                fmt=lambda x: rf"$10^{{{int(np.log10(x))}}}$")
        halo_contours(hc, hclabels)
    nt, ni = np.meshgrid(tau[::3], inlet_temp)
    c_slices = [(400, "#31a9ff", "C1"), (600, "#52d273", "C2"),
                (800, "#ff5a5f", "C3")]
    for ax in (ax_ct, ax_cq):
        ax.scatter(nt, ni, s=4.2, facecolors="none", edgecolors="white",
                   linewidths=0.25, alpha=0.54, rasterized=True)
        for ts, color, tag in c_slices:
            ax.axhline(ts, color=color, ls="--", lw=1.0)
            ax.text(tau.min() * 1.35, ts + (7 if ts < 800 else -9), tag,
                    fontsize=6.4, color="#111827", ha="left",
                    va="bottom" if ts < 800 else "top",
                    bbox={"boxstyle": "round,pad=0.11", "fc": "white", "ec": color,
                          "lw": 0.60, "alpha": 0.90})
        ax.set_xscale("log")
        ax.set_xlabel(r"residence time $\tau$ [s]")
        style_axis(ax, False)
    knowledge_arrow(ax_ct, (0.17, 0.22), (0.71, 0.22),
                    r"residence time $\uparrow$" "\nignition / hot branch",
                    "#1479b8", (0.46, 0.31), rad=-0.08)
    knowledge_arrow(ax_ct, (0.25, 0.47), (0.25, 0.76),
                    r"inlet preheat $\uparrow$" "\nextinction shifts left",
                    "#16854b", (0.285, 0.62), align="left")
    cold = ax_ct.text(0.15, 0.10, "cold / extinguished", transform=ax_ct.transAxes,
                      color="#73d7ff", fontsize=6.9, fontweight="bold",
                      ha="center", va="center", zorder=11)
    cold.set_path_effects([pe.Stroke(linewidth=2.7, foreground="#111827"), pe.Normal()])
    hot = ax_ct.text(0.67, 0.76, "reacting plateau", transform=ax_ct.transAxes,
                     color="#8b1e1e", fontsize=7.0, fontweight="bold",
                     ha="center", va="center", zorder=11)
    hot.set_path_effects([pe.Stroke(linewidth=2.8, foreground="white"), pe.Normal()])
    knowledge_arrow(ax_cq, (0.18, 0.22), (0.73, 0.28),
                    "reaction-rate growth\n" r"$\dot q\,\uparrow$ after ignition",
                    "#b4232f", (0.49, 0.37), rad=-0.10)
    knowledge_arrow(ax_cq, (0.42, 0.68), (0.18, 0.53),
                    "same extinction\nboundary",
                    "#007f91", (0.47, 0.70), rad=0.10)
    negligible = ax_cq.text(0.15, 0.10, "negligible heat release",
                            transform=ax_cq.transAxes, color="#73d7ff", fontsize=6.8,
                            fontweight="bold", ha="center", va="center", zorder=11)
    negligible.set_path_effects([
        pe.Stroke(linewidth=2.7, foreground="#111827"), pe.Normal()
    ])
    for ts, color, tag in c_slices:
        j = int(np.argmin(np.abs(inlet_temp - ts)))
        y = reactor_temp[j, :]
        ax_ccut.plot(tau, y, color=color, lw=1.65, label=f"{tag}  {ts} K")
        ax_ccut.fill_between(tau, inlet_temp.min(), y, color=color, alpha=0.055)
    field_header(ax_ct, "e", "CSTR steady temperature",
                 f"21 inlet states × 72 residence times = {len(cstr):,} roots")
    field_header(ax_cq, "f", "CSTR heat release", "cyan: extinction boundary")
    inset_colorbar(fig, ax_ct, ctmap, "reactor temperature [K]", width="34%")
    inset_colorbar(fig, ax_cq, cqmap, r"heat release [W m$^{-3}$]", width="34%")
    ax_ct.set_ylabel("inlet temperature [K]")
    ax_cq.tick_params(labelleft=False)
    cut_header(ax_ccut, "g", "matched hot-branch cuts")
    ax_ccut.set_xscale("log")
    ax_ccut.set_xlabel(r"residence time $\tau$ [s]")
    ax_ccut.set_ylabel("steady reactor temperature [K]")
    ax_ccut.set_ylim(inlet_temp.min(), np.nanmax(reactor_temp) * 1.025)
    ax_ccut.legend(frameon=True, facecolor="white", edgecolor="#b9c2cc",
                   framealpha=0.85, loc="lower right", fontsize=6.6)
    style_axis(ax_ccut)

    for ax in (ax_k, ax_pv, ax_ct, ax_cq):
        for spine in ax.spines.values():
            spine.set_color("#ffffff")
            spine.set_alpha(0.65)

    meta["dense_field_plate"] = save_figure(
        fig, out, "fig9_dense_gradient_field_comparison_2d",
        {"kepler_field": ax_k, "kepler_cut": ax_kcut,
         "pv_field": ax_pv, "pv_cut": ax_pvcut,
         "cstr_temperature": ax_ct, "cstr_heat_release": ax_cq,
         "cstr_cut": ax_ccut},
    )


def render_split_knowledge_figures(out: Path, meta: dict) -> None:
    """Render three final-size, large-type mechanism figures for the manuscript."""
    kepler = pd.read_csv(out / "data" / "kepler_orekit_grid.csv", float_precision="round_trip")
    pv = pd.read_csv(out / "data" / "pvlib_cec_operating_surface.csv", float_precision="round_trip")
    cstr = pd.read_csv(out / "data" / "cantera_cstr_hot_branch_surface.csv", float_precision="round_trip")
    egrid, mgrid, kval = pivot_grid(kepler, "M_rad", "e", "E_rad")
    irradiance, cell_temp, pmp = pivot_grid(
        pv, "cell_temperature_C", "effective_irradiance_W_m2", "p_mp"
    )
    tau, inlet_temp, rtemp = pivot_grid(
        cstr, "inlet_temperature_K", "residence_time_s", "steady_temperature_K"
    )
    _, _, qdot = pivot_grid(
        cstr, "inlet_temperature_K", "residence_time_s", "heat_release_rate_W_m3"
    )

    def mechanism_arrow(ax, start, end, text_value: str, color: str, text_pos,
                        rad: float = 0.0, align: str = "center") -> None:
        patch = FancyArrowPatch(
            start, end, transform=ax.transAxes, arrowstyle="-|>", mutation_scale=13,
            connectionstyle=f"arc3,rad={rad}", color=color, linewidth=1.9,
            zorder=12, clip_on=True,
        )
        patch.set_path_effects([
            pe.Stroke(linewidth=4.3, foreground="white", alpha=0.94), pe.Normal()
        ])
        ax.add_patch(patch)
        label = ax.text(
            text_pos[0], text_pos[1], text_value, transform=ax.transAxes,
            color=color, fontsize=9.0, fontweight="bold", ha=align, va="center",
            linespacing=1.04, zorder=13,
        )
        label.set_path_effects([
            pe.Stroke(linewidth=3.4, foreground="white", alpha=0.98), pe.Normal()
        ])

    def field_title(ax, letter: str, title: str, count_text: str | None = None) -> None:
        ax.text(0.015, 0.965, letter, transform=ax.transAxes, ha="left", va="top",
                fontsize=11.5, fontweight="bold", color="white", zorder=15,
                bbox={"boxstyle": "round,pad=0.18", "fc": "#111827", "ec": "white",
                      "lw": 0.6, "alpha": 0.94})
        ax.text(0.070, 0.965, title, transform=ax.transAxes, ha="left", va="top",
                fontsize=10.3, fontweight="bold", color="white", zorder=15,
                bbox={"boxstyle": "round,pad=0.20", "fc": "#111827", "ec": "none",
                      "alpha": 0.82})
        if count_text:
            ax.text(0.985, 0.045, count_text, transform=ax.transAxes, ha="right",
                    va="bottom", fontsize=8.0, color="white", zorder=15,
                    bbox={"boxstyle": "round,pad=0.20", "fc": "#111827",
                          "ec": "white", "lw": 0.45, "alpha": 0.82})

    def curve_title(ax, letter: str, title: str) -> None:
        ax.set_facecolor("#edf2f7")
        ax.text(0.02, 0.97, letter, transform=ax.transAxes, ha="left", va="top",
                fontsize=11.5, fontweight="bold")
        ax.text(0.15, 0.97, title, transform=ax.transAxes, ha="left", va="top",
                fontsize=9.4, fontweight="bold")

    def contour_halo(contour_set, labels) -> None:
        contour_set.set_path_effects([
            pe.Stroke(linewidth=1.85, foreground="#17202a", alpha=0.78), pe.Normal()
        ])
        for label in labels:
            label.set_path_effects([
                pe.Stroke(linewidth=2.7, foreground="#17202a", alpha=0.92), pe.Normal()
            ])

    # Figure 9a: Kepler, at final two-column width.
    fig = plt.figure(figsize=(7.2, 3.55), facecolor="white")
    gs = fig.add_gridspec(1, 2, left=0.085, right=0.985, bottom=0.17, top=0.965,
                          width_ratios=[2.55, 1.0], wspace=0.23)
    ax0, ax1 = fig.add_subplot(gs[0]), fig.add_subplot(gs[1])
    im = ax0.pcolormesh(mgrid, egrid, kval.T, shading="auto", cmap="viridis",
                        rasterized=True)
    cs = ax0.contour(mgrid, egrid, kval.T, levels=[0.5, 1.0, 1.5, 2.0, 2.5, 3.0],
                     colors="white", linewidths=0.65)
    labs = ax0.clabel(cs, inline=True, fontsize=7.1, fmt=lambda x: f"E={x:g}")
    contour_halo(cs, labs)
    mm, ee = np.meshgrid(mgrid[::8], egrid[::4])
    ax0.scatter(mm, ee, s=4.5, facecolors="none", edgecolors="white",
                linewidths=0.28, alpha=0.48, rasterized=True)
    slices = [(0.60, "#22b8cf", "S1"), (0.90, "#ffc107", "S2"),
              (0.99, "#ff5a5f", "S3")]
    kcut_series = []
    for es, color, tag in slices:
        ax0.axhline(es, color=color, ls="--", lw=1.25)
        j = int(np.argmin(np.abs(egrid - es)))
        values = kval[:, j]
        kcut_series.append((es, color, tag, values))
        ax1.plot(mgrid, values, color=color, lw=2.0, marker="o", ms=2.5,
                 markevery=15, mec="white", mew=0.35, label=f"{tag}: e={es:g}")
    ax1.fill_between(mgrid, kcut_series[0][3], kcut_series[2][3],
                     color="#7b2b83", alpha=0.11, zorder=0)
    probe_m = math.pi / 2
    probe_i = int(np.argmin(np.abs(mgrid - probe_m)))
    low_e = kcut_series[0][3][probe_i]
    high_e = kcut_series[2][3][probe_i]
    ax1.axvline(probe_m, color="#46566b", ls=":", lw=1.0)
    ax1.annotate("", xy=(probe_m, high_e), xytext=(probe_m, low_e),
                 arrowprops={"arrowstyle": "<->", "color": "#7b2b83", "lw": 1.25})
    ax1.text(probe_m + 0.08, (low_e + high_e) / 2,
             rf"$\Delta E={high_e-low_e:.2f}$ rad", color="#7b2b83",
             fontsize=7.3, fontweight="bold", rotation=90, va="center")
    mechanism_arrow(ax0, (0.32, 0.22), (0.80, 0.22),
                    "phase advance\n" r"$M\uparrow\;\Rightarrow\;E\uparrow$",
                    "#145f82", (0.57, 0.31), rad=-0.08)
    mechanism_arrow(ax0, (0.22, 0.38), (0.22, 0.72),
                    r"eccentricity $\uparrow$" "\nnonlinear shift grows",
                    "#7b2b83", (0.26, 0.55), align="left")
    mechanism_arrow(ax0, (0.55, 0.76), (0.035, 0.92),
                    "near-parabolic hard corner\n" r"$|\partial E/\partial M|\gg1$",
                    "#b4232f", (0.58, 0.82), rad=0.16, align="left")
    bulk = ax0.text(0.64, 0.08, "well-conditioned bulk", transform=ax0.transAxes,
                    fontsize=8.8, fontweight="bold", color="#173a5e", ha="center")
    bulk.set_path_effects([pe.Stroke(linewidth=3.0, foreground="white"), pe.Normal()])
    field_title(ax0, "a", "Kepler anomaly solve field",
                f"72 × 180 = {len(kepler):,} roots")
    inset_colorbar(fig, ax0, im, r"eccentric anomaly $E$ [rad]", width="34%")
    ax0.set_xlabel(r"mean anomaly $M$ [rad]", fontsize=9.5)
    ax0.set_ylabel(r"eccentricity $e$", fontsize=9.5)
    ax0.tick_params(labelsize=8.2)
    style_axis(ax0, False)
    curve_title(ax1, "b", "matched solution cuts")
    ax1.set_xlabel(r"mean anomaly $M$ [rad]", fontsize=9.0)
    ax1.set_ylabel(r"solved $E$ [rad]", fontsize=9.0)
    ax1.tick_params(labelsize=8.0)
    ax1.set_xlim(mgrid.min(), mgrid.max())
    ax1.set_ylim(0, math.pi * 1.02)
    ax1.legend(loc="lower right", frameon=True, fontsize=7.7,
               facecolor="white", edgecolor="#aeb8c2", framealpha=0.9)
    style_axis(ax1)
    meta["kepler_mechanism_detail"] = save_figure(
        fig, out, "fig9a_kepler_mechanism_field_2d", {"field": ax0, "cuts": ax1}
    )

    # Figure 9b: PV power mechanisms, at final two-column width.
    fig = plt.figure(figsize=(7.2, 3.55), facecolor="white")
    gs = fig.add_gridspec(1, 2, left=0.09, right=0.985, bottom=0.17, top=0.965,
                          width_ratios=[2.55, 1.0], wspace=0.24)
    ax0, ax1 = fig.add_subplot(gs[0]), fig.add_subplot(gs[1])
    im = ax0.pcolormesh(cell_temp, irradiance, pmp.T, shading="auto", cmap="inferno",
                        rasterized=True)
    cs = ax0.contour(cell_temp, irradiance, pmp.T, levels=[50, 100, 150, 200, 250],
                     colors="white", linewidths=0.65)
    labs = ax0.clabel(cs, inline=True, fontsize=7.1, fmt="%g W")
    contour_halo(cs, labs)
    pt, pg = np.meshgrid(cell_temp, irradiance)
    ax0.scatter(pt, pg, s=6, facecolors="none", edgecolors="white",
                linewidths=0.3, alpha=0.62, rasterized=True)
    pslices = [(200, "#29a7ff", "P1"), (600, "#3dcc73", "P2"),
               (1000, "#ffd43b", "P3")]
    pcut_series = []
    for gsval, color, tag in pslices:
        ax0.axhline(gsval, color=color, ls="--", lw=1.25)
        j = int(np.argmin(np.abs(irradiance - gsval)))
        values = pmp[:, j]
        pcut_series.append((gsval, color, tag, values))
        ax1.plot(cell_temp, values, color=color, lw=2.0, marker="o", ms=2.7,
                 markevery=2, mec="white", mew=0.35,
                 label=f"{tag}: {gsval} W m$^{{-2}}$")
    ax1.fill_between(cell_temp, pcut_series[0][3], pcut_series[1][3],
                     color="#3dcc73", alpha=0.075, zorder=0)
    ax1.fill_between(cell_temp, pcut_series[1][3], pcut_series[2][3],
                     color="#ffd43b", alpha=0.075, zorder=0)
    ref_t = 25.0
    ref_i = int(np.argmin(np.abs(cell_temp - ref_t)))
    ax1.axvline(ref_t, color="#46566b", ls=":", lw=1.05)
    for _, color, _, values in pcut_series:
        ax1.scatter(ref_t, values[ref_i], s=20, marker="D", color=color,
                    edgecolor="white", linewidth=0.45, zorder=7)
    p_low = pcut_series[0][3][ref_i]
    p_high = pcut_series[2][3][ref_i]
    ax1.annotate("", xy=(ref_t, p_high), xytext=(ref_t, p_low),
                 arrowprops={"arrowstyle": "<->", "color": "#16854b", "lw": 1.25})
    ax1.text(ref_t + 2.2, (p_low + p_high) / 2, "irradiance\ngain",
             color="#16854b", fontsize=7.2, fontweight="bold", va="center")
    beta_abs = float(np.polyfit(cell_temp, pcut_series[2][3], 1)[0])
    beta_rel = 100.0 * beta_abs / pcut_series[2][3][ref_i]
    ax1.text(0.50, 0.035,
             rf"$\beta_P(1000)={beta_abs:.2f}$ W K$^{{-1}}$ "
             + rf"({beta_rel:.3f}% K$^{{-1}}$)",
             transform=ax1.transAxes, fontsize=6.35, color="#8b1e1e", ha="center",
             bbox={"boxstyle": "round,pad=0.24", "fc": "white", "ec": "#b4232f",
                   "lw": 0.7, "alpha": 0.88})
    for _, color, tag, values in pcut_series:
        direct = ax1.text(cell_temp.max() - 1.5, values[-1] + 3.0, tag,
                          color=color, fontsize=7.5, fontweight="bold",
                          ha="right", va="bottom", zorder=8)
        direct.set_path_effects([
            pe.Stroke(linewidth=2.5, foreground="white"), pe.Normal()
        ])
    ax0.plot(25, 1000, marker="*", ms=11, mfc="#00e5ff", mec="#14213d",
             mew=0.75, zorder=15)
    stc = ax0.text(0.49, 0.80, "STC reference\n" r"25$^\circ$C, 1000 W m$^{-2}$",
                   transform=ax0.transAxes, fontsize=8.4, fontweight="bold",
                   color="#083d56", ha="left", va="center", zorder=14)
    stc.set_path_effects([pe.Stroke(linewidth=3.1, foreground="white"), pe.Normal()])
    mechanism_arrow(ax0, (0.14, 0.18), (0.14, 0.72),
                    r"irradiance $\uparrow$" "\n" r"$I_{ph}$ and $P_{mp}\uparrow$",
                    "#16854b", (0.18, 0.46), align="left")
    mechanism_arrow(ax0, (0.53, 0.70), (0.86, 0.70),
                    r"cell heating $\rightarrow$" "\n" r"thermal derating, $P_{mp}\downarrow$",
                    "#b4232f", (0.70, 0.59), rad=-0.10)
    low = ax0.text(0.37, 0.09, "low-light region", transform=ax0.transAxes,
                   fontsize=8.7, fontweight="bold", color="#58d3ff", ha="center")
    low.set_path_effects([pe.Stroke(linewidth=3.0, foreground="#111827"), pe.Normal()])
    high = ax0.text(0.78, 0.88, "high-output region", transform=ax0.transAxes,
                    fontsize=8.7, fontweight="bold", color="#8b1e1e", ha="center")
    high.set_path_effects([pe.Stroke(linewidth=3.0, foreground="white"), pe.Normal()])
    field_title(ax0, "a", "PV maximum-power solve field",
                f"21 × 17 = {len(pv):,} roots")
    inset_colorbar(fig, ax0, im, r"maximum power $P_{mp}$ [W]", width="34%")
    ax0.set_xlabel(r"cell temperature [$^\circ$C]", fontsize=9.5)
    ax0.set_ylabel(r"effective irradiance [W m$^{-2}$]", fontsize=9.5)
    ax0.tick_params(labelsize=8.2)
    style_axis(ax0, False)
    curve_title(ax1, "b", "matched power cuts")
    ax1.set_xlabel(r"cell temperature [$^\circ$C]", fontsize=9.0)
    ax1.set_ylabel(r"maximum power $P_{mp}$ [W]", fontsize=9.0)
    ax1.tick_params(labelsize=8.0)
    ax1.set_xlim(cell_temp.min(), cell_temp.max())
    ax1.set_ylim(0, np.nanmax(pmp) * 1.05)
    style_axis(ax1)
    meta["pv_mechanism_detail"] = save_figure(
        fig, out, "fig9b_pv_power_mechanisms_2d", {"field": ax0, "cuts": ax1}
    )

    # Figure 9c: CSTR needs two full rows so temperature and heat release stay legible.
    fig = plt.figure(figsize=(7.2, 6.25), facecolor="white")
    outer = fig.add_gridspec(2, 2, left=0.09, right=0.985, bottom=0.09, top=0.98,
                             width_ratios=[2.55, 1.0], hspace=0.30, wspace=0.24)
    axt, axtc = fig.add_subplot(outer[0, 0]), fig.add_subplot(outer[0, 1])
    axq, axqc = fig.add_subplot(outer[1, 0]), fig.add_subplot(outer[1, 1])
    tim = axt.pcolormesh(tau, inlet_temp, rtemp, shading="auto", cmap="inferno",
                         rasterized=True)
    ext = axt.contour(tau, inlet_temp, rtemp, levels=[1000], colors="cyan", linewidths=1.25)
    ext.set_path_effects([pe.Stroke(linewidth=3.0, foreground="#102a43"), pe.Normal()])
    hotcs = axt.contour(tau, inlet_temp, rtemp, levels=[1400, 1700], colors="white",
                        linewidths=0.65)
    hotlabs = axt.clabel(hotcs, inline=True, fontsize=7.0, fmt=lambda x: f"{int(x)} K")
    contour_halo(hotcs, hotlabs)
    qt = np.maximum(qdot, 1e2)
    qim = axq.pcolormesh(tau, inlet_temp, qt, shading="auto", cmap="magma",
                         norm=LogNorm(vmin=1e2, vmax=max(1e6, np.nanmax(qt))),
                         rasterized=True)
    qext = axq.contour(tau, inlet_temp, rtemp, levels=[1000], colors="cyan", linewidths=1.25)
    qext.set_path_effects([pe.Stroke(linewidth=3.0, foreground="#102a43"), pe.Normal()])
    qlevels = [v for v in (1e4, 1e6, 1e8) if np.nanmin(qt) < v < np.nanmax(qt)]
    qcs = axq.contour(tau, inlet_temp, qt, levels=qlevels, colors="white", linewidths=0.6)
    qlabs = axq.clabel(qcs, inline=True, fontsize=7.0,
                       fmt=lambda x: rf"$10^{{{int(np.log10(x))}}}$")
    contour_halo(qcs, qlabs)
    nt, ni = np.meshgrid(tau[::3], inlet_temp)
    cslices = [(400, "#29a7ff", "C1"), (600, "#3dcc73", "C2"),
               (800, "#ff5a5f", "C3")]
    for field_ax in (axt, axq):
        field_ax.scatter(nt, ni, s=4.6, facecolors="none", edgecolors="white",
                         linewidths=0.28, alpha=0.52, rasterized=True)
        for tin_value, color, _ in cslices:
            field_ax.axhline(tin_value, color=color, ls="--", lw=1.2)
        field_ax.set_xscale("log")
        field_ax.set_xlabel(r"residence time $\tau$ [s]", fontsize=9.3)
        field_ax.set_ylabel("inlet temperature [K]", fontsize=9.3)
        field_ax.tick_params(labelsize=8.1)
        style_axis(field_ax, False)
    ccut_series = []
    for tin_value, color, tag in cslices:
        j = int(np.argmin(np.abs(inlet_temp - tin_value)))
        temp_values = rtemp[j, :]
        heat_values = qt[j, :]
        hot_indices = np.flatnonzero(temp_values >= 1000.0)
        critical_index = int(hot_indices[0]) if len(hot_indices) else 0
        critical_tau = float(tau[critical_index])
        ccut_series.append((tin_value, color, tag, temp_values, heat_values,
                            critical_index, critical_tau))
        axtc.plot(tau, temp_values, color=color, lw=2.0, marker="o", ms=2.4,
                  markevery=8, mec="white", mew=0.35,
                  label=f"{tag}: {tin_value} K")
        axqc.plot(tau, heat_values, color=color, lw=2.0, marker="o", ms=2.4,
                  markevery=8, mec="white", mew=0.35,
                  label=f"{tag}: {tin_value} K")
        axtc.fill_between(tau, inlet_temp.min(), temp_values, color=color,
                          alpha=0.035, zorder=0)
        axqc.fill_between(tau, 1e2, heat_values, color=color, alpha=0.045, zorder=0)
        axtc.axvline(critical_tau, color=color, ls=":", lw=1.0, alpha=0.72)
        axqc.axvline(critical_tau, color=color, ls=":", lw=1.0, alpha=0.72)
        axtc.scatter(critical_tau, temp_values[critical_index], marker="D", s=23,
                     color=color, edgecolor="white", linewidth=0.45, zorder=8)
        axqc.scatter(critical_tau, heat_values[critical_index], marker="D", s=23,
                     color=color, edgecolor="white", linewidth=0.45, zorder=8)
    mechanism_arrow(axt, (0.18, 0.22), (0.72, 0.22),
                    r"residence time $\uparrow$" "\nignition / hot branch",
                    "#1479b8", (0.47, 0.32), rad=-0.08)
    mechanism_arrow(axt, (0.27, 0.46), (0.27, 0.76),
                    r"inlet preheat $\uparrow$" "\nextinction shifts left",
                    "#16854b", (0.31, 0.62), align="left")
    cold = axt.text(0.16, 0.10, "cold / extinguished", transform=axt.transAxes,
                    fontsize=8.7, fontweight="bold", color="#73d7ff", ha="center")
    cold.set_path_effects([pe.Stroke(linewidth=3.0, foreground="#111827"), pe.Normal()])
    hot = axt.text(0.68, 0.75, "reacting plateau", transform=axt.transAxes,
                   fontsize=8.7, fontweight="bold", color="#8b1e1e", ha="center")
    hot.set_path_effects([pe.Stroke(linewidth=3.0, foreground="white"), pe.Normal()])
    mechanism_arrow(axq, (0.19, 0.22), (0.75, 0.28),
                    "after ignition\n" r"heat release $\dot q\uparrow$",
                    "#b4232f", (0.50, 0.38), rad=-0.10)
    mechanism_arrow(axq, (0.52, 0.69), (0.19, 0.52),
                    "same extinction\nboundary", "#007f91", (0.57, 0.72),
                    rad=0.10)
    negligible = axq.text(0.17, 0.10, "negligible heat release", transform=axq.transAxes,
                          fontsize=8.6, fontweight="bold", color="#73d7ff", ha="center")
    negligible.set_path_effects([
        pe.Stroke(linewidth=3.0, foreground="#111827"), pe.Normal()
    ])
    field_title(axt, "a", "CSTR steady-temperature field",
                f"21 × 72 = {len(cstr):,} roots")
    field_title(axq, "c", "CSTR heat-release field", "cyan: 1000 K boundary")
    inset_colorbar(fig, axt, tim, "reactor temperature [K]", width="36%")
    inset_colorbar(fig, axq, qim, r"heat release [W m$^{-3}$]", width="36%")
    curve_title(axtc, "b", "temperature cuts")
    axtc.set_xscale("log")
    axtc.axhspan(inlet_temp.min(), 1000, color="#90a4b8", alpha=0.10, zorder=-1)
    axtc.axhline(1000, color="#007f91", ls="--", lw=1.0)
    crossing_lines = ["1000 K crossing"]
    for _, _, tag, _, _, _, critical_tau in ccut_series:
        prefix = r"$\leq$" if np.isclose(critical_tau, tau.min()) else ""
        crossing_lines.append(f"{tag}: {prefix}{critical_tau:.2e} s")
    axtc.text(0.05, 0.34, "\n".join(crossing_lines), transform=axtc.transAxes,
              fontsize=7.0, color="#334155",
              bbox={"boxstyle": "round,pad=0.24", "fc": "white", "ec": "#007f91",
                    "lw": 0.7, "alpha": 0.88})
    axtc.set_xlabel(r"residence time $\tau$ [s]", fontsize=9.0)
    axtc.set_ylabel("reactor temperature [K]", fontsize=9.0)
    axtc.tick_params(labelsize=8.0)
    axtc.legend(loc="lower right", frameon=True, fontsize=7.5,
                facecolor="white", edgecolor="#aeb8c2", framealpha=0.9)
    style_axis(axtc)
    curve_title(axqc, "d", "heat-release cuts")
    axqc.set_xscale("log")
    axqc.set_yscale("log")
    axqc.axhspan(1e2, 1e3, color="#90a4b8", alpha=0.14, zorder=-1)
    axqc.text(0.05, 0.08, "cold-state floor", transform=axqc.transAxes,
              fontsize=6.9, fontweight="bold", color="#426786")
    axqc.annotate("post-ignition decay\nwith increasing residence time",
                  xy=(0.82, 0.43), xytext=(0.34, 0.66), xycoords="axes fraction",
                  textcoords="axes fraction", fontsize=7.1, color="#b4232f",
                  fontweight="bold", ha="center",
                  arrowprops={"arrowstyle": "-|>", "color": "#b4232f", "lw": 1.2,
                              "connectionstyle": "arc3,rad=-0.12"})
    axqc.set_xlabel(r"residence time $\tau$ [s]", fontsize=9.0)
    axqc.set_ylabel(r"heat release [W m$^{-3}$]", fontsize=9.0)
    axqc.tick_params(labelsize=8.0)
    axqc.legend(loc="lower right", frameon=True, fontsize=7.5,
                facecolor="white", edgecolor="#aeb8c2", framealpha=0.9)
    style_axis(axqc)
    meta["cstr_mechanism_detail"] = save_figure(
        fig, out, "fig9c_cstr_extinction_mechanisms_2d",
        {"temperature_field": axt, "temperature_cuts": axtc,
         "heat_field": axq, "heat_cuts": axqc},
    )

    # Figure 9d: PR root topology and physical phase selection.
    root_map = pd.read_csv(out / "data" / "coolprop_pr_root_map.csv")
    sat = pd.read_csv(out / "data" / "coolprop_pr_propane_saturation.csv")
    pr_grid, tr_grid, root_counts = pivot_grid(root_map, "Tr", "Pr", "root_count")
    fig = plt.figure(figsize=(7.2, 3.55), facecolor="white")
    gs = fig.add_gridspec(1, 2, left=0.085, right=0.985, bottom=0.17, top=0.965,
                          width_ratios=[2.55, 1.0], wspace=0.23)
    ax0, ax1 = fig.add_subplot(gs[0]), fig.add_subplot(gs[1])
    phase_cmap = mpl.colors.ListedColormap(["#dbeafe", "#f59e0b"])
    phase_norm = BoundaryNorm([0.5, 2.0, 3.5], phase_cmap.N)
    im = ax0.pcolormesh(pr_grid, tr_grid, root_counts, shading="auto",
                        cmap=phase_cmap, norm=phase_norm, rasterized=True)
    boundary = ax0.contour(pr_grid, tr_grid, root_counts, levels=[2],
                           colors="#0f5675", linewidths=1.15)
    boundary.set_path_effects([
        pe.Stroke(linewidth=2.8, foreground="white", alpha=0.92), pe.Normal()
    ])
    pm, tm = np.meshgrid(pr_grid[::6], tr_grid[::5])
    ax0.scatter(pm, tm, s=4.5, facecolors="none", edgecolors="#334155",
                linewidths=0.25, alpha=0.40, rasterized=True)
    sat_pr = sat.P_Pa.to_numpy(float) / 4251200.0
    sat_tr = sat.T_K.to_numpy(float) / 369.89
    ax0.plot(sat_pr, sat_tr, color="#111827", lw=1.35, zorder=8)
    ax0.plot(1.0, 1.0, marker="*", ms=10.5, mfc="#ef4444", mec="white",
             mew=0.7, zorder=12)
    selected_tr = 0.95
    ax0.axhline(selected_tr, color="#3dcc73", ls="--", lw=1.35)
    mechanism_arrow(ax0, (0.18, 0.22), (0.76, 0.22),
                    r"compression $P_r\uparrow$" "\nroot topology changes",
                    "#145f82", (0.48, 0.31), rad=-0.08)
    mechanism_arrow(ax0, (0.66, 0.46), (0.66, 0.82),
                    r"heating $T_r\uparrow$" "\nwedge collapses",
                    "#16854b", (0.69, 0.64), align="left")
    three_region = ax0.text(0.23, 0.54, "three real roots\nliquid / unstable / vapor",
                            transform=ax0.transAxes, fontsize=8.5, fontweight="bold",
                            color="#8a3f00", ha="center", va="center", zorder=11)
    three_region.set_path_effects([
        pe.Stroke(linewidth=3.0, foreground="white"), pe.Normal()
    ])
    one_region = ax0.text(0.82, 0.84, "one-root\nsupercritical region",
                          transform=ax0.transAxes, fontsize=8.5, fontweight="bold",
                          color="#1e4f82", ha="center", va="center", zorder=11)
    one_region.set_path_effects([
        pe.Stroke(linewidth=3.0, foreground="white"), pe.Normal()
    ])
    ax0.annotate("critical collapse", xy=(1.0, 1.0), xytext=(1.16, 1.08),
                 fontsize=7.6, color="#b4232f", fontweight="bold",
                 arrowprops={"arrowstyle": "->", "color": "#b4232f", "lw": 1.0})
    field_title(ax0, "a", "Peng–Robinson root-count field",
                f"121 × 151 = {len(root_map):,} states")
    cb = inset_colorbar(fig, ax0, im, "number of real PR roots", width="35%")
    cb.set_ticks([1, 3])
    cb.set_ticklabels(["one", "three"])
    ax0.set_xlabel(r"reduced pressure $P_r$", fontsize=9.5)
    ax0.set_ylabel(r"reduced temperature $T_r$", fontsize=9.5)
    ax0.tick_params(labelsize=8.2)
    style_axis(ax0, False)

    cut = root_map[np.isclose(root_map.Tr, selected_tr)].sort_values("Pr").copy()
    three = cut[cut.root_count == 3].copy()
    p_lo, p_hi = float(three.Pr.min()), float(three.Pr.max())
    psat = float(np.interp(selected_tr * 369.89, sat.T_K, sat.P_Pa) / 4251200.0)
    ax1.axvspan(p_lo, p_hi, color="#f59e0b", alpha=0.11, zorder=0)
    ax1.axvline(p_lo, color="#7c8795", ls=":", lw=1.0)
    ax1.axvline(p_hi, color="#7c8795", ls=":", lw=1.0)
    ax1.axvline(psat, color="#111827", ls="--", lw=1.15)
    branch_specs = [("Z0", "#2166ac", "liquid root", "-"),
                    ("Z1", "#6b7280", "unstable root", "--"),
                    ("Z2", "#b2182b", "vapor root", "-")]
    for col, color, label, ls in branch_specs:
        values = three[col].to_numpy(float)
        ax1.plot(three.Pr, values, color=color, ls=ls, lw=1.75, marker="o",
                 ms=2.5, markevery=3, mec="white", mew=0.35, zorder=5)
    ax1.fill_between(three.Pr, three.Z0, three.Z2, color="#f59e0b",
                     alpha=0.09, zorder=1)
    stable = np.where(
        (cut.root_count == 3) & (cut.Pr < psat), cut.Z2,
        np.where((cut.root_count == 3) & (cut.Pr >= psat), cut.Z0, cut.Z0),
    )
    left_stable = cut.Pr <= psat
    right_stable = cut.Pr >= psat
    ax1.plot(cut.loc[left_stable, "Pr"], stable[left_stable], color="#111827",
             lw=2.4, zorder=7)
    ax1.plot(cut.loc[right_stable, "Pr"], stable[right_stable], color="#111827",
             lw=2.4, zorder=7)
    psat_i = int(np.argmin(np.abs(three.Pr.to_numpy(float) - psat)))
    z_liq = float(three.Z0.iloc[psat_i])
    z_vap = float(three.Z2.iloc[psat_i])
    ax1.annotate("", xy=(psat, z_vap), xytext=(psat, z_liq),
                 arrowprops={"arrowstyle": "<->", "color": "#111827", "lw": 1.25})
    ax1.text(psat + 0.015, (z_liq + z_vap) / 2, "coexistence\nphase switch",
             fontsize=7.0, fontweight="bold", color="#111827", va="center")
    for x, y, text_value, color in [
        (0.60, 0.12, "liquid", "#2166ac"),
        (0.68, 0.29, "unstable", "#6b7280"),
        (0.61, 0.66, "vapor", "#b2182b"),
    ]:
        txt = ax1.text(x, y, text_value, color=color, fontsize=7.5,
                       fontweight="bold", ha="center")
        txt.set_path_effects([pe.Stroke(linewidth=2.5, foreground="white"), pe.Normal()])
    ax1.text(0.04, 0.06,
             f"three-root interval: {p_lo:.3f}–{p_hi:.3f}\n"
             + f"CoolProp coexistence: $P_r={psat:.3f}$\n"
             + "three algebraic roots ≠ three stable phases",
             transform=ax1.transAxes, fontsize=6.7, color="#334155",
             bbox={"boxstyle": "round,pad=0.24", "fc": "white", "ec": "#aeb8c2",
                   "lw": 0.7, "alpha": 0.90})
    curve_title(ax1, "b", r"phase roots at $T_r=0.95$")
    ax1.set_xlim(0.44, 0.88)
    ax1.set_ylim(0.05, 0.82)
    ax1.set_xlabel(r"reduced pressure $P_r$", fontsize=9.0)
    ax1.set_ylabel("compressibility root $Z$", fontsize=9.0, labelpad=1.5)
    ax1.tick_params(labelsize=8.0)
    style_axis(ax1)
    meta["peng_robinson_mechanism_detail"] = save_figure(
        fig, out, "fig9d_peng_robinson_phase_mechanisms_2d",
        {"root_field": ax0, "phase_roots": ax1},
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=OUT_DEFAULT)
    args = ap.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    set_paper_style()
    meta = {
        "description": "Framework-backed, data-driven 2-D publication figures and dense comparison plate",
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
    render_dense_field_plate(out, meta)
    render_split_knowledge_figures(out, meta)
    manifest = out / "render_manifest.json"
    manifest.write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in meta.items() if k not in ("description", "input_manifests")}, indent=2))


if __name__ == "__main__":
    main()
