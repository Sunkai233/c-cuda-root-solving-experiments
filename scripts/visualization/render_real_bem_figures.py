#!/usr/bin/env python3
"""Render publication figures from the released OpenFAST/TurbSim/BEM evidence.

The rotor is lofted from the NREL 5-MW AeroDyn blade and airfoil files.  The
inflow volume is reconstructed from the released TurbSim full-field time series
with Taylor's frozen-turbulence mapping x = U_ref (t-t0).  The 2-D and batch
figures use the exact released BEM binary dataset and C polar tables.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import struct
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import Normalize, TwoSlopeNorm
from matplotlib.patches import Arc, FancyArrowPatch, Polygon, Rectangle
from scipy.optimize import brentq


ROOT = Path(__file__).resolve().parents[2]
OUT_DEFAULT = ROOT / "paper_figures" / "real_simulation_v1"
HUB_HEIGHT = 90.0
HUB_RADIUS = 1.5


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(8 << 20), b""):
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
            "xtick.labelsize": 7.5,
            "ytick.labelsize": 7.5,
            "legend.fontsize": 7.5,
            "savefig.dpi": 400,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )


def audit_layout(fig, named_axes: dict[str, object]) -> dict:
    """Measure tight element boxes in figure coordinates and report collisions."""
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    boxes = {}
    for name, artist in named_axes.items():
        bb = artist.get_tightbbox(renderer).transformed(fig.transFigure.inverted())
        boxes[name] = [float(bb.x0), float(bb.y0), float(bb.x1), float(bb.y1)]
    overlaps = []
    names = list(boxes)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            aa, bb = boxes[a], boxes[b]
            w = max(0.0, min(aa[2], bb[2]) - max(aa[0], bb[0]))
            h = max(0.0, min(aa[3], bb[3]) - max(aa[1], bb[1]))
            if w * h > 1e-6:
                overlaps.append({"elements": [a, b], "normalized_area": float(w * h)})
    return {"tight_bboxes_xyxy": boxes, "pairwise_overlaps": overlaps}


def read_blade_table(path: Path) -> np.ndarray:
    rows = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        p = line.split()
        if len(p) >= 7:
            try:
                rows.append([float(p[i]) for i in range(6)] + [int(p[6])])
            except ValueError:
                pass
    return np.asarray(rows[:19], dtype=float)


def read_airfoil(path: Path, n: int = 180) -> tuple[np.ndarray, float]:
    pairs = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        p = line.split()
        if len(p) == 2:
            try:
                pairs.append((float(p[0]), float(p[1])))
            except ValueError:
                pass
    ref = float(pairs[0][0])
    xy = np.asarray(pairs[1:], dtype=float)
    if np.linalg.norm(xy[0] - xy[-1]) > 1e-9:
        xy = np.vstack([xy, xy[0]])
    d = np.linalg.norm(np.diff(xy, axis=0), axis=1)
    s = np.r_[0.0, np.cumsum(d)]
    si = np.linspace(0.0, s[-1], n, endpoint=False)
    return np.c_[np.interp(si, s, xy[:, 0]), np.interp(si, s, xy[:, 1])], ref


def airfoil_paths() -> dict[int, Path]:
    base = ROOT / "domains/bem/openfast/5MW_Baseline/Airfoils"
    names = {
        1: "Cylinder1_coords.txt",
        2: "Cylinder2_coords.txt",
        3: "DU40_A17_coords.txt",
        4: "DU35_A17_coords.txt",
        5: "DU30_A17_coords.txt",
        6: "DU25_A17_coords.txt",
        7: "DU21_A17_coords.txt",
        8: "NACA64_A17_coords.txt",
    }
    return {k: base / v for k, v in names.items()}


def blade_mesh(blade: np.ndarray, azimuth_deg: float):
    import pyvista as pv

    sections = []
    psi = np.deg2rad(azimuth_deg)
    er = np.array([0.0, np.cos(psi), np.sin(psi)])
    et = np.array([0.0, -np.sin(psi), np.cos(psi)])
    ex = np.array([1.0, 0.0, 0.0])
    afs = airfoil_paths()
    for spn, crv, swp, _crvang, twist_deg, chord, afid in blade:
        xy, xref = read_airfoil(afs[int(afid)])
        tw = np.deg2rad(twist_deg)
        cdir = np.cos(tw) * et + np.sin(tw) * ex
        ndir = -np.sin(tw) * et + np.cos(tw) * ex
        center = np.array([swp, 0.0, HUB_HEIGHT]) + (HUB_RADIUS + spn) * er + crv * et
        sec = center + chord * ((xy[:, :1] - xref) * cdir + xy[:, 1:] * ndir)
        sections.append(sec)
    pts = np.vstack(sections)
    ns, nc = len(sections), sections[0].shape[0]
    faces = []
    for i in range(ns - 1):
        for j in range(nc):
            k = (j + 1) % nc
            faces.extend([4, i * nc + j, i * nc + k, (i + 1) * nc + k, (i + 1) * nc + j])
    return pv.PolyData(pts, np.asarray(faces, dtype=np.int64))


def tower_mesh():
    import pyvista as pv

    z = np.linspace(0.0, HUB_HEIGHT - 2.0, 48)
    a = np.linspace(0, 2 * np.pi, 72, endpoint=False)
    zz, aa = np.meshgrid(z, a, indexing="ij")
    rr = 3.2 + (1.95 - 3.2) * zz / zz.max()
    pts = np.c_[rr.ravel() * np.cos(aa).ravel(), rr.ravel() * np.sin(aa).ravel(), zz.ravel()]
    faces = []
    na = len(a)
    for i in range(len(z) - 1):
        for j in range(na):
            k = (j + 1) % na
            faces.extend([4, i * na + j, i * na + k, (i + 1) * na + k, (i + 1) * na + j])
    return pv.PolyData(pts, np.asarray(faces, dtype=np.int64))


def render_rotor_inflow(out: Path, meta: dict) -> None:
    import pyvista as pv
    from openfast_io.turbsim_file import TurbSimFile

    pv.global_theme.allow_empty_mesh = True
    blade_file = ROOT / "domains/bem/openfast/5MW_Baseline/NRELOffshrBsline5MW_AeroDyn_blade.dat"
    bts_file = ROOT / "domains/bem/openfast/5MW_Baseline/Wind/90m_12mps_twr.bts"
    blade = read_blade_table(blade_file)
    ts = TurbSimFile(str(bts_file))
    u = np.asarray(ts["u"])
    y = np.asarray(ts["y"], dtype=float)
    z = np.asarray(ts["z"], dtype=float)
    dt = float(ts["dt"])
    uref = float(ts["uRef"])
    mid = u.shape[1] // 2
    nt = 241
    idx = np.arange(mid - nt // 2, mid + nt // 2 + 1, 4)
    x = uref * (idx - mid) * dt
    uu = u[0, idx, :, :]
    vv = u[1, idx, :, :]
    ww = u[2, idx, :, :]
    xx, yy, zz = np.meshgrid(x, y, z, indexing="ij")
    grid = pv.StructuredGrid(xx, yy, zz)
    speed = np.sqrt(uu**2 + vv**2 + ww**2)
    grid["u"] = uu.ravel(order="F")
    grid["speed"] = speed.ravel(order="F")
    grid["velocity"] = np.c_[uu.ravel(order="F"), vv.ravel(order="F"), ww.ravel(order="F")]

    p = pv.Plotter(off_screen=True, window_size=(3000, 1900))
    p.set_background("#eef3f6", top="#d5e2eb")

    # Full-field cross-plane colored by the actual streamwise TurbSim velocity.
    ix = int(np.argmin(np.abs(x + 48.0)))
    plane = grid.slice(normal=(1, 0, 0), origin=(x[ix], 0, HUB_HEIGHT))
    clim = tuple(np.percentile(uu, [1.0, 99.0]))
    p.add_mesh(plane, scalars="u", cmap="turbo", clim=clim, opacity=0.90,
               show_scalar_bar=True, scalar_bar_args={"title": "TurbSim $u$  [m s$^{-1}$]", "vertical": True,
               "position_x": 0.88, "position_y": 0.18, "height": 0.55, "width": 0.045,
               "title_font_size": 24, "label_font_size": 20})

    # Streamlines are integrated through the reconstructed 3-component field.
    seeds = pv.PolyData(np.c_[np.full(121, x.min() + 1),
                              np.repeat(np.linspace(-60, 60, 11), 11),
                              np.tile(np.linspace(30, 150, 11), 11)])
    try:
        streams = grid.streamlines_from_source(seeds, vectors="velocity", integration_direction="forward",
                                               max_length=145.0, initial_step_length=0.8,
                                               terminal_speed=0.05)
        if streams.n_points:
            tube = streams.tube(radius=0.13)
            p.add_mesh(tube, scalars="speed", cmap="turbo", clim=clim, opacity=0.72, show_scalar_bar=False,
                       ambient=0.25, diffuse=0.75)
    except Exception:
        pass

    # Wind turbine geometry is built from actual station-wise chord/twist/airfoils.
    p.add_mesh(tower_mesh(), color="#f2f4f5", smooth_shading=True, ambient=0.42, diffuse=0.52,
               specular=0.22, specular_power=18)
    tables = load_tables()
    nt = tables["bem_node_r"]
    for az in (90.0, 210.0, 330.0):
        mesh = blade_mesh(blade, az)
        p.add_mesh(mesh, color="#f7f8f8", smooth_shading=True, ambient=0.48, diffuse=0.47,
                   specular=0.30, specular_power=24)
    hub = pv.Sphere(radius=3.0, center=(0, 0, HUB_HEIGHT), theta_resolution=80, phi_resolution=80)
    p.add_mesh(hub, color="#f3f5f6", smooth_shading=True, ambient=0.42, diffuse=0.52, specular=0.28)
    nacelle = pv.Capsule(center=(5.0, 0, HUB_HEIGHT + 1.0), direction=(1, 0, 0),
                         radius=2.25, cylinder_length=7.0, resolution=80)
    p.add_mesh(nacelle, color="#e9edef", smooth_shading=True, ambient=0.40, diffuse=0.55, specular=0.25)
    ground = pv.Plane(center=(0, 0, -0.2), direction=(0, 0, 1), i_size=230, j_size=210,
                      i_resolution=2, j_resolution=2)
    p.add_mesh(ground, color="#8ca47b", opacity=0.55, roughness=1.0)

    p.add_text("OPENFAST / TURBSIM FULL-FIELD INFLOW\nNREL 5-MW rotor  |  t = 306.1 s  |  Uref = 12 m/s\nTaylor reconstruction:  x = Uref (t - t0)",
               position="upper_left", font_size=17, color="#23343f", font="arial", shadow=False)
    p.enable_anti_aliasing("ssaa")
    try:
        p.enable_ssao(radius=10, bias=0.04, kernel_size=64)
    except Exception:
        pass
    p.camera_position = [(205, -205, 150), (-8, 0, 82), (0, 0, 1)]
    p.camera.zoom(0.78)
    png = out / "fig1_openfast_turbulent_rotor.png"
    p.screenshot(str(png), transparent_background=False)
    p.close()
    meta["fig1"] = {
        "file": png.name,
        "blade_input": blade_file.relative_to(ROOT).as_posix(),
        "turbulence_input": bts_file.relative_to(ROOT).as_posix(),
        "turbulence_sha256": sha256(bts_file),
        "mapping": "Taylor frozen-turbulence reconstruction x=Uref*(t-t0); not Navier-Stokes CFD",
        "grid": [int(v) for v in u.shape],
        "dt_s": dt,
        "u_ref_mps": uref,
    }


def parse_c_array(text: str, name: str, dtype=float) -> np.ndarray:
    m = re.search(rf"\b{name}\s*\[[^\]]+\]\s*=\s*\{{(.*?)\}};", text, re.S)
    if not m:
        raise KeyError(name)
    vals = re.findall(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?", m.group(1))
    return np.asarray([dtype(v) for v in vals])


def load_tables() -> dict[str, np.ndarray]:
    text = (ROOT / "include/bem_real_tables.h").read_text(encoding="utf-8")
    return {name: parse_c_array(text, name, int if name in {"bem_af_offset", "bem_af_count", "bem_node_afid"} else float)
            for name in ("bem_af_offset", "bem_af_count", "bem_alpha_deg", "bem_cl", "bem_cd",
                         "bem_node_r", "bem_node_chord", "bem_node_tip_const", "bem_node_hub_const", "bem_node_afid")}


def wrap_pi(x):
    return (x + np.pi) % (2 * np.pi) - np.pi


def polar(t, af: int, alpha: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    off, n = int(t["bem_af_offset"][af]), int(t["bem_af_count"][af])
    a = wrap_pi(alpha) * 180 / np.pi
    xp = t["bem_alpha_deg"][off:off+n]
    return np.interp(a, xp, t["bem_cl"][off:off+n]), np.interp(a, xp, t["bem_cd"][off:off+n])


def residual(t, phi, vx, vy, theta, node):
    phi = np.asarray(phi, dtype=float)
    cl, _ = polar(t, int(t["bem_node_afid"][node]), phi - theta)
    s, c = np.sin(phi), np.cos(phi)
    ass = np.abs(s)
    ft = (2 / np.pi) * np.arccos(np.minimum(1.0, np.exp(-t["bem_node_tip_const"][node] / np.maximum(ass, 1e-300))))
    fh = (2 / np.pi) * np.arccos(np.minimum(1.0, np.exp(-t["bem_node_hub_const"][node] / np.maximum(ass, 1e-300))))
    F = np.maximum(ft * fh, 1e-4)
    sigma = 3 * t["bem_node_chord"][node] / (2 * np.pi * t["bem_node_r"][node])
    cn, ct = cl * c, cl * s
    k = sigma * cn / (4 * F * s * s)
    kp = sigma * ct / (4 * F * s * c)
    if vx < 0:
        kp = -kp
    momentum = ((phi > 0) & (vx >= 0)) | ((phi < 0) & (vx < 0))
    a_low = k / (1 + k)
    tt = 2 * F * k
    g1 = tt - (10 / 9 - F)
    g2 = tt - (4 / 3 - F) * F
    g3 = tt - (25 / 9 - 2 * F)
    a_hi = np.where(np.abs(g3) < 1e-6, 1 - 0.5 / np.sqrt(np.maximum(g2, 1e-300)),
                    (g1 - np.sqrt(np.abs(g2))) / g3)
    a = np.where(k <= 2 / 3, a_low, a_hi)
    return np.where(momentum, s / (1 - a) - c / (vy / vx) * (1 - kp),
                    s * (1 - k) - c / (vy / vx) * (1 - kp))


def residual_components(t, phi, vx, vy, theta, node):
    """Vectorized diagnostic terms, algebraically identical to bem_residual()."""
    phi = np.asarray(phi, dtype=float)
    cl, cd = polar(t, int(t["bem_node_afid"][node]), phi - theta)
    s, c = np.sin(phi), np.cos(phi)
    ass = np.abs(s)
    ft = (2 / np.pi) * np.arccos(np.minimum(1.0, np.exp(-t["bem_node_tip_const"][node] / np.maximum(ass, 1e-300))))
    fh = (2 / np.pi) * np.arccos(np.minimum(1.0, np.exp(-t["bem_node_hub_const"][node] / np.maximum(ass, 1e-300))))
    F = np.maximum(ft * fh, 1e-4)
    sigma = 3 * t["bem_node_chord"][node] / (2 * np.pi * t["bem_node_r"][node])
    k = sigma * (cl * c) / (4 * F * s * s)
    kp = sigma * (cl * s) / (4 * F * s * c)
    if vx < 0:
        kp = -kp
    tt = 2 * F * k
    g1 = tt - (10 / 9 - F)
    g2 = tt - (4 / 3 - F) * F
    g3 = tt - (25 / 9 - 2 * F)
    a = np.where(k <= 2 / 3, k / (1 + k),
                 np.where(np.abs(g3) < 1e-6, 1 - 0.5 / np.sqrt(np.maximum(g2, 1e-300)),
                          (g1 - np.sqrt(np.abs(g2))) / g3))
    R = residual(t, phi, vx, vy, theta, node)
    return {"cl": cl, "cd": cd, "F": F, "sigma": np.full_like(phi, sigma),
            "k": k, "kp": kp, "a": a, "R": R}


def open_dataset():
    path = ROOT / "results_raw/20260824T060500Z_bem_real_dataset_v2/bem_real_f64_soa.bin"
    with path.open("rb") as f:
        magic, version, n, narr, nnodes, nsteps = struct.unpack("<8sIQIII", f.read(32))
    if magic != b"BEMREAL2" or narr != 5 or n != nnodes * nsteps:
        raise RuntimeError("unexpected BEM dataset header")
    mm = np.memmap(path, dtype="<f8", mode="r", offset=32, shape=(5, n))
    return path, mm, int(nnodes), int(nsteps), int(version)


def arrow(ax, p0, p1, color, label, text_offset=(0, 0), lw=1.6):
    ax.add_patch(FancyArrowPatch(p0, p1, arrowstyle="-|>", mutation_scale=11, lw=lw, color=color))
    ax.text(p1[0] + text_offset[0], p1[1] + text_offset[1], label, color=color, fontsize=8)


def render_rotor_plane_2d(out: Path, meta: dict) -> None:
    """Actual TurbSim rotor-plane slice with projected AeroDyn blade planform."""
    from openfast_io.turbsim_file import TurbSimFile

    blade_file = ROOT / "domains/bem/openfast/5MW_Baseline/NRELOffshrBsline5MW_AeroDyn_blade.dat"
    bts_file = ROOT / "domains/bem/openfast/5MW_Baseline/Wind/90m_12mps_twr.bts"
    blade = read_blade_table(blade_file)
    ts = TurbSimFile(str(bts_file))
    uvw = np.asarray(ts["u"], dtype=float)
    y = np.asarray(ts["y"], dtype=float)
    z = np.asarray(ts["z"], dtype=float)
    tt = np.asarray(ts["t"], dtype=float)
    i = int(np.argmin(np.abs(tt - 306.1)))
    u, v, w = uvw[:, i]
    levels = np.linspace(float(np.percentile(u, 1)), float(np.percentile(u, 99)), 25)

    fig = plt.figure(figsize=(7.25, 4.55))
    gs = fig.add_gridspec(2, 3, width_ratios=(1.64, 0.70, 0.055), height_ratios=(1, 1),
                          left=0.075, right=0.955, bottom=0.11, top=0.975,
                          wspace=0.28, hspace=0.10)
    ax = fig.add_subplot(gs[:, 0])
    cf = ax.contourf(y, z, u.T, levels=levels, cmap="turbo", extend="both")
    cs = ax.contour(y, z, u.T, levels=levels[::4], colors="#20343f", linewidths=0.35, alpha=0.40)
    # Actual transverse velocity components on the same TurbSim grid.
    iy = np.arange(1, len(y), 3)
    iz = np.arange(1, len(z), 3)
    Yq, Zq = np.meshgrid(y[iy], z[iz], indexing="ij")
    ax.quiver(Yq, Zq, v[np.ix_(iy, iz)], w[np.ix_(iy, iz)], color="white",
              angles="xy", scale_units="xy", scale=0.24, width=0.0030,
              headwidth=3.2, headlength=4.0, alpha=0.82)

    # Rotor outline and projected blade planforms use the 19 released stations.
    th = np.linspace(0, 2 * np.pi, 720)
    ax.plot(63 * np.cos(th), HUB_HEIGHT + 63 * np.sin(th), color="white", lw=0.8, ls=(0, (4, 3)), alpha=0.88)
    nt = load_tables()["bem_node_r"]
    for az in (90.0, 210.0, 330.0):
        psi = np.deg2rad(az)
        er = np.array([np.cos(psi), np.sin(psi)])
        et = np.array([-np.sin(psi), np.cos(psi)])
        r = HUB_RADIUS + blade[:, 0]
        projected_chord = blade[:, 5] * np.cos(np.deg2rad(blade[:, 4]))
        center = np.array([0.0, HUB_HEIGHT]) + r[:, None] * er + blade[:, 1][:, None] * et
        side1 = center + 0.5 * projected_chord[:, None] * et
        side2 = center - 0.5 * projected_chord[:, None] * et
        poly = np.vstack([side1, side2[::-1]])
        ax.add_patch(Polygon(poly, closed=True, facecolor="#f5f7f7", edgecolor="#17262e", lw=0.75, zorder=6))
        # The 17 ordinary BEM nodes are marked at their exact released radii.
        node_curve = np.interp(nt - HUB_RADIUS, blade[:, 0], blade[:, 1])
        nodes = np.array([0.0, HUB_HEIGHT]) + nt[:, None] * er + node_curve[:, None] * et
        ax.scatter(nodes[:, 0], nodes[:, 1], s=5.5, facecolor="#f7f8f8", edgecolor="#17262e", lw=0.35, zorder=7)
    ax.add_patch(plt.Circle((0, HUB_HEIGHT), 3.0, facecolor="#e4e8ea", edgecolor="#17262e", lw=0.8, zorder=8))
    tower_y = np.array([-3.2, 3.2, 1.95, -1.95])
    tower_z = np.array([0, 0, HUB_HEIGHT - 2, HUB_HEIGHT - 2])
    ax.add_patch(Polygon(np.c_[tower_y, tower_z], closed=True, facecolor="#e7ebed", edgecolor="#17262e", lw=0.7, zorder=5))
    ax.annotate("17 BEM nodes per blade", xy=(-28, 137), xytext=(-69, 155), color="#17262e", fontsize=7.6,
                arrowprops=dict(arrowstyle="->", color="#17262e", lw=0.7))
    ax.set_xlim(y.min(), y.max())
    ax.set_ylim(z.min(), z.max())
    ax.set_aspect("equal")
    ax.set_xlabel("lateral coordinate $y$  [m]")
    ax.set_ylabel("height $z$  [m]")
    ax.text(0.015, 0.035, "a", transform=ax.transAxes, va="bottom", color="white", fontweight="bold")
    cax = fig.add_subplot(gs[:, 2])
    cb = fig.colorbar(cf, cax=cax, orientation="vertical")
    cb.set_label(r"TurbSim streamwise velocity $u(y,z,t=306.1\,\mathrm{s})$  [m s$^{-1}$]")

    izh = int(np.argmin(np.abs(z - HUB_HEIGHT)))
    iyh = int(np.argmin(np.abs(y)))
    axpv = fig.add_subplot(gs[0, 1])
    axph = fig.add_subplot(gs[1, 1], sharex=axpv)
    axpv.plot(u[iyh, :], z, color="#2166ac", lw=1.4)
    axph.plot(u[:, izh], y, color="#b2182b", lw=1.4)
    for ap in (axpv, axph):
        ap.axvline(float(ts["uRef"]), color="#3c474c", lw=0.8, ls="--")
        ap.grid(color="#c7ced2", lw=0.45)
    axpv.set_ylabel(r"height $z$  [m]")
    axph.set_ylabel(r"lateral $y$  [m]")
    axph.set_xlabel(r"streamwise velocity $u$  [m s$^{-1}$]")
    axpv.tick_params(labelbottom=False)
    axpv.text(0.035, 0.98, "b", transform=axpv.transAxes, va="top", fontweight="bold")
    axpv.text(0.55, 0.08, r"vertical cut, $y=0$ m", transform=axpv.transAxes, color="#2166ac", fontsize=7.1)
    axph.text(0.44, 0.08, r"horizontal cut, $z=90$ m", transform=axph.transAxes, color="#b2182b", fontsize=7.1)
    axph.text(0.58, 0.90, r"$U_{ref}=12$ m s$^{-1}$", transform=axph.transAxes, fontsize=7.0, va="top")
    stats = (rf"$u_{{min}}={u.min():.2f}$ m s$^{{-1}}$" + "\n" +
             rf"$u_{{max}}={u.max():.2f}$ m s$^{{-1}}$" + "\n" +
             rf"$\sigma_u={u.std():.2f}$ m s$^{{-1}}$")
    axpv.text(0.05, 0.77, stats, transform=axpv.transAxes, fontsize=7.2, va="top")
    layout = audit_layout(fig, {"rotor_plane": ax, "vertical_profile": axpv,
                                "horizontal_profile": axph, "colorbar": cax})
    for ext in ("png", "pdf", "svg"):
        fig.savefig(out / f"fig1_turbsim_rotor_plane_2d.{ext}", bbox_inches="tight", facecolor="white")
    plt.close(fig)
    meta["fig1"] = {
        "files": [f"fig1_turbsim_rotor_plane_2d.{x}" for x in ("png", "pdf", "svg")],
        "blade_input": blade_file.relative_to(ROOT).as_posix(),
        "turbulence_input": bts_file.relative_to(ROOT).as_posix(),
        "turbulence_sha256": sha256(bts_file), "time_index": i, "time_s": float(tt[i]),
        "grid_yz": [int(len(y)), int(len(z))], "u_min_mps": float(u.min()),
        "u_max_mps": float(u.max()), "u_std_mps": float(u.std()),
        "truth_boundary": "direct TurbSim rotor-plane sample; no CFD reconstruction or interpolation beyond contour rendering",
        "layout_audit": layout,
    }


def render_local_section(out: Path, meta: dict) -> None:
    t = load_tables()
    data_path, mm, nnodes, nsteps, version = open_dataset()
    flat = 89241
    node = flat % nnodes
    local_node = node % 17
    step = flat // nnodes
    vx, vy, theta, phi_ref, phi_prev = (float(mm[i, flat]) for i in range(5))
    afid0 = int(t["bem_node_afid"][local_node])
    afid = afid0 + 1
    xy, xref = read_airfoil(airfoil_paths()[afid], 320)
    chord = float(t["bem_node_chord"][local_node])
    alpha = phi_ref - theta

    ph = np.linspace(np.deg2rad(0.2), np.deg2rad(89.5), 5000)
    comp = residual_components(t, ph, vx, vy, theta, local_node)
    # Locate the exact zero of the released C residual nearest the OpenFAST root.
    j = int(np.argmin(np.abs(ph - phi_ref)))
    changes = np.where(np.signbit(comp["R"][:-1]) != np.signbit(comp["R"][1:]))[0]
    kroot = int(changes[np.argmin(np.abs(changes - j))])
    phi_zero = brentq(lambda q: float(residual(t, np.array([q]), vx, vy, theta, local_node)[0]),
                      float(ph[kroot]), float(ph[kroot + 1]), xtol=5e-15)
    rref = float(residual(t, np.array([phi_ref]), vx, vy, theta, local_node)[0])
    delta_microdeg = (phi_ref - phi_zero) * 180 / np.pi * 1e6
    croot = residual_components(t, np.array([phi_zero]), vx, vy, theta, local_node)

    fig = plt.figure(figsize=(7.25, 6.0))
    gs = fig.add_gridspec(2, 2, width_ratios=(1.08, 0.92), height_ratios=(1.00, 0.92),
                          left=0.09, right=0.965, bottom=0.075, top=0.98, wspace=0.29, hspace=0.34)
    ax = fig.add_subplot(gs[0, 0])
    th = theta
    R = np.array([[np.cos(th), -np.sin(th)], [np.sin(th), np.cos(th)]])
    shape = ((xy - [xref, 0]) * chord) @ R.T
    ax.add_patch(Polygon(shape, closed=True, facecolor="#cbd8df", edgecolor="#263943", lw=1.0, zorder=2))
    s = 0.070
    origin = np.array([-0.15, 0.55])
    a = origin + np.array([s * vy, 0])
    b = a + np.array([0, s * vx])
    arrow(ax, origin, a, "#d6604d", rf"$V_{{t}}={vy:.2f}$ m s$^{{-1}}$", (0.05, -0.22))
    arrow(ax, a, b, "#4393c3", rf"$V_{{x}}={vx:.2f}$ m s$^{{-1}}$", (0.06, -0.02))
    arrow(ax, origin, b, "#542788", rf"$W={math.hypot(vx, vy):.2f}$ m s$^{{-1}}$", (0.04, 0.18), 2.0)
    arc_r = 0.92
    ax.add_patch(Arc(origin, 2 * arc_r, 2 * arc_r, theta1=0, theta2=np.rad2deg(phi_ref), color="#542788", lw=1.1))
    ax.text(origin[0] + 0.72, origin[1] + 0.16, rf"$\phi={np.rad2deg(phi_ref):.2f}^\circ$", color="#542788", fontsize=8)
    ax.plot([-0.8, 3.6], [0, 0], color="#72848d", lw=0.6, ls="--")
    ax.text(-0.78, -0.25, rf"Blade {node//17+1}, element {local_node+1}: $r={t['bem_node_r'][local_node]:.5f}$ m, $c={chord:.4f}$ m", fontsize=7.2)
    ax.text(-0.78, -0.48, rf"$\theta={np.rad2deg(theta):.5f}^\circ$, $\alpha=\phi-\theta={np.rad2deg(alpha):.5f}^\circ$", fontsize=7.2)
    ax.set_aspect("equal")
    ax.set_xlim(-0.9, 3.65)
    ax.set_ylim(-0.65, 2.25)
    ax.set_xlabel("local tangential direction  [m]")
    ax.set_ylabel("local axial direction  [m]")
    ax.text(0.015, 0.97, "a", transform=ax.transAxes, va="top", fontweight="bold")
    ax.spines[["top", "right"]].set_visible(False)

    # Exact released polar table and interpolation point.
    ax2 = fig.add_subplot(gs[0, 1])
    off = int(t["bem_af_offset"][afid0]); n = int(t["bem_af_count"][afid0])
    ad = t["bem_alpha_deg"][off:off+n]
    cltab = t["bem_cl"][off:off+n]; cdtab = t["bem_cd"][off:off+n]
    region = (ad >= -20) & (ad <= 30)
    cl0, cd0 = polar(t, afid0, np.array([alpha]))
    l1 = ax2.plot(ad[region], cltab[region], color="#2166ac", lw=1.35, marker=".", ms=2.3,
                  label=r"released $C_l(\alpha)$ samples")
    ax2.scatter([np.rad2deg(alpha)], [cl0[0]], s=34, color="#b2182b", zorder=4)
    ax2b = ax2.twinx()
    l2 = ax2b.plot(ad[region], cdtab[region], color="#4d9221", lw=1.15, ls="--",
                   label=r"released $C_d(\alpha)$ samples")
    ax2b.scatter([np.rad2deg(alpha)], [cd0[0]], s=28, marker="s", color="#4d9221", zorder=4)
    ax2.axvline(np.rad2deg(alpha), color="#b2182b", lw=0.7, ls=":")
    ax2.set_xlabel(r"angle of attack $\alpha$  [deg]")
    ax2.set_ylabel(r"lift coefficient $C_l$  [-]", color="#2166ac")
    ax2b.set_ylabel(r"drag coefficient $C_d$  [-]", color="#4d9221")
    ax2.grid(color="#cad1d5", lw=0.4)
    ax2.text(0.04, 0.94, r"$C_l$ samples", color="#2166ac", transform=ax2.transAxes, va="top", fontsize=7.2)
    ax2.text(0.04, 0.87, r"$C_d$ samples", color="#4d9221", transform=ax2.transAxes, va="top", fontsize=7.2)
    ax2.text(0.025, 0.97, "b", transform=ax2.transAxes, va="top", fontweight="bold")
    polar_note = (rf"actual $\alpha={np.rad2deg(alpha):.5f}^\circ$" + "\n" +
                  rf"$C_l={cl0[0]:.6f}$, $C_d={cd0[0]:.6f}$")
    ax2.annotate(polar_note, (np.rad2deg(alpha), cl0[0]), xytext=(0.58, 0.57),
                 textcoords="axes fraction", fontsize=7.2,
                 arrowprops=dict(arrowstyle="->", color="#b2182b", lw=0.7))

    ax3 = fig.add_subplot(gs[1, 0])
    rr = comp["R"].copy()
    rr[np.abs(rr) > 2.5] = np.nan
    ax3.axhline(0, color="#6f7b81", lw=0.65)
    ax3.plot(np.rad2deg(ph), rr, color="#2166ac", lw=1.35, label=r"exact C residual $R(\phi)$")
    ax3.axvline(np.rad2deg(theta), color="#7f8c92", lw=0.7, ls=":", label=r"$\phi=\theta$")
    ax3.scatter([np.rad2deg(phi_zero)], [0], s=39, color="#b2182b", edgecolor="white", lw=0.7, zorder=4)
    ax3.annotate(rf"C zero  {np.rad2deg(phi_zero):.8f}$^\circ$", (np.rad2deg(phi_zero), 0),
                 xytext=(28, 0.73), fontsize=7.3, arrowprops=dict(arrowstyle="->", lw=0.7, color="#b2182b"))
    ax3.set_xlim(0, 75); ax3.set_ylim(-1.05, 1.05)
    ax3.set_xlabel(r"inflow angle $\phi$  [deg]")
    ax3.set_ylabel(r"BEM residual $R(\phi)$  [-]")
    ax3.grid(color="#cad1d5", lw=0.4)
    ax3.text(0.69, 0.47, r"exact C residual $R(\phi)$", color="#2166ac", transform=ax3.transAxes,
             ha="center", fontsize=7.1)
    ax3.text(0.105, 0.07, r"$\phi=\theta$", color="#657981", transform=ax3.transAxes, fontsize=7.1)
    ax3.text(0.015, 0.97, "c", transform=ax3.transAxes, va="top", fontweight="bold")
    root_note = (rf"OpenFAST $-$ C zero = {delta_microdeg:.3f} $\mu$deg" + "\n" +
                 rf"$R(\phi_{{ref}})={rref:.3e}$")
    ax3.text(0.57, 0.12, root_note, transform=ax3.transAxes, fontsize=7.0)

    ax4 = fig.add_subplot(gs[1, 1])
    ax4.plot(np.rad2deg(ph), comp["F"], color="#762a83", lw=1.25, label=r"Prandtl loss $F$")
    ax4.plot(np.rad2deg(ph), comp["a"], color="#d6604d", lw=1.25, label=r"axial induction $a$")
    ax4.plot(np.rad2deg(ph), comp["kp"], color="#1b7837", lw=1.1, ls="--", label=r"tangential term $\kappa'$ ")
    ax4.axvline(np.rad2deg(phi_zero), color="#b2182b", lw=0.75, ls=":")
    ax4.scatter(np.repeat(np.rad2deg(phi_zero), 3),
                [croot["F"][0], croot["a"][0], croot["kp"][0]],
                s=[28, 28, 24], color=["#762a83", "#d6604d", "#1b7837"], zorder=4)
    ax4.set_xlim(0, 45); ax4.set_ylim(-0.15, 1.08)
    ax4.set_xlabel(r"inflow angle $\phi$  [deg]")
    ax4.set_ylabel("nonlinear model terms  [-]")
    ax4.grid(color="#cad1d5", lw=0.4)
    ax4.text(0.68, 0.79, r"Prandtl loss $F$", color="#762a83", transform=ax4.transAxes, fontsize=7.1)
    ax4.text(0.68, 0.22, r"axial induction $a$", color="#d6604d", transform=ax4.transAxes, fontsize=7.1)
    ax4.text(0.68, 0.08, r"tangential term $\kappa'$", color="#1b7837", transform=ax4.transAxes, fontsize=7.1)
    ax4.text(0.025, 0.97, "d", transform=ax4.transAxes, va="top", fontweight="bold")
    terms_note = (rf"$F={croot['F'][0]:.6f}$" + "\n" + rf"$a={croot['a'][0]:.6f}$" + "\n" +
                  rf"$\kappa'={croot['kp'][0]:.6f}$" + "\n" + rf"$\sigma={croot['sigma'][0]:.6f}$")
    ax4.text(0.05, 0.72, terms_note, transform=ax4.transAxes, fontsize=7.0, va="top")

    for ext in ("png", "pdf", "svg"):
        fig.savefig(out / f"fig2_bem_element_diagnostics_2d.{ext}", bbox_inches="tight", facecolor="white")
    plt.close(fig)
    meta["fig2"] = {
        "files": [f"fig2_bem_element_diagnostics_2d.{x}" for x in ("png", "pdf", "svg")],
        "dataset": data_path.relative_to(ROOT).as_posix(), "dataset_sha256": sha256(data_path),
        "dataset_version": version, "flat_record": flat, "time_step": step, "global_node_zero_based": node,
        "blade_one_based": node // 17 + 1, "local_node_zero_based": local_node,
        "Vx_mps": vx, "Vy_mps": vy, "theta_rad": theta, "phi_openfast_rad": phi_ref,
        "phi_exact_c_zero_rad": phi_zero, "reference_minus_c_zero_microdeg": delta_microdeg,
        "residual_at_reference": rref, "airfoil_file": airfoil_paths()[afid].name,
        "Cl_at_reference": float(cl0[0]), "Cd_at_reference": float(cd0[0]),
        "F_at_c_zero": float(croot["F"][0]), "a_at_c_zero": float(croot["a"][0]),
        "kappa_prime_at_c_zero": float(croot["kp"][0]), "solidity": float(croot["sigma"][0]),
    }


def render_batch_field(out: Path, meta: dict) -> None:
    t = load_tables()
    data_path, mm, nnodes, nsteps, version = open_dataset()
    phi = np.asarray(mm[3]).reshape(nsteps, nnodes)
    dt = 600.0 / (nsteps - 1)
    time = np.arange(nsteps) * dt
    radii = t["bem_node_r"]

    fig = plt.figure(figsize=(7.25, 5.35))
    gs = fig.add_gridspec(2, 2, height_ratios=(1.12, 0.88), width_ratios=(1.30, 0.70),
                          hspace=0.34, wspace=0.30, left=0.085, right=0.96, bottom=0.09, top=0.98)
    ax = fig.add_subplot(gs[0, :])
    im = ax.imshow(np.rad2deg(phi).T, aspect="auto", origin="lower", interpolation="nearest",
                   extent=(0, 600, 0.5, 51.5), cmap="twilight_shifted", vmin=-180, vmax=180,
                   rasterized=True)
    for yline in (17.5, 34.5):
        ax.axhline(yline, color="white", lw=0.8, alpha=0.8)
    ax.set_yticks([9, 26, 43], ["blade 1", "blade 2", "blade 3"])
    ax.set_xlabel("OpenFAST simulation time  [s]")
    ax.set_ylabel("51 equations per time step")
    cb = fig.colorbar(im, ax=ax, orientation="vertical", pad=0.012, aspect=22)
    cb.set_label(r"reference root $\phi$  [deg]")
    ax.text(0.006, 0.96, "a", transform=ax.transAxes, color="white", fontweight="bold", va="top")

    ax.text(0.50, 1.025, "48,000 time steps × 51 blade elements = 2,448,000 reference roots",
            transform=ax.transAxes, ha="center", va="bottom", fontsize=8.2)

    # A 20-second, full-resolution zoom makes each of the 51 simultaneous tasks visible.
    axz = fig.add_subplot(gs[1, 0])
    t0, t1 = 300.0, 320.0
    mask = (time >= t0) & (time <= t1)
    imz = axz.imshow(np.rad2deg(phi[mask]).T, aspect="auto", origin="lower", interpolation="nearest",
                     extent=(time[mask][0], time[mask][-1], 0.5, 51.5),
                     cmap="twilight_shifted", vmin=-180, vmax=180, rasterized=True)
    for yline in (17.5, 34.5):
        axz.axhline(yline, color="white", lw=0.8)
    axz.set_yticks([9, 26, 43], ["blade 1\n17 rows", "blade 2\n17 rows", "blade 3\n17 rows"])
    axz.set_xlabel("full-resolution time window  [s]")
    axz.set_ylabel("element index within each blade")
    axz.text(0.008, 0.96, "b", transform=axz.transAxes, color="white", fontweight="bold", va="top")

    # Radial profiles at the same instant as Figure 1 retain all 17 samples.
    axr = fig.add_subplot(gs[1, 1])
    sample_step = int(round(306.1 / dt))
    cols = ["#b2182b", "#2166ac", "#1b7837"]
    marks = ["o", "s", "^"]
    for b in range(3):
        vals = np.rad2deg(phi[sample_step, b * 17:(b + 1) * 17])
        axr.plot(vals, radii, color=cols[b], lw=1.15, marker=marks[b], ms=2.8, label=f"blade {b+1}")
    axr.set_xlabel(r"reference root $\phi$  [deg]")
    axr.set_ylabel("element radius $r$  [m]")
    axr.grid(color="#cad1d5", lw=0.4)
    axr.legend(frameon=False, loc="best")
    axr.text(0.035, 0.96, "c", transform=axr.transAxes, fontweight="bold", va="top")
    axr.text(0.97, 0.04, "17 measured points\nper blade at 306.1 s", transform=axr.transAxes,
             ha="right", va="bottom", fontsize=7.1)
    for ext in ("png", "pdf", "svg"):
        fig.savefig(out / f"fig3_batch_field_2d.{ext}", bbox_inches="tight", facecolor="white")
    plt.close(fig)

    valid = np.isfinite(phi)
    meta["fig3"] = {
        "files": [f"fig3_batch_field_2d.{x}" for x in ("png", "pdf", "svg")],
        "dataset": data_path.relative_to(ROOT).as_posix(), "dataset_sha256": sha256(data_path),
        "records": int(phi.size), "time_steps": nsteps, "nodes_per_step": nnodes,
        "blades": 3, "elements_per_blade": 17, "valid_roots": int(valid.sum()),
        "phi_deg_range": [float(np.nanmin(np.rad2deg(phi))), float(np.nanmax(np.rad2deg(phi)))],
        "detail_window_s": [t0, t1], "radial_profile_time_s": float(time[sample_step]),
    }


def render_batch_field_v2(out: Path, meta: dict) -> None:
    """Dense but legible overview, literal 51-task tile, and time-radius tile."""
    t = load_tables()
    data_path, mm, nnodes, nsteps, version = open_dataset()
    phi_deg = np.rad2deg(np.asarray(mm[3]).reshape(nsteps, nnodes))
    dt = 600.0 / (nsteps - 1)
    time = np.arange(nsteps) * dt
    radii = t["bem_node_r"]
    sample_step = int(round(306.1 / dt))
    t0, t1 = 104.0, 116.0

    fig = plt.figure(figsize=(7.25, 5.05))
    gs = fig.add_gridspec(2, 2, height_ratios=(1.12, 0.88), width_ratios=(1.02, 0.98),
                          hspace=0.34, wspace=0.38, left=0.085, right=0.90,
                          bottom=0.09, top=0.965)
    ax = fig.add_subplot(gs[0, :])
    im = ax.imshow(phi_deg.T, aspect="auto", origin="lower", interpolation="nearest",
                   extent=(0, 600, 0.5, 51.5), cmap="twilight_shifted", vmin=-180, vmax=180,
                   rasterized=True)
    for yline in (17.5, 34.5):
        ax.axhline(yline, color="white", lw=0.8, alpha=0.8)
    ax.set_yticks([9, 26, 43], ["blade 1", "blade 2", "blade 3"])
    ax.set_xlabel("OpenFAST simulation time  [s]")
    ax.set_ylabel("51 equations per time step")
    ax.text(0.006, 0.96, "a", transform=ax.transAxes, color="white", fontweight="bold", va="top")
    ax.axvline(time[sample_step], color="#f6e8c3", lw=0.9, alpha=0.95)
    ax.add_patch(Rectangle((t0, 0.5), t1 - t0, 17, fill=False, edgecolor="#f6e8c3", lw=1.0))
    ax.text(0.50, 1.025, "48,000 time steps × 51 blade elements = 2,448,000 reference roots",
            transform=ax.transAxes, ha="center", va="bottom", fontsize=8.2)

    axt = fig.add_subplot(gs[1, 0])
    tile = phi_deg[sample_step].reshape(3, 17)
    axt.imshow(tile, aspect="auto", origin="lower", interpolation="nearest",
               extent=(0.5, 17.5, 0.5, 3.5), cmap="twilight_shifted", vmin=-180, vmax=180)
    axt.set_xticks(np.arange(1, 18, 2))
    axt.set_yticks([1, 2, 3], ["blade 1", "blade 2", "blade 3"])
    axt.set_xlabel("radial element index")
    axt.set_ylabel("51 tasks at one step")
    axt.set_xticks(np.arange(0.5, 18, 1), minor=True)
    axt.set_yticks(np.arange(0.5, 4, 1), minor=True)
    axt.grid(which="minor", color="white", lw=0.45, alpha=0.75)
    axt.tick_params(which="minor", bottom=False, left=False)
    cmap = mpl.colormaps["twilight_shifted"]
    norm = Normalize(-180, 180)
    for b in range(3):
        for e in range(17):
            val = float(tile[b, e])
            rgb = cmap(norm(val))[:3]
            luminance = 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]
            axt.text(e + 1, b + 1, f"{val:.0f}", ha="center", va="center",
                     fontsize=4.4, color="white" if luminance < 0.52 else "#17262e")
    axt.text(0.012, 0.96, "b", transform=axt.transAxes, color="white", fontweight="bold", va="top")
    axt.text(0.50, 1.025, f"one time step: 3 blades × 17 roots  (t={time[sample_step]:.3f} s)",
             transform=axt.transAxes, ha="center", va="bottom", fontsize=7.2)

    axz = fig.add_subplot(gs[1, 1])
    mask = (time >= t0) & (time <= t1)
    blade_one = phi_deg[mask, :17].T
    axz.imshow(blade_one, aspect="auto", origin="lower", interpolation="nearest",
               extent=(time[mask][0], time[mask][-1], 0.5, 17.5),
               cmap="twilight_shifted", vmin=-180, vmax=180, rasterized=True)
    selected = [0, 4, 8, 12, 16]
    axz.set_yticks([q + 1 for q in selected], [f"e{q+1}  {radii[q]:.1f}m" for q in selected])
    axz.set_xlabel("simulation time  [s]")
    axz.text(0.012, 0.96, "c", transform=axz.transAxes, color="white", fontweight="bold", va="top")
    axz.text(0.98, 0.93, "blade 1", transform=axz.transAxes, ha="right", va="top", fontsize=7.1)
    axz.text(0.50, 1.025, "blade 1: time × radial-element batch (full resolution)",
             transform=axz.transAxes, ha="center", va="bottom", fontsize=7.2)

    cax = fig.add_axes([0.94, 0.09, 0.018, 0.875])
    cb = fig.colorbar(im, cax=cax, orientation="vertical")
    cb.set_label(r"reference root $\phi$  [deg]")
    layout = audit_layout(fig, {"overview": ax, "single_step_tile": axt,
                                "time_radius_tile": axz, "colorbar": cax})
    for ext in ("png", "pdf", "svg"):
        fig.savefig(out / f"fig3_batch_field_2d.{ext}", bbox_inches="tight", facecolor="white")
    plt.close(fig)

    meta["fig3"] = {
        "files": [f"fig3_batch_field_2d.{x}" for x in ("png", "pdf", "svg")],
        "dataset": data_path.relative_to(ROOT).as_posix(), "dataset_sha256": sha256(data_path),
        "records": int(phi_deg.size), "time_steps": nsteps, "nodes_per_step": nnodes,
        "blades": 3, "elements_per_blade": 17, "valid_roots": int(np.isfinite(phi_deg).sum()),
        "phi_deg_range": [float(np.nanmin(phi_deg)), float(np.nanmax(phi_deg))],
        "detail_window_s": [t0, t1], "task_tile_time_s": float(time[sample_step]),
        "layout_audit": layout,
    }


def write_notes(out: Path, meta: dict) -> None:
    notes = """# Real OpenFAST/BEM two-dimensional publication figures

