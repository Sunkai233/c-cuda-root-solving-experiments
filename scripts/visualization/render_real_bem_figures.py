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
from matplotlib.patches import Arc, FancyArrowPatch, Polygon


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

    fig = plt.figure(figsize=(7.15, 3.25), constrained_layout=True)
    gs = fig.add_gridspec(1, 2, width_ratios=(1.12, 0.88))
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
    ax.text(-0.78, -0.25, rf"Blade {node//17+1}, AeroDyn station {local_node+2}: $r={t['bem_node_r'][local_node]:.2f}$ m, $c={chord:.3f}$ m", fontsize=7.4)
    ax.text(-0.78, -0.48, rf"$\theta={np.rad2deg(theta):.2f}^\circ$, $\alpha=\phi-\theta={np.rad2deg(alpha):.2f}^\circ$", fontsize=7.4)
    ax.set_aspect("equal")
    ax.set_xlim(-0.9, 3.65)
    ax.set_ylim(-0.65, 2.25)
    ax.set_xlabel("local tangential direction  [m]")
    ax.set_ylabel("local axial direction  [m]")
    ax.text(0.015, 0.97, "a", transform=ax.transAxes, va="top", fontweight="bold")
    ax.spines[["top", "right"]].set_visible(False)

    ax2 = fig.add_subplot(gs[0, 1])
    ph = np.linspace(np.deg2rad(0.2), np.deg2rad(89.5), 2400)
    rr = residual(t, ph, vx, vy, theta, local_node)
    rr[np.abs(rr) > 2.5] = np.nan
    ax2.axhline(0, color="#6f7b81", lw=0.65)
    ax2.plot(np.rad2deg(ph), rr, color="#2166ac", lw=1.45, label=r"exact released C residual $R(\phi)$")
    rref = float(residual(t, np.array([phi_ref]), vx, vy, theta, local_node)[0])
    ax2.scatter([np.rad2deg(phi_ref)], [rref], s=42, color="#b2182b", edgecolor="white", lw=0.8, zorder=4)
    ax2.annotate(rf"OpenFAST root  {np.rad2deg(phi_ref):.3f}$^\circ$", (np.rad2deg(phi_ref), rref),
                 xytext=(31, 0.72), textcoords="data", fontsize=7.7,
                 arrowprops=dict(arrowstyle="->", lw=0.8, color="#b2182b"))
    ax2.set_xlim(0, 75)
    ax2.set_ylim(-1.05, 1.05)
    ax2.set_xlabel(r"inflow angle $\phi$  [deg]")
    ax2.set_ylabel(r"BEM residual $R(\phi)$  [-]")
    ax2.grid(color="#cad1d5", lw=0.45, alpha=0.8)
    ax2.text(0.015, 0.97, "b", transform=ax2.transAxes, va="top", fontweight="bold")
    ax2.legend(loc="lower right", frameon=False)
    for ext in ("png", "pdf", "svg"):
        fig.savefig(out / f"fig2_real_bem_section_residual.{ext}", bbox_inches="tight", facecolor="white")
    plt.close(fig)
    meta["fig2"] = {
        "files": [f"fig2_real_bem_section_residual.{x}" for x in ("png", "pdf", "svg")],
        "dataset": data_path.relative_to(ROOT).as_posix(), "dataset_sha256": sha256(data_path),
        "dataset_version": version, "flat_record": flat, "time_step": step, "global_node_zero_based": node,
        "blade_one_based": node // 17 + 1, "local_node_zero_based": local_node,
        "Vx_mps": vx, "Vy_mps": vy, "theta_rad": theta, "phi_openfast_rad": phi_ref,
        "residual_at_reference": rref, "airfoil_file": airfoil_paths()[afid].name,
    }


def render_batch_field(out: Path, meta: dict) -> None:
    t = load_tables()
    data_path, mm, nnodes, nsteps, version = open_dataset()
    phi = np.asarray(mm[3]).reshape(nsteps, nnodes)
    dt = 600.0 / (nsteps - 1)
    time = np.arange(nsteps) * dt
    radii = t["bem_node_r"]

    fig = plt.figure(figsize=(7.15, 4.8))
    gs = fig.add_gridspec(2, 1, height_ratios=(0.90, 1.10), hspace=0.28,
                          left=0.09, right=0.93, bottom=0.07, top=0.98)
    ax = fig.add_subplot(gs[0])
    im = ax.imshow(np.rad2deg(phi).T, aspect="auto", origin="lower", interpolation="nearest",
                   extent=(0, 600, 0.5, 51.5), cmap="twilight_shifted", vmin=-180, vmax=180,
                   rasterized=True)
    for yline in (17.5, 34.5):
        ax.axhline(yline, color="white", lw=0.8, alpha=0.8)
    ax.set_yticks([9, 26, 43], ["blade 1", "blade 2", "blade 3"])
    ax.set_xlabel("OpenFAST simulation time  [s]")
    ax.set_ylabel("3 blades × 17 radial elements")
    cb = fig.colorbar(im, ax=ax, orientation="vertical", pad=0.012, aspect=22)
    cb.set_label(r"reference root $\phi$  [deg]")
    ax.text(0.006, 0.96, "a", transform=ax.transAxes, color="white", fontweight="bold", va="top")

    ax3 = fig.add_subplot(gs[1], projection="3d")
    take = np.arange(0, nsteps, 120)
    tt = time[take]
    T, R = np.meshgrid(tt, radii, indexing="xy")
    norm = Normalize(-180, 180)
    cmap = mpl.colormaps["twilight_shifted"]
    for b in range(3):
        P = np.rad2deg(phi[take, b * 17:(b + 1) * 17]).T
        Y = R + b * 72.0
        ax3.plot_surface(T, Y, P, facecolors=cmap(norm(P)), rstride=1, cstride=1,
                         linewidth=0, antialiased=False, shade=False, alpha=0.96)
    ax3.set_xlabel("time  [s]", labelpad=5)
    ax3.set_ylabel("")
    ax3.set_zlabel(r"$\phi$  [deg]", labelpad=4)
    ax3.set_yticks([np.mean(radii), np.mean(radii) + 72, np.mean(radii) + 144],
                   ["blade 1", "blade 2", "blade 3"])
    ax3.view_init(elev=25, azim=-61)
    ax3.set_box_aspect((2.6, 1.25, 1.0))
    ax3.text2D(0.006, 0.97, "b", transform=ax3.transAxes, fontweight="bold", va="top")
    ax3.text2D(0.08, 0.96, "2,448,000 roots = 48,000 time steps × 3 blades × 17 elements",
               transform=ax3.transAxes, fontsize=8.2)
    ax3.xaxis.pane.set_facecolor((0.95, 0.97, 0.98, 1))
    ax3.yaxis.pane.set_facecolor((0.95, 0.97, 0.98, 1))
    ax3.zaxis.pane.set_facecolor((0.97, 0.98, 0.99, 1))
    for ext in ("png", "pdf"):
        fig.savefig(out / f"fig3_real_batch_spacetime.{ext}", bbox_inches="tight", facecolor="white")
    plt.close(fig)

    valid = np.isfinite(phi)
    meta["fig3"] = {
        "files": [f"fig3_real_batch_spacetime.{x}" for x in ("png", "pdf")],
        "dataset": data_path.relative_to(ROOT).as_posix(), "dataset_sha256": sha256(data_path),
        "records": int(phi.size), "time_steps": nsteps, "nodes_per_step": nnodes,
        "blades": 3, "elements_per_blade": 17, "valid_roots": int(valid.sum()),
        "phi_deg_range": [float(np.nanmin(np.rad2deg(phi))), float(np.nanmax(np.rad2deg(phi)))],
    }


def write_notes(out: Path, meta: dict) -> None:
    notes = """# Real OpenFAST/BEM publication figures

These are data-driven scientific visualizations, not conceptual schematics.

## Figure 1 — rotor and full-field turbulent inflow

The three blades are lofted from the released NREL 5-MW AeroDyn station table
(span, chord, twist, sweep and airfoil ID) and the released airfoil coordinate
files. The colored plane and streamlines use all three velocity components from
the released TurbSim `.bts` file. The streamwise coordinate is reconstructed by
Taylor's frozen-turbulence hypothesis, `x = U_ref (t-t0)`. It must therefore be
captioned as a **TurbSim full-field inflow reconstruction**, not as a
Navier–Stokes CFD solution.

Suggested caption: *NREL 5-MW rotor immersed in the OpenFAST/TurbSim full-field
inflow used to generate the BEM benchmark. Blade surfaces are lofted from the
released AeroDyn chord, twist and airfoil definitions. The upstream volume is a
Taylor reconstruction of the measured TurbSim time series; color denotes the
streamwise velocity component.*

## Figure 2 — one real blade-element equation

Panel (a) uses record 89,241 from the released 2,448,000-record binary dataset
and the corresponding real airfoil geometry. Panel (b) evaluates the exact
released C residual and polar tables, then marks the OpenFAST reference root.

Suggested caption: *Local blade-element kinematics and nonlinear residual for a
representative OpenFAST record. The velocity triangle, airfoil, operating angle
and marked root are taken from the released benchmark rather than synthesized.*

## Figure 3 — why batched solving is required

Every pixel and surface sample comes from the complete released reference-root
array. At every time step, OpenFAST produces 51 coupled-in-time but independently
solvable blade-element root problems: 3 blades × 17 ordinary elements. Over
48,000 time steps this yields 2,448,000 solves, exposing the two-dimensional
parallelism that the GPU implementation batches.

Suggested caption: *Space–time organization of the complete OpenFAST BEM root
workload. The heat map contains all 2,448,000 reference roots; the surfaces
separate the three blades and show radial and temporal coherence. The workload
is naturally batched over blade elements and time.*

## Reproduce

```bash
python scripts/visualization/render_real_bem_figures.py
```

Python dependencies: `numpy`, `matplotlib`, `pyvista`, `vtk`, and
`openfast-io`. The JSON manifest records exact source SHA-256 hashes and selected
record values.
"""
    (out / "FIGURE_NOTES.md").write_text(notes, encoding="utf-8")
    (out / "render_manifest.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", type=Path, default=OUT_DEFAULT)
    ap.add_argument("--skip-3d", action="store_true")
    args = ap.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    set_paper_style()
    meta = {"generator": Path(__file__).relative_to(ROOT).as_posix(), "truth_boundary":
            "OpenFAST/AeroDyn/TurbSim simulation data; Fig. 1 uses Taylor reconstruction and is not Navier-Stokes CFD"}
    if not args.skip_3d:
        render_rotor_inflow(out, meta)
    render_local_section(out, meta)
    render_batch_field(out, meta)
    write_notes(out, meta)
    print(json.dumps({"output": str(out), "figures": sorted(p.name for p in out.iterdir())}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
