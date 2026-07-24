"""Independent frequency-domain reference for WP3; empymod 2.6.0."""
import argparse
import json
import math
from pathlib import Path

import empymod
import numpy as np


def pair(value):
    z = complex(value)
    return {"re": z.real, "im": z.imag}


def run(config_path):
    cfg = json.loads(Path(config_path).read_text(encoding="utf-8-sig"))
    rho = 1.0 / float(cfg["medium"]["sigma_s_m"])
    # Air/earth interface; electrodes are 1 cm inside earth because empymod
    # assigns an interface point to the upper layer.
    z = float(cfg["csamt"]["electrode_depth_m"])
    src = [
        float(cfg["csamt"]["a_m"]), float(cfg["csamt"]["b_m"]),
        0.0, 0.0, z, z,
    ]
    common = dict(
        depth=[0.0], res=[2.0e14, rho], freqtime=float(cfg["csamt"]["frequency_hz"]),
        srcpts=5, strength=float(cfg["csamt"]["current_a"]), verb=0,
    )
    rows = []
    for x in cfg["csamt"]["receiver_x_m"]:
        ex = empymod.bipole(src, [x, 0.0, z, 0.0, 0.0], mrec=False, **common)
        hy = empymod.bipole(src, [x, 0.0, z, 90.0, 0.0], mrec=True, **common)
        impedance = complex(ex) / complex(hy)
        omega = 2.0 * math.pi * float(cfg["csamt"]["frequency_hz"])
        mu0 = 4.0e-7 * math.pi
        rows.append({
            "x_m": x, "ex": pair(ex), "hy": pair(hy),
            "rho_a_ohm_m": abs(impedance) ** 2 / (omega * mu0),
            "phase_rad": math.atan2(impedance.imag, impedance.real),
        })
    w = cfg["wfem"]
    wsrc = [w["a_m"], w["b_m"], 0.0, 0.0, z, z]
    wrec = [w["m_m"], w["n_m"], 0.0, 0.0, z, z]
    variants = {}
    for transform in ("dlf", "qwe"):
        voltage = empymod.bipole(
            wsrc, wrec, [0.0], [2.0e14, rho], float(w["frequency_hz"]),
            srcpts=5, recpts=5, strength=float(w["current_a"]),
            ht=transform, verb=0,
        )
        variants[transform] = pair(complex(voltage) / float(w["current_a"]))
    tem = cfg["tem"]
    nodes, weights = np.polynomial.legendre.leggauss(int(tem["gate_quadrature_order"]))
    loop_z = float(tem["loop_depth_m"])
    loop = [0.0, 0.0, loop_z, 0.0, 90.0]
    moment = (
        float(tem["current_a"]) * float(tem["transmitter_turns"])
        * float(tem["equivalent_transmitter_area_m2"])
    )
    pickup = float(tem["receiver_turns"]) * float(tem["equivalent_receiver_area_m2"])
    ramp_signal = {
        "nodes": [-float(tem["ramp_s"]), 0.0],
        "amplitudes": [1.0, 0.0], "signal": -1, "nquad": 5,
    }
    tem_rows = []
    def gate_rows(gates, receiver):
      result = []
      for start, stop in gates:
        times = 0.5 * (stop - start) * nodes + 0.5 * (start + stop)
        kwargs = dict(
            src=loop, rec=receiver, depth=[0.0], res=[2.0e14, rho],
            freqtime=times, msrc="b", mrec="b", strength=moment, verb=0,
            ft="dlf", ftarg={"dlf": "key_201_2012", "pts_per_dec": -1},
        )
        step = -pickup * np.asarray(empymod.bipole(signal=-1, **kwargs))
        ramp = -pickup * np.asarray(empymod.bipole(signal=ramp_signal, **kwargs))
        result.append({
            "start_s": start, "stop_s": stop,
            "step_gate_average_v": float(np.dot(weights, step) / 2.0),
            "ramp_gate_average_v": float(np.dot(weights, ramp) / 2.0),
            "nodes_s": times.tolist(), "weights": weights.tolist(),
        })
      return result
    tem_rows = gate_rows(tem["gates_s"], loop)
    asym = tem["asymptotic_check"]
    asym_rec = [float(asym["receiver_offset_m"]), 0.0, loop_z, 0.0, 90.0]
    asym_rows = gate_rows(asym["gates_s"], asym_rec)
    return {
        "schema": "wp3-empymod-frequency-oracle-v1",
        "empymod_version": empymod.__version__,
        "coordinates": "East-North-Depth; electrodes 0.01 m inside earth",
        "csamt": rows,
        "wfem_delta_u_over_i_ohm": variants,
        "tem_magnetic_dipole_small_loop_gate_average": tem_rows,
        "tem_magnetic_dipole_late_time_asymptotic_gate_average": asym_rows,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    Path(args.output).write_text(
        json.dumps(run(args.config), indent=2), encoding="utf-8"
    )
