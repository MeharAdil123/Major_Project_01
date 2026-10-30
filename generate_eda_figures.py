"""
Comprehensive Exploratory Data Analysis (EDA) Figure Generation Script
for Group 10 Major Project: Wi-Fi CSI HAR & Fall Detection.

Generates 3 High-Impact Publication-Quality EDA Figures:
  1. EDA 1: Subcarrier-Time CSI Amplitude Heatmaps & Subcarrier Spatial Correlation Heatmap
  2. EDA 2: Statistical Boxplots across Activity Classes (Peak Energy, Amplitude Fluctuation, Dual-Link Correlation, Doppler Power)
  3. EDA 3: High-Dimensional Feature Space Manifold (PCA & t-SNE 2D Cluster Projections)

Outputs saved to: results/eda/
"""

import sys
import os
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.decomposition import PCA
from sklearn.manifold import TSNE
from sklearn.preprocessing import StandardScaler

# Ensure reproducibility and headless rendering
plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")
plt.rcParams["font.family"] = "sans-serif"
plt.rcParams["font.sans-serif"] = ["DejaVu Sans", "Arial", "Helvetica"]
plt.rcParams["axes.edgecolor"] = "#333333"
plt.rcParams["axes.linewidth"] = 0.8

EDA_DIR = Path("results/eda")
EDA_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================================
# 1. LOAD DATASET & CHANNELS
# ============================================================================
print("=" * 80)
print("  GENERATING PUBLICATION-QUALITY EDA FIGURES FOR WI-FI CSI HAR & FALL DETECTION")
print("=" * 80)

csv_path = Path("temp_mohith_repo/data/features/features_4s.csv")
channels_path = Path("data/channels_4s.npy")

if not csv_path.exists():
    raise FileNotFoundError(f"Missing {csv_path}")
if not channels_path.exists():
    raise FileNotFoundError(f"Missing {channels_path}")

print(f"Loading features from {csv_path}...")
df = pd.read_csv(csv_path)

print(f"Loading 32-channel tensors from {channels_path}...")
C = np.load(channels_path)  # Shape: [2401, 32, 200]
print(f"Loaded: N={len(df)} windows, C shape={C.shape}")


# ============================================================================
# 2. EDA 1A: SUBCARRIER-TIME CSI DYNAMIC SPECTROGRAM HEATMAPS
# ============================================================================
print("\n[1/3] Generating EDA 1A: Subcarrier-Time CSI Heatmaps...")

# Select representative clean takes for key classes
target_classes = [
    ("Empty Room (Baseline)", "empty", "No presence / Thermal floor"),
    ("Walking Gait (Periodic)", "walk", "Rhythmic multipath ripples"),
    ("Emergency Fall (Impact Shock)", "fall", "Abrupt high-energy burst"),
    ("Bend & Pick (Look-Alike)", "bend_pick", "Localized torso flexion")
]

fig, axes = plt.subplots(2, 2, figsize=(15, 10), sharex=True, sharey=True)
axes = axes.flatten()

# Common time axis (4.0 seconds, 200 timesteps @ 50 Hz)
time_axis = np.linspace(0, 4.0, 200)

