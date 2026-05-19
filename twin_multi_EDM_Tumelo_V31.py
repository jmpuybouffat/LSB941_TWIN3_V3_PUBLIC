# ============================================================
# BYTE NDT - LSB941 TWIN V3.1
# Tumelo multi-EDM detection report + detection map
#
# Input:
#   01_INPUTS_VALIDATED_GEOMETRY/EDM_Tumelo_transformed.csv
#   05_3D_SCAN/scan3D_groove_total_1D16.csv
#   05_3D_SCAN/scan3D_groove_total_1D32.csv
#   05_3D_SCAN/scan3D_groove_total_2D8x8.csv
#
# Output:
#   07_REPORTS/BYTE_NDT_Tumelo_EDM_detection_report_ALL.csv
#   06_IMAGES/BYTE_NDT_Tumelo_EDM_detection_map.png
#   08_EXPORT_FOR_STREAMLIT/...
# ============================================================

from pathlib import Path
import shutil
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


BASE_DIR = Path(r"D:\PROJET_BYTENDT_AI\01_SCRIPTS\09_RESULTS_REPORTS\LSB941_TWIN_V1")

INPUT_DIR = BASE_DIR / "01_INPUTS_VALIDATED_GEOMETRY"
SCAN_DIR = BASE_DIR / "05_3D_SCAN"
IMG_DIR = BASE_DIR / "06_IMAGES"
REPORT_DIR = BASE_DIR / "07_REPORTS"
STREAMLIT_DIR = BASE_DIR / "08_EXPORT_FOR_STREAMLIT"

IMG_DIR.mkdir(parents=True, exist_ok=True)
REPORT_DIR.mkdir(parents=True, exist_ok=True)
STREAMLIT_DIR.mkdir(parents=True, exist_ok=True)

EDM_FILE = INPUT_DIR / "EDM_Tumelo_transformed.csv"

CONFIGS = ["1D16", "1D32", "2D8x8"]