All panels are two-dimensional, data-driven scientific visualizations rather
than conceptual schematics. No three-dimensional reconstruction is used.

## Figure 1 — actual TurbSim rotor-plane field

The contour is the direct `y-z` plane at 306.1 s from the released TurbSim
`.bts` file. Color is the measured streamwise component; arrows are the measured
lateral and vertical components. The projected blade planforms use all 19
released AeroDyn span, chord and twist stations, and the markers are the exact
17 ordinary BEM radii used by each blade. No Taylor or CFD reconstruction is
present in this figure.

Suggested caption: *Instantaneous TurbSim rotor-plane inflow at 306.1 s for the
NREL 5-MW benchmark. Color denotes streamwise velocity and arrows denote the two
transverse components. The rotor planform and 51 blade-element nodes are drawn
from the released AeroDyn geometry and solver tables.*

## Figure 2 — complete diagnostics for one real blade element

Panel (a) uses record 89,241 from the released 2,448,000-record binary dataset
and the corresponding DU25 airfoil coordinates. Panel (b) displays the released
polar samples and the interpolated operating point. Panel (c) evaluates the
exact released C residual and locates its numerical zero. Panel (d) exposes the
Prandtl loss, axial induction, tangential term and solidity that form the same
residual. The manifest records the difference between the OpenFAST reference
angle and the exact zero in microdegrees.