for i, (display_name, label, subtitle) in enumerate(target_classes):
    sub = df[df["window_label"] == label]
    # Pick a high-variance representative window for dynamic actions, or median for empty
    if label == "empty":
        idx = sub.index[len(sub) // 2]
    else:
        # Pick window with clear motion energy
        best_local_idx = sub["rx1_motion_max"].argmax()
        idx = sub.index[best_local_idx]

    window_data = C[idx]  # [32, 200]
    
    # Plot heatmap
    im = axes[i].imshow(
        window_data,
        aspect="auto",
        cmap="turbo",
        origin="lower",
        extent=[0, 4.0, 1, 32],
        vmin=-1.5,
        vmax=1.5
    )
    
    axes[i].set_title(f"{display_name}\n({subtitle})", fontsize=12, fontweight="bold", pad=8)
    axes[i].set_ylabel("Subcarrier Index (1-32 Channels)" if i % 2 == 0 else "", fontsize=10)
    axes[i].set_xlabel("Time (Seconds)" if i >= 2 else "", fontsize=10)
    
    # Annotate RX split
    axes[i].axhline(y=16.5, color="white", linestyle="--", linewidth=1.2, alpha=0.8)
    axes[i].text(0.1, 8, "RX1 (Amp + Phase)", color="white", fontsize=9, fontweight="bold",
                 bbox=dict(boxstyle="round,pad=0.2", facecolor="black", alpha=0.5))
    axes[i].text(0.1, 24, "RX2 (Amp + Phase)", color="white", fontsize=9, fontweight="bold",
                 bbox=dict(boxstyle="round,pad=0.2", facecolor="black", alpha=0.5))

fig.subplots_adjust(right=0.88, hspace=0.25, wspace=0.15)
cbar_ax = fig.add_axes([0.90, 0.15, 0.02, 0.70])
cbar = fig.colorbar(im, cax=cbar_ax)
cbar.set_label("Dynamic Amplitude Perturbation ($\Delta A$)", fontsize=11, fontweight="bold")

fig.suptitle("EDA 1: Physical-Layer CSI Subcarrier Dynamics Across Human Activities\nDual ESP32-S3 Transceivers (32 Multi-Receiver Carrier Channels, 4.0-Second Windows)",
             fontsize=14, fontweight="bold", y=0.98)

eda1_path = EDA_DIR / "eda1_csi_spectrogram_heatmaps.png"
fig.savefig(eda1_path, dpi=300, bbox_inches="tight")
plt.close(fig)
print(f"Saved EDA 1A to {eda1_path}")


# ============================================================================
# EDA 1B: SUBCARRIER SPATIAL CORRELATION HEATMAP (Explaining SE Attention)
# ============================================================================
print("\n[1/3b] Generating EDA 1B: Subcarrier Correlation Heatmap...")

# Compute average 32x32 correlation matrix across all active human windows
active_indices = df[df["window_label"] != "empty"].index
corr_matrices = []
for idx in active_indices[:400]:
    w = C[idx]  # [32, 200]
    corr = np.corrcoef(w)
    if not np.isnan(corr).any():
        corr_matrices.append(corr)

mean_corr = np.mean(corr_matrices, axis=0)

fig, ax = plt.subplots(figsize=(10, 8))
sns.heatmap(
    mean_corr,
    cmap="mako",
    vmin=-0.4,
    vmax=1.0,
    ax=ax,
    cbar_kws={"label": "Subcarrier Pearson Correlation ($r$)"}
)
ax.set_title("EDA 1B: Multi-Receiver Subcarrier Cross-Correlation Matrix\nDemonstrating Channel Redundancy and Justifying Squeeze-and-Excitation (SE) Attention",
             fontsize=12, fontweight="bold", pad=12)
ax.set_xlabel("Subcarrier Channel Index (1-16: RX1, 17-32: RX2)", fontsize=10, fontweight="bold")
ax.set_ylabel("Subcarrier Channel Index (1-16: RX1, 17-32: RX2)", fontsize=10, fontweight="bold")

# Add bounding boxes showing RX1 and RX2 blocks
ax.axvline(16, color="yellow", linestyle="--", linewidth=1.5)
ax.axhline(16, color="yellow", linestyle="--", linewidth=1.5)
ax.text(8, 2, "RX1 Intra-Link", color="yellow", fontweight="bold", ha="center")
ax.text(24, 18, "RX2 Intra-Link", color="yellow", fontweight="bold", ha="center")
ax.text(24, 2, "Cross-Link (RX1-RX2)", color="white", fontweight="bold", ha="center")

eda1b_path = EDA_DIR / "eda1_subcarrier_correlation_heatmap.png"
fig.savefig(eda1b_path, dpi=300, bbox_inches="tight")
plt.close(fig)
print(f"Saved EDA 1B to {eda1b_path}")


# ============================================================================
# 3. EDA 2: MULTI-METRIC STATISTICAL BOXPLOTS ACROSS ACTIVITIES
# ============================================================================
print("\n[2/3] Generating EDA 2: Statistical Boxplots...")

# Order classes by kinetic intensity
class_order = ["empty", "sit", "stand", "lie", "walk", "sit_down", "stand_up", "bend_pick", "fall"]
class_labels = ["Empty", "Sit", "Stand", "Lie", "Walk", "Sit Down", "Stand Up", "Bend/Pick", "FALL"]

# Palette: highlight Fall in Crimson Red, Empty in Gray, others in Blue/Teal
palette = {
    "empty": "#888888",
    "sit": "#4575b4",
    "stand": "#74add1",
    "lie": "#abd9e9",
    "walk": "#313695",
    "sit_down": "#fdae61",
    "stand_up": "#fee090",
    "bend_pick": "#f46d43",
    "fall": "#d73027"  # Vivid Red
}

fig, axes = plt.subplots(2, 2, figsize=(16, 11))
axes = axes.flatten()

# 1. Peak Motion Energy
sns.boxplot(
    data=df, x="window_label", y="rx1_motion_max", order=class_order,
    palette=palette, ax=axes[0], showfliers=False, width=0.6, boxprops=dict(alpha=0.85)
)
axes[0].set_title("(a) Peak Kinematic Motion Energy ($E_{max}$)\nHighlights Explosive Downward Fall Impulse Shock", fontsize=11, fontweight="bold")
axes[0].set_ylabel("Max Motion Energy (Arbitrary Units)", fontsize=10, fontweight="bold")
axes[0].set_xlabel("")
axes[0].set_xticklabels(class_labels, rotation=25, ha="right", fontsize=9)
axes[0].grid(True, linestyle=":", alpha=0.6)

# 2. Dynamic Amplitude Fluctuation (Standard Deviation sigma)
sns.boxplot(
    data=df, x="window_label", y="rx1_sd_mean", order=class_order,
    palette=palette, ax=axes[1], showfliers=False, width=0.6, boxprops=dict(alpha=0.85)
)
axes[1].set_title("(b) Temporal Amplitude Fluctuation ($\sigma_{mean}$)\nDistinguishes Sustained Motion (Walk/Fall) from Static Posture", fontsize=11, fontweight="bold")
axes[1].set_ylabel("Mean Amplitude Standard Deviation ($\sigma$)", fontsize=10, fontweight="bold")
axes[1].set_xlabel("")
axes[1].set_xticklabels(class_labels, rotation=25, ha="right", fontsize=9)
axes[1].grid(True, linestyle=":", alpha=0.6)

# 3. Cross-Receiver Motion Correlation
sns.boxplot(
    data=df, x="window_label", y="xrx_motion_corr", order=class_order,
    palette=palette, ax=axes[2], showfliers=False, width=0.6, boxprops=dict(alpha=0.85)
)
axes[2].set_title("(c) Cross-Receiver Spatial Motion Correlation ($r_{RX1, RX2}$)\nDemonstrates Simultaneous Dual-Link Multi-Angle Disturbance", fontsize=11, fontweight="bold")
axes[2].set_ylabel("Cross-Link Correlation ($r$)", fontsize=10, fontweight="bold")
axes[2].set_xlabel("Activity Class", fontsize=10, fontweight="bold")
axes[2].set_xticklabels(class_labels, rotation=25, ha="right", fontsize=9)
axes[2].grid(True, linestyle=":", alpha=0.6)

# 4. Doppler Power in 3.0 - 8.0 Hz Band
sns.boxplot(
    data=df, x="window_label", y="rx1_pc1_frac_3_8Hz", order=class_order,
    palette=palette, ax=axes[3], showfliers=False, width=0.6, boxprops=dict(alpha=0.85)
)
axes[3].set_title("(d) Doppler Energy Fraction in 3.0–8.0 Hz Kinetic Band\nCaptures Rapid Torso Velocity During Acceleration", fontsize=11, fontweight="bold")
axes[3].set_ylabel("Power Spectral Fraction (3–8 Hz)", fontsize=10, fontweight="bold")
axes[3].set_xlabel("Activity Class", fontsize=10, fontweight="bold")
axes[3].set_xticklabels(class_labels, rotation=25, ha="right", fontsize=9)
axes[3].grid(True, linestyle=":", alpha=0.6)

fig.suptitle("EDA 2: Physical Feature Distributions Across Human Activities and Postures\nEmpirical Validation on 2,401 4-Second Sensing Windows from 6 Unseen Subjects",
             fontsize=14, fontweight="bold", y=0.98)
plt.tight_layout(rect=[0, 0, 1, 0.95])

eda2_path = EDA_DIR / "eda2_activity_features_boxplot.png"
fig.savefig(eda2_path, dpi=300, bbox_inches="tight")
plt.close(fig)
print(f"Saved EDA 2 to {eda2_path}")


# ============================================================================
# 4. EDA 3: HIGH-DIMENSIONAL FEATURE MANIFOLD (PCA & t-SNE CLUSTER PROJECTIONS)
# ============================================================================
print("\n[3/3] Generating EDA 3: PCA & t-SNE Feature Space Projections...")

# Select numeric feature columns (excluding metadata)
feature_cols = [c for c in df.columns if c not in [
    "session_id", "subject", "take_id", "activity_label", "window_label", "position", "t_start", "source", "kind"
]]

X = df[feature_cols].values
# Handle any NaNs if present
X = np.nan_to_num(X, nan=0.0)

# Standardize
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)

