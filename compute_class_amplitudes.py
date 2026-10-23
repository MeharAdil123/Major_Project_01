"""
Standalone Script to Compute Average CSI Amplitudes, RSSI Power, and Kinematic Motion Energy
for Each Activity Class on the 6-Subject Library Dataset (2,401 Windows).

Does NOT modify or interfere with any other existing project files.
Saves results to: results/class_amplitudes_summary.csv and results/class_amplitudes_summary.json
"""

import os
import json
from pathlib import Path
import numpy as np
import pandas as pd

def compute_class_amplitudes():
    print("=" * 85)
    print("  DETAILED CSI AMPLITUDE & KINEMATIC MOTION ANALYSIS PER ACTIVITY CLASS")
    print("  Dataset: 6-Subject Library Dataset (202 Takes, 2,401 Windows of 4s)")
    print("=" * 85)

    base_dir = Path(".")
    csv_candidates = [
        base_dir / "temp_mohith_repo" / "data" / "features" / "features_4s.csv",
        base_dir / "data" / "features" / "features_4s.csv"
    ]
    csv_path = next((p for p in csv_candidates if p.exists()), None)
    if not csv_path:
        raise FileNotFoundError("Could not find features_4s.csv.")

    df = pd.read_csv(csv_path)
    classes = sorted(df["window_label"].unique())

    print(f"Loaded {len(df)} windows across {len(classes)} classes:\n{classes}\n")

    summary_list = []

    for c in classes:
        sub = df[df["window_label"] == c]
        n_windows = len(sub)

        # 1. Received Signal Power (RSSI in dBm)
        rx1_rssi = float(sub["rx1_rssi_mean"].mean())
        rx2_rssi = float(sub["rx2_rssi_mean"].mean())
        dual_rssi = (rx1_rssi + rx2_rssi) / 2.0

        # 2. Dynamic Temporal Amplitude Fluctuation (Standard Deviation)
        # Higher values reflect strong body kinematics disturbing the RF field
        rx1_sd = float(sub["rx1_sd_mean"].mean())
        rx2_sd = float(sub["rx2_sd_mean"].mean())
        dual_sd = (rx1_sd + rx2_sd) / 2.0

        # 3. Sliding Kinematic Motion Energy
        rx1_motion = float(sub["rx1_motion_mean"].mean())
        rx2_motion = float(sub["rx2_motion_mean"].mean())
        dual_motion = (rx1_motion + rx2_motion) / 2.0

        # 4. Low vs High Frequency Subcarrier Profile (Band 0 vs Band 7)
        rx1_b0 = float(sub["rx1_band0_mean"].mean())
        rx1_b7 = float(sub["rx1_band7_mean"].mean())
        rx2_b0 = float(sub["rx2_band0_mean"].mean())
        rx2_b7 = float(sub["rx2_band7_mean"].mean())

        summary_list.append({
            "Class": c,
            "Windows": n_windows,
            "RX1_RSSI_dBm": round(rx1_rssi, 2),
            "RX2_RSSI_dBm": round(rx2_rssi, 2),
            "Dual_RSSI_dBm": round(dual_rssi, 2),
            "RX1_Amplitude_Fluct": round(rx1_sd, 4),
            "RX2_Amplitude_Fluct": round(rx2_sd, 4),
            "Dual_Kinematic_Fluct": round(dual_sd, 4),
            "Kinematic_Motion_Energy": round(dual_motion, 4),
            "RX1_Band0": round(rx1_b0, 4),
            "RX1_Band7": round(rx1_b7, 4),
            "RX2_Band0": round(rx2_b0, 4),
            "RX2_Band7": round(rx2_b7, 4),
        })

    summary_df = pd.DataFrame(summary_list)

    # Print Clean Display Table
    print("-" * 92)
    print(f"{'Class':<12} | {'Windows':<7} | {'Dual RSSI':<12} | {'Dynamic Fluctuation':<20} | {'Kinematic Motion':<18} | {'Phys. State':<12}")
    print("-" * 92)

    state_descriptions = {
        "empty": "No Person",
        "stand": "Stationary",
        "lie": "Stationary",
        "sit": "Stationary",
        "bend_pick": "Transient Event",
        "fall": "Rapid Impact",
        "stand_up": "Postural Shift",
        "sit_down": "Postural Shift",
        "walk": "Continuous Motion"
    }

    for r in summary_list:
        desc = state_descriptions.get(r["Class"], "Activity")
        print(f"{r['Class']:<12} | {r['Windows']:<7} | {r['Dual_RSSI_dBm']:<8.2f} dBm | {r['Dual_Kinematic_Fluct']:<20.4f} | {r['Kinematic_Motion_Energy']:<18.4f} | {desc:<12}")
    print("-" * 92)

    # Save CSV and JSON
    out_dir = base_dir / "results"
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_out = out_dir / "class_amplitudes_summary.csv"
    json_out = out_dir / "class_amplitudes_summary.json"

    summary_df.to_csv(csv_out, index=False)
    with open(json_out, "w") as f:
        json.dump(summary_list, f, indent=2)

    print(f"\nSaved CSV summary to:  {csv_out}")
    print(f"Saved JSON summary to: {json_out}\n")

if __name__ == "__main__":
    compute_class_amplitudes()