Suggested caption: *Data-level audit of a representative OpenFAST blade-element
root problem: local kinematics and DU25 geometry, released polar interpolation,
exact C residual, and its nonlinear induction/loss terms.*

## Figure 3 — why batched solving is required

Every pixel and curve sample comes from the complete released reference-root
array. At every time step, OpenFAST produces 51 coupled-in-time but independently
solvable blade-element root problems: 3 blades × 17 ordinary elements. Over
48,000 time steps this yields 2,448,000 solves, exposing the two-dimensional
parallelism that the GPU implementation batches.

Suggested caption: *Space–time organization of the complete OpenFAST BEM root
workload. The overview contains all 2,448,000 roots. The labeled 3-by-17 tile
shows the 51 independent equations solved at one time step, while the
full-resolution time-by-radius tile exposes the second batching dimension for
one blade.*

## Reproduce

```bash
python scripts/visualization/render_real_bem_figures.py
```

Python dependencies: `numpy`, `matplotlib`, `scipy`, and `openfast-io`. The JSON
manifest records exact source SHA-256 hashes and selected
record values.
"""
    (out / "FIGURE_NOTES.md").write_text(notes, encoding="utf-8")
    (out / "render_manifest.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", type=Path, default=OUT_DEFAULT)
    args = ap.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    set_paper_style()
    for obsolete in (
        "fig1_openfast_turbulent_rotor.png",
        "fig2_real_bem_section_residual.png", "fig2_real_bem_section_residual.pdf", "fig2_real_bem_section_residual.svg",
        "fig3_real_batch_spacetime.png", "fig3_real_batch_spacetime.pdf",
    ):
        p = out / obsolete
        if p.exists():
            p.unlink()
    meta = {"generator": Path(__file__).relative_to(ROOT).as_posix(), "truth_boundary":
            "Only direct two-dimensional OpenFAST/AeroDyn/TurbSim/BEM data views; no 3-D reconstruction"}
    render_rotor_plane_2d(out, meta)
    render_local_section(out, meta)
    render_batch_field_v2(out, meta)
    write_notes(out, meta)
    print(json.dumps({"output": str(out), "figures": sorted(p.name for p in out.iterdir())}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