# 1. Compute PCA
pca = PCA(n_components=2, random_state=42)
X_pca = pca.fit_transform(X_scaled)
var_explained = pca.explained_variance_ratio_ * 100

# 2. Compute t-SNE (subsampled for speed and clean visualization)
print("Computing 2D t-SNE embedding (2,401 points)...")
tsne = TSNE(n_components=2, perplexity=35, n_iter_without_progress=300, random_state=42, n_jobs=4)
X_tsne = tsne.fit_transform(X_scaled)

# Plot side-by-side
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(18, 8))

# Map labels to 6 broad viva presentation categories
display_map = {
    "empty": "Empty Room",
    "fall": "Emergency Fall",
    "walk": "Walking Gait",
    "sit": "Sitting Posture",
    "stand": "Standing Posture",
    "lie": "Lying Posture",
    "sit_down": "Sit Down Transition",
    "stand_up": "Stand Up Transition",
    "bend_pick": "Bend & Pick (Look-Alike)"
}
df_plot = pd.DataFrame({
    "PCA1": X_pca[:, 0],
    "PCA2": X_pca[:, 1],
    "tSNE1": X_tsne[:, 0],
    "tSNE2": X_tsne[:, 1],
    "Activity": df["window_label"].map(display_map)
})

plot_order = [
    "Empty Room",
    "Sitting Posture",
    "Standing Posture",
    "Lying Posture",
    "Walking Gait",
    "Sit Down Transition",
    "Stand Up Transition",
    "Bend & Pick (Look-Alike)",
    "Emergency Fall"
]