def read_edm_tumelo(path: Path) -> pd.DataFrame:
    """
    Reads Tumelo EDM list.
    Expected format: X;Y;Z with decimal comma or decimal point.
    No header assumed.
    """
    if not path.exists():
        raise FileNotFoundError(f"Missing EDM Tumelo file: {path}")

    rows = []
    with open(path, "r", encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            # allow ; , whitespace, decimal comma
            parts = line.replace(",", ".").replace(";", " ").split()

            if len(parts) < 3:
                continue

            try:
                x, y, z = float(parts[0]), float(parts[1]), float(parts[2])
                rows.append((x, y, z))
            except ValueError:
                continue

    if not rows:
        raise ValueError(f"No valid EDM XYZ points found in {path}")

    df = pd.DataFrame(rows, columns=["edm_x", "edm_y", "edm_z"])
    df.insert(0, "edm_id", [f"EDM_{i+1:02d}" for i in range(len(df))])

    # Temporary side attribution:
    # positive/negative Y split. This can be refined after groove validation.
    y_mid = df["edm_y"].median()
    df["side"] = np.where(df["edm_y"] >= y_mid, "SIDE_A", "SIDE_B")

    return df


def read_csv_robust(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing scan file: {path}")

    for sep in [",", ";", r"\s+"]:
        try:
            df = pd.read_csv(path, sep=sep, engine="python")
            if df.shape[1] >= 2:
                return df
        except Exception:
            pass

    raise ValueError(f"Cannot read CSV: {path}")


def find_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
    lower = {str(c).lower(): c for c in df.columns}
    for name in candidates:
        if name.lower() in lower:
            return lower[name.lower()]
    return None


def load_scan(config: str) -> pd.DataFrame:
    path = SCAN_DIR / f"scan3D_groove_total_{config}.csv"
    df = read_csv_robust(path)

    required_candidates = {
        "scan_position_mm": ["scan_position_mm", "scan_pos_mm", "x_scan", "scan_id"],
        "amplitude_percent": ["amplitude_percent", "edm_echo_percent", "beam_percent", "amplitude"],
        "amplitude_db": ["amplitude_db", "beam_db"],
        "focus_x": ["focus_x", "x", "max_x"],
        "focus_y": ["focus_y", "y", "max_y"],
        "focus_z": ["focus_z", "z", "max_z"],
        "condition": ["condition"],
    }

    out = pd.DataFrame()

    for standard, candidates in required_candidates.items():
        col = find_col(df, candidates)
        if col is not None:
            out[standard] = df[col]
        else:
            if standard == "condition":
                out[standard] = "A+B"
            elif standard == "amplitude_db":
                out[standard] = np.nan
            else:
                out[standard] = np.nan

    out["config"] = config

    # Numeric conversion
    for c in ["scan_position_mm", "amplitude_percent", "amplitude_db", "focus_x", "focus_y", "focus_z"]:
        out[c] = pd.to_numeric(out[c], errors="coerce")

    out = out.dropna(subset=["amplitude_percent"])
    return out


def compute_detection_for_edm(edm_row: pd.Series, scan_df: pd.DataFrame, config: str) -> dict:
    """
    Associates each EDM with nearest focal/scan response.

    Current V3.1 logic:
    - spatial distance to focus_x/focus_y/focus_z when available
    - if scan coordinates are incomplete, uses strongest local response
    - reports amplitude and -6 dB equivalent width
    """

    edm_xyz = np.array([edm_row["edm_x"], edm_row["edm_y"], edm_row["edm_z"]], dtype=float)

    focus_cols_ok = scan_df[["focus_x", "focus_y", "focus_z"]].notna().all(axis=1)

    if focus_cols_ok.any():
        sub = scan_df.loc[focus_cols_ok].copy()
        focus_xyz = sub[["focus_x", "focus_y", "focus_z"]].to_numpy(dtype=float)
        dist = np.linalg.norm(focus_xyz - edm_xyz[None, :], axis=1)

        # Combine distance and amplitude: nearest strong response
        amp = sub["amplitude_percent"].to_numpy(dtype=float)
        amp_norm = amp / max(np.nanmax(amp), 1e-12)

        score = amp_norm / (1.0 + dist / 10.0)
        best_local_idx = int(np.nanargmax(score))
        best = sub.iloc[best_local_idx]
        best_distance = float(dist[best_local_idx])
    else:
        sub = scan_df.copy()
        best_idx = int(np.nanargmax(sub["amplitude_percent"].to_numpy(dtype=float)))
        best = sub.iloc[best_idx]
        best_distance = np.nan

    max_amp = float(best["amplitude_percent"])
    scan_pos = float(best["scan_position_mm"]) if np.isfinite(best["scan_position_mm"]) else np.nan
    condition = str(best["condition"])

    # -6 dB width based on global scan response near strongest response
    amp_all = scan_df["amplitude_percent"].to_numpy(dtype=float)
    scan_all = scan_df["scan_position_mm"].to_numpy(dtype=float)

    threshold = max_amp * 10 ** (-6.0 / 20.0)

    if np.isfinite(scan_pos):
        local_window = np.abs(scan_all - scan_pos) <= 25.0
    else:
        local_window = np.ones(len(scan_df), dtype=bool)

    mask = (amp_all >= threshold) & local_window & np.isfinite(scan_all)

    if np.any(mask):
        length_minus_6db = float(np.nanmax(scan_all[mask]) - np.nanmin(scan_all[mask]))
    else:
        length_minus_6db = 0.0

    if max_amp >= 60.0:
        status = "DETECTED"
    elif max_amp >= 35.0:
        status = "TO_BE_CONFIRMED"
    else:
        status = "NOT_DETECTED"

    return {
        "edm_id": edm_row["edm_id"],
        "side": edm_row["side"],
        "config": config,
        "condition": condition,
        "edm_x": float(edm_row["edm_x"]),
        "edm_y": float(edm_row["edm_y"]),
        "edm_z": float(edm_row["edm_z"]),
        "best_scan_position_mm": scan_pos,
        "best_focus_x": float(best["focus_x"]) if np.isfinite(best["focus_x"]) else np.nan,
        "best_focus_y": float(best["focus_y"]) if np.isfinite(best["focus_y"]) else np.nan,
        "best_focus_z": float(best["focus_z"]) if np.isfinite(best["focus_z"]) else np.nan,
        "distance_to_best_focus_mm": best_distance,
        "max_amplitude_percent": max_amp,
        "length_minus_6db_mm": length_minus_6db,
        "status": status,
        "comment_fr": "Détection V3.1 estimée à partir de la liste EDM Tumelo et du scan 3D de gorge.",
        "comment_en": "V3.1 detection estimated from Tumelo EDM list and 3D groove scan.",
    }


def build_multi_edm_report(edm_df: pd.DataFrame) -> pd.DataFrame:
    all_rows = []

    for config in CONFIGS:
        print(f"Loading scan for {config}")
        scan_df = load_scan(config)

        for _, edm in edm_df.iterrows():
            row = compute_detection_for_edm(edm, scan_df, config)
            all_rows.append(row)

    report = pd.DataFrame(all_rows)

    # Best config per EDM
    report["rank_amp"] = report.groupby("edm_id")["max_amplitude_percent"].rank(
        method="first", ascending=False
    )

    report["best_config_for_edm"] = np.where(report["rank_amp"] == 1, "YES", "NO")
    report = report.drop(columns=["rank_amp"])

    return report


def plot_multi_edm_map(edm_df: pd.DataFrame, report: pd.DataFrame) -> Path:
    out_img = IMG_DIR / "BYTE_NDT_Tumelo_EDM_detection_map.png"

    best = report[report["best_config_for_edm"] == "YES"].copy()

    fig = plt.figure(figsize=(16, 10))
    fig.suptitle("BYTE NDT - LSB941 V3.1 Tumelo Multi-EDM Detection Map", fontsize=16, fontweight="bold")

    ax1 = fig.add_subplot(2, 2, 1)
    for side, g in edm_df.groupby("side"):
        ax1.scatter(g["edm_x"], g["edm_y"], label=side, s=80)
        for _, r in g.iterrows():
            ax1.text(r["edm_x"], r["edm_y"], r["edm_id"], fontsize=8)

    ax1.set_title("Tumelo EDM positions / Positions EDM Tumelo")
    ax1.set_xlabel("X (mm)")
    ax1.set_ylabel("Y (mm)")
    ax1.grid(True)
    ax1.legend()

    ax2 = fig.add_subplot(2, 2, 2)
    ax2.bar(best["edm_id"], best["max_amplitude_percent"])
    ax2.set_title("Best detection amplitude per EDM")
    ax2.set_ylabel("Amplitude (%)")
    ax2.tick_params(axis="x", rotation=45)
    ax2.grid(True, axis="y")

    ax3 = fig.add_subplot(2, 2, 3)
    colors = []
    for s in best["status"]:
        if s == "DETECTED":
            colors.append("green")
        elif s == "TO_BE_CONFIRMED":
            colors.append("orange")
        else:
            colors.append("red")

    ax3.scatter(best["edm_x"], best["edm_y"], c=colors, s=120)
    for _, r in best.iterrows():
        ax3.text(r["edm_x"], r["edm_y"], f"{r['edm_id']}\n{r['config']}", fontsize=8)

    ax3.set_title("Best PA configuration per EDM")
    ax3.set_xlabel("X (mm)")
    ax3.set_ylabel("Y (mm)")
    ax3.grid(True)

    ax4 = fig.add_subplot(2, 2, 4)
    ax4.axis("off")
    n_edm = edm_df["edm_id"].nunique()
    n_detected = (best["status"] == "DETECTED").sum()
    n_confirm = (best["status"] == "TO_BE_CONFIRMED").sum()
    n_not = (best["status"] == "NOT_DETECTED").sum()

    text = (
        "V3.1 MULTI-EDM REPORT / RAPPORT MULTI-EDM V3.1\n\n"
        f"Tumelo EDM count / Nombre EDM Tumelo: {n_edm}\n"
        f"Detected / Détectées: {n_detected}\n"
        f"To be confirmed / À confirmer: {n_confirm}\n"
        f"Not detected / Non détectées: {n_not}\n\n"
        "Configurations evaluated:\n"
        "- 1D16\n"
        "- 1D32\n"
        "- 2D8x8\n\n"
        "FR:\n"
        "La carte associe chaque EDM Tumelo à la meilleure réponse\n"
        "issue des scans 3D de gorge V3.1.\n\n"
        "EN:\n"
        "The map associates each Tumelo EDM with the best response\n"
        "from the V3.1 3D groove scans."
    )
    ax4.text(0.02, 0.98, text, va="top", fontsize=11)

    plt.tight_layout(rect=[0, 0, 1, 0.94])
    fig.savefig(out_img, dpi=200)
    plt.close(fig)

    streamlit_img = STREAMLIT_DIR / out_img.name
    shutil.copy2(out_img, streamlit_img)

    return out_img


def main():
    print("BYTE NDT - V3.1 Tumelo Multi-EDM Detection")

    print(f"Reading EDM file: {EDM_FILE}")
    edm_df = read_edm_tumelo(EDM_FILE)

    print(f"Tumelo EDM count: {len(edm_df)}")
    print(edm_df)

    report = build_multi_edm_report(edm_df)

    report_path = REPORT_DIR / "BYTE_NDT_Tumelo_EDM_detection_report_ALL.csv"
    report.to_csv(report_path, index=False)

    streamlit_report = STREAMLIT_DIR / report_path.name
    shutil.copy2(report_path, streamlit_report)

    img_path = plot_multi_edm_map(edm_df, report)

    print("Done V3.1.")
    print(f"Report: {report_path}")
    print(f"Image : {img_path}")
    print(f"Streamlit exports updated: {STREAMLIT_DIR}")


if __name__ == "__main__":
    main()