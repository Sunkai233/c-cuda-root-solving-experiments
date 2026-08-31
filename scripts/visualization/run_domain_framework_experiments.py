#!/usr/bin/env python3
"""Generate framework-level evidence for the four non-OpenFAST domains.

The calculations deliberately keep two layers separate:

* application-framework runs (pvlib, Cantera and CoolProp), which show where
  large batches of independent scalar solves arise in real workflows; and
* exact checks against this repository's frozen scalar equations.

Orekit is executed by ``run_orekit_reference.py`` because its Java runtime may
need an ASCII-path virtual environment on Windows.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
OUT_DEFAULT = ROOT / "paper_figures" / "domain_frameworks_v1" / "data"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def file_record(path: Path, rows: int | None = None) -> dict:
    rec = {"file": path.name, "sha256": sha256(path)}
    if rows is not None:
        rec["rows"] = int(rows)
    return rec


def run_pvlib(out: Path) -> dict:
    import pvlib

    module_name = "Canadian_Solar_Inc__CS5P_220M"
    modules = pvlib.pvsystem.retrieve_sam("CECMod")
    module = modules[module_name]
    irradiance = np.linspace(100.0, 1100.0, 21)
    cell_temperature = np.linspace(-10.0, 70.0, 17)
    rows = []
    curves = []
    for tc in cell_temperature:
        for g in irradiance:
            IL, I0, Rs, Rsh, a = pvlib.pvsystem.calcparams_cec(
                g,
                tc,
                module.alpha_sc,
                module.a_ref,
                module.I_L_ref,
                module.I_o_ref,
                module.R_sh_ref,
                module.R_s,
                module.Adjust,
            )
            sd = pvlib.pvsystem.singlediode(IL, I0, Rs, Rsh, a, method="lambertw")
            rows.append(
                {
                    "effective_irradiance_W_m2": g,
                    "cell_temperature_C": tc,
                    "IL_A": IL,
                    "I0_A": I0,
                    "Rs_ohm": Rs,
                    "Rsh_ohm": Rsh,
                    "nNsVth_V": a,
                    **{k: float(sd[k]) for k in ("i_sc", "v_oc", "i_mp", "v_mp", "p_mp")},
                }
            )
            if g in (200.0, 600.0, 1000.0) and tc in (10.0, 50.0):
                voltage = np.linspace(0.0, float(sd["v_oc"]), 181)
                current = pvlib.pvsystem.i_from_v(voltage, IL, I0, Rs, Rsh, a, method="brentq")
                for v, i in zip(voltage, current):
                    curves.append(
                        {
                            "effective_irradiance_W_m2": g,
                            "cell_temperature_C": tc,
                            "V": float(v),
                            "I": float(i),
                            "P": float(v * i),
                        }
                    )
    surface = pd.DataFrame(rows)
    curves_df = pd.DataFrame(curves)
    surface_path = out / "pvlib_cec_operating_surface.csv"
    curves_path = out / "pvlib_cec_iv_curves.csv"
    surface.to_csv(surface_path, index=False, float_format="%.16g")
    curves_df.to_csv(curves_path, index=False, float_format="%.16g")

    # ``round_trip`` is essential here: the default fast parser in recent
    # pandas releases can shorten long fixed-point strings such as 1.053591e-12
    # to 1.0535e-12, which is visible close to open circuit.
    frozen = pd.read_csv(
        ROOT / "references" / "pv_extended_ref_v1_20260824" / "pv_extended.csv",
        float_precision="round_trip",
    )
    predicted = pvlib.pvsystem.i_from_v(
        frozen["V"].to_numpy(), frozen["IL"].to_numpy(), frozen["I0"].to_numpy(),
        frozen["Rs"].to_numpy(), frozen["Rsh"].to_numpy(), frozen["a"].to_numpy(), method="brentq"
    )
    check = frozen[["sample_id", "split", "region", "V", "I"]].copy()
    check["pvlib_I"] = predicted
    check["absolute_error"] = np.abs(predicted - frozen["I"].to_numpy())
    check_path = out / "pvlib_benchmark_reference_check.csv"
    check.to_csv(check_path, index=False, float_format="%.16g")

    module_fields = ["Technology", "STC", "PTC", "A_c", "Length", "Width", "N_s", "I_sc_ref",
                     "V_oc_ref", "I_mp_ref", "V_mp_ref", "alpha_sc", "beta_oc", "a_ref", "I_L_ref",
                     "I_o_ref", "R_s", "R_sh_ref", "Adjust", "Version", "Date"]
    module_parameters = {}
    for key in module_fields:
        value = module[key]
        module_parameters[key] = value.item() if hasattr(value, "item") else value
    return {
        "framework": "pvlib CEC single-diode model + Lambert W / Brent",
        "version": importlib.metadata.version("pvlib"),
        "module": module_name,
        "module_parameters": module_parameters,
        "operating_surface": file_record(surface_path, len(surface)),
        "iv_curves": file_record(curves_path, len(curves_df)),
        "benchmark_check": {
            **file_record(check_path, len(check)),
            "max_absolute_error_A": float(check["absolute_error"].max()),
            "p99_absolute_error_A": float(check["absolute_error"].quantile(0.99)),
        },
    }


def cantera_solution():
    import cantera as ct

    # Cantera's C++ file loader can truncate non-ASCII Windows paths.  Parsing
    # the installed, versioned YAML string is equivalent and avoids that issue.
    mechanism_path = Path(ct.__file__).parent / "data" / "gri30.yaml"
    mechanism_yaml = mechanism_path.read_text(encoding="utf-8")
    return ct.Solution(yaml=mechanism_yaml, transport_model=None), mechanism_path


def run_cantera(out: Path) -> dict:
    import cantera as ct

    inlet_temperatures = np.arange(300.0, 801.0, 25.0)
    residence_times = np.geomspace(0.1, 1.0e-4, 72)
    rows = []
    extinction = []
    mechanism_sha = None
    for tin in inlet_temperatures:
        gas, mechanism_path = cantera_solution()
        mechanism_sha = sha256(mechanism_path)
        gas.TP = tin, ct.one_atm
        gas.set_equivalence_ratio(0.5, "CH4:1.0", "O2:1.0, N2:3.76")
        inlet = ct.Reservoir(gas, clone=True)
        gas.equilibrate("HP")
        reactor = ct.IdealGasReactor(gas, clone=True, volume=1.0)
        exhaust = ct.Reservoir(gas, clone=True)
        state = {"tau": float(residence_times[0])}
        inlet_mfc = ct.MassFlowController(
            inlet, reactor, mdot=lambda t, r=reactor, s=state: r.mass / s["tau"]
        )
        # Keep references alive for the duration of the ReactorNet.
        outlet_mfc = ct.PressureController(reactor, exhaust, primary=inlet_mfc, K=0.01)
        sim = ct.ReactorNet([reactor])
        branch_temperatures = []
        for tau in residence_times:
            state["tau"] = float(tau)
            sim.initial_time = 0.0
            sim.solve_steady()
            branch_temperatures.append(float(reactor.T))
            rows.append(
                {
                    "inlet_temperature_K": tin,
                    "residence_time_s": tau,
                    "steady_temperature_K": reactor.T,
                    "heat_release_rate_W_m3": reactor.phase.heat_release_rate,
                    "X_CH4": reactor.phase["CH4"].X[0],
                    "X_CO": reactor.phase["CO"].X[0],
                    "X_CO2": reactor.phase["CO2"].X[0],
                    "X_H2O": reactor.phase["H2O"].X[0],
                }
            )
        hot = np.asarray(branch_temperatures) > tin + 100.0
        extinction_tau = float(residence_times[np.flatnonzero(hot)[-1]]) if np.any(hot) else math.nan
        extinction.append({"inlet_temperature_K": tin, "last_hot_residence_time_s": extinction_tau})
        _ = outlet_mfc
    field = pd.DataFrame(rows)
    ext = pd.DataFrame(extinction)
    field_path = out / "cantera_cstr_hot_branch_surface.csv"
    ext_path = out / "cantera_cstr_extinction_curve.csv"
    field.to_csv(field_path, index=False, float_format="%.16g")
    ext.to_csv(ext_path, index=False, float_format="%.16g")
    return {
        "framework": "Cantera ideal-gas well-stirred combustor, hot-branch continuation",
        "version": importlib.metadata.version("cantera"),
        "mechanism": "GRI-Mech 3.0 (gri30.yaml)",
        "mechanism_sha256": mechanism_sha,
        "equivalence_ratio": 0.5,
        "pressure_Pa": float(ct.one_atm),
        "inlet_temperature_count": len(inlet_temperatures),
        "residence_time_count": len(residence_times),
        "surface": file_record(field_path, len(field)),
        "extinction_curve": file_record(ext_path, len(ext)),
    }


def pr_parameters(T: np.ndarray, P: np.ndarray, Tc: float, Pc: float, omega: float):
    R = 8.31446261815324
    kappa = 0.37464 + 1.54226 * omega - 0.26992 * omega * omega
    alpha = (1.0 + kappa * (1.0 - np.sqrt(T / Tc))) ** 2
    # Exact Peng-Robinson critical constants (the familiar 0.45724 and 0.07780
    # are display-rounded values and visibly perturb roots near the critical
    # point).
    omega_a = 0.4572355289213822
    omega_b = 0.07779607390388846
    a = omega_a * R * R * Tc * Tc / Pc * alpha
    b = omega_b * R * Tc / Pc
    A = a * P / (R * R * T * T)
    B = b * P / (R * T)
    return A, B, a, b


def pr_roots(A: float, B: float) -> list[float]:
    roots = np.roots([1.0, -(1.0 - B), A - 3.0 * B * B - 2.0 * B,
                      -(A * B - B * B - B * B * B)])
    return sorted(float(z.real) for z in roots if abs(z.imag) < 1e-9 and z.real > B)


def run_coolprop(out: Path) -> dict:
    import CoolProp
    import CoolProp.CoolProp as CP

    fluid = "Propane"
    state = CP.AbstractState("PR", fluid)
    Tc = float(state.T_critical())
    Pc = float(state.p_critical())
    omega = float(CP.PropsSI("acentric", fluid))
    R = 8.31446261815324

    sat_rows = []
    sat_checks = []
    # The PR saturation flash becomes numerically singular in the immediate
    # critical-point neighbourhood; 0.99 Tc stays inside the documented VLE
    # domain while retaining a clearly resolved dome.
    for T in np.linspace(max(float(state.Ttriple()) + 1.0, 0.55 * Tc), 0.99 * Tc, 160):
        state.update(CP.QT_INPUTS, 0.0, float(T))
        P = float(state.p())
        rho_l = float(state.rhomolar())
        state.update(CP.QT_INPUTS, 1.0, float(T))
        rho_v = float(state.rhomolar())
        A, B, _, _ = pr_parameters(np.asarray(T), np.asarray(P), Tc, Pc, omega)
        roots = pr_roots(float(A), float(B))
        z_l_cp = P / (rho_l * R * T)
        z_v_cp = P / (rho_v * R * T)
        sat_rows.append({"T_K": T, "P_Pa": P, "rho_liq_mol_m3": rho_l, "rho_vap_mol_m3": rho_v,
                         "Z_liq_coolprop": z_l_cp, "Z_vap_coolprop": z_v_cp})
        sat_checks.append({"T_K": T, "P_Pa": P, "Z_liq_coolprop": z_l_cp,
                           "Z_liq_cubic_root": roots[0], "Z_vap_coolprop": z_v_cp,
                           "Z_vap_cubic_root": roots[-1], "liquid_absolute_error": abs(z_l_cp-roots[0]),
                           "vapor_absolute_error": abs(z_v_cp-roots[-1])})

    map_rows = []
    for Tr in np.linspace(0.55, 1.15, 121):
        for Pr in np.linspace(0.02, 1.5, 151):
            T, P = Tr * Tc, Pr * Pc
            A, B, _, _ = pr_parameters(np.asarray(T), np.asarray(P), Tc, Pc, omega)
            roots = pr_roots(float(A), float(B))
            deriv = [abs(3*z*z - 2*(1-float(B))*z + float(A)-3*float(B)**2-2*float(B)) for z in roots]
            padded = roots + [math.nan] * (3 - len(roots))
            map_rows.append({"Tr": Tr, "Pr": Pr, "A": float(A), "B": float(B), "root_count": len(roots),
                             "Z0": padded[0], "Z1": padded[1], "Z2": padded[2],
                             "max_root_condition": max((1.0/max(d, 1e-300) for d in deriv), default=math.nan)})

    isotherm_rows = []
    for Tr in (0.70, 0.80, 0.90, 0.98, 1.05):
        T = Tr * Tc
        _, _, a, b = pr_parameters(np.asarray(T), np.asarray(Pc), Tc, Pc, omega)
        for vr in np.geomspace(1.005, 80.0, 500):
            v = float(vr * b)
            P = R*T/(v-b) - float(a)/(v*(v+b)+b*(v-b))
            isotherm_rows.append({"Tr": Tr, "v_over_b": vr, "P_over_Pc": P/Pc})

    sat = pd.DataFrame(sat_rows)
    checks = pd.DataFrame(sat_checks)
    root_map = pd.DataFrame(map_rows)
    isotherms = pd.DataFrame(isotherm_rows)
    sat_path = out / "coolprop_pr_propane_saturation.csv"
    check_path = out / "coolprop_pr_cubic_root_check.csv"
    map_path = out / "coolprop_pr_root_map.csv"
    iso_path = out / "coolprop_pr_isotherms.csv"
    sat.to_csv(sat_path, index=False, float_format="%.16g")
    checks.to_csv(check_path, index=False, float_format="%.16g")
    root_map.to_csv(map_path, index=False, float_format="%.16g")
    isotherms.to_csv(iso_path, index=False, float_format="%.16g")
    return {
        "framework": "CoolProp Peng-Robinson backend + exact cubic Z roots",
        "version": CoolProp.__version__,
        "fluid": fluid,
        "critical_temperature_K": Tc,
        "critical_pressure_Pa": Pc,
        "acentric_factor": omega,
        "saturation": file_record(sat_path, len(sat)),
        "root_map": file_record(map_path, len(root_map)),
        "isotherms": file_record(iso_path, len(isotherms)),
        "cubic_root_check": {
            **file_record(check_path, len(checks)),
            "max_liquid_Z_error": float(checks["liquid_absolute_error"].max()),
            "max_vapor_Z_error": float(checks["vapor_absolute_error"].max()),
        },
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=OUT_DEFAULT)
    args = ap.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    manifest = {
        "purpose": "Framework-level real workflows aligned to frozen scalar benchmark semantics",
        "pv": run_pvlib(out),
        "cstr": run_cantera(out),
        "peng_robinson": run_coolprop(out),
    }
    path = out / "framework_experiment_manifest.json"
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