color_map = {
    "Empty Room": "#888888",
    "Sitting Posture": "#4575b4",
    "Standing Posture": "#74add1",
    "Lying Posture": "#abd9e9",
    "Walking Gait": "#313695",
    "Sit Down Transition": "#fdae61",
    "Stand Up Transition": "#fee090",
    "Bend & Pick (Look-Alike)": "#f46d43",
    "Emergency Fall": "#d73027"
}

# Panel A: PCA
sns.scatterplot(
    data=df_plot, x="PCA1", y="PCA2", hue="Activity", hue_order=plot_order,
    palette=color_map, s=35, alpha=0.75, ax=ax1, edgecolor="k", linewidth=0.2
)
ax1.set_title(f"(a) Linear Manifold: Principal Component Analysis (PCA)\nPC1 ({var_explained[0]:.1f}% variance) vs PC2 ({var_explained[1]:.1f}% variance)",
              fontsize=12, fontweight="bold", pad=10)
ax1.set_xlabel(f"Principal Component 1 ({var_explained[0]:.1f}% Variance)", fontsize=10, fontweight="bold")
ax1.set_ylabel(f"Principal Component 2 ({var_explained[1]:.1f}% Variance)", fontsize=10, fontweight="bold")
ax1.legend(loc="upper right", frameon=True, fontsize=9)
ax1.grid(True, linestyle=":", alpha=0.5)

# Panel B: t-SNE
sns.scatterplot(
    data=df_plot, x="tSNE1", y="tSNE2", hue="Activity", hue_order=plot_order,
    palette=color_map, s=35, alpha=0.75, ax=ax2, edgecolor="k", linewidth=0.2
)
ax2.set_title("(b) Non-Linear Manifold: t-SNE 2D Cluster Embedding\nReveals Natural Activity Separability & Non-Linear Boundary Margins",
              fontsize=12, fontweight="bold", pad=10)
ax2.set_xlabel("t-SNE Dimension 1", fontsize=10, fontweight="bold")
ax2.set_ylabel("t-SNE Dimension 2", fontsize=10, fontweight="bold")
ax2.legend(loc="upper right", frameon=True, fontsize=9)
ax2.grid(True, linestyle=":", alpha=0.5)

fig.suptitle("EDA 3: High-Dimensional RF Feature Space Clustering & Manifold Projection (2,401 Sensing Windows)\nProves Clear RF Separability While Highlighting Non-Linear Overlap Between Falls and Look-Alikes",
             fontsize=14, fontweight="bold", y=0.98)
plt.tight_layout(rect=[0, 0, 1, 0.95])

eda3_path = EDA_DIR / "eda3_feature_space_manifold.png"
fig.savefig(eda3_path, dpi=300, bbox_inches="tight")
plt.close(fig)
print(f"Saved EDA 3 to {eda3_path}")

print("\n" + "=" * 80)
print("  ALL 3 EDA FIGURES SUCCESSFULLY GENERATED!")
print("  Files:")
print(f"    1. EDA 1A (Spectrogram Heatmaps):     {eda1_path}")
print(f"    2. EDA 1B (Correlation Heatmap):       {eda1b_path}")
print(f"    3. EDA 2  (Statistical Boxplots):     {eda2_path}")
print(f"    4. EDA 3  (PCA / t-SNE Projections):  {eda3_path}")
print("=" * 80)
