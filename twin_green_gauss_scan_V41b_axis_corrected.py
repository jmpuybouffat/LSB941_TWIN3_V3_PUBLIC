# ============================================================
# BYTE NDT - LSB941 TWIN V4.1b
# Green + Gaussian scan with validated reference-frame correction
#
# Purpose:
#   Correct coordinate mapping between the validated EDM reference
#   frame and the focal-law / PA frame before validating the
#   Green+Gauss EDM response.
#
# Public wording:
#   The public images and CSV comments use neutral wording:
#   "validated reference EDM list" / "reference frame".
#
# Axis mapping:
#       model_x = reference_y
#       model_y = reference_x
#
# Outputs:
#   04_EDM_RESPONSE/green_gauss_V41b_EDM_response_axis_corrected_2D8x8.csv
#   05_3D_SCAN/green_gauss_V41b_scan_axis_corrected_2D8x8.csv
#   06_IMAGES/BYTE_NDT_V41b_axis_corrected_scan.png
#   06_IMAGES/BYTE_NDT_V41b_axis_corrected_EDM_response.png
#   08_EXPORT_FOR_STREAMLIT/...
# ============================================================

from pathlib import Path
import shutil
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(r"D:\PROJET_BYTENDT_AI\01_SCRIPTS\09_RESULTS_REPORTS\LSB941_TWIN_V1")

INPUT_DIR = BASE_DIR / "01_INPUTS_VALIDATED_GEOMETRY"
EXPORT_DIR = BASE_DIR / "08_EXPORT_FOR_STREAMLIT"
EDM_DIR = BASE_DIR / "04_EDM_RESPONSE"
SCAN_DIR = BASE_DIR / "05_3D_SCAN"
IMG_DIR = BASE_DIR / "06_IMAGES"
STREAMLIT_DIR = BASE_DIR / "08_EXPORT_FOR_STREAMLIT"

for d in [EDM_DIR, SCAN_DIR, IMG_DIR, STREAMLIT_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# Local source file name. Public outputs use neutral wording.
EDM_FILE = INPUT_DIR / "EDM_Tumelo_transformed.csv"

HW_A = EXPORT_DIR / "hardware_export_A_PA1_to_C1_2D8x8.csv"
HW_B = EXPORT_DIR / "hardware_export_B_PA2_to_C2_2D8x8.csv"


# ============================================================
# PHYSICAL PARAMETERS
# ============================================================

FREQ_HZ = 5.0e6
C_STEEL_MS = 3230.0
ALPHA_NP_PER_MM = 0.001

WAVELENGTH_MM = (C_STEEL_MS / FREQ_HZ) * 1000.0
K_RAD_PER_MM = 2.0 * np.pi / WAVELENGTH_MM
OMEGA_RAD_PER_US = 2.0 * np.pi * FREQ_HZ * 1e-6

Z_PLANE_MM = -51.8

SIGMA_MM = 22.0
SPOT_SIGMA_MM = 6.0

NX = 140
NY = 140


# ============================================================
# UTILITIES
# ============================================================

def read_csv_robust(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing file: {path}")

    for sep in [",", ";", r"\s+"]:
        try:
            df = pd.read_csv(path, sep=sep, engine="python")
            if df.shape[1] >= 2:
                return df
        except Exception:
            pass

    raise ValueError(f"Cannot read CSV file: {path}")


def find_col(df: pd.DataFrame, names: list[str]) -> str | None:
    lower = {str(c).lower(): c for c in df.columns}
    for n in names:
        if n.lower() in lower:
            return lower[n.lower()]
    return None


def read_reference_edm_axis_corrected(path: Path) -> pd.DataFrame:
    rows = []

    with open(path, "r", encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            parts = line.replace(",", ".").replace(";", " ").split()
            if len(parts) < 3:
                continue

            try:
                reference_x = float(parts[0])
                reference_y = float(parts[1])
                reference_z = float(parts[2])
                rows.append((reference_x, reference_y, reference_z))
            except ValueError:
                continue

    if not rows:
        raise ValueError("No valid reference EDM rows found.")

    df = pd.DataFrame(rows, columns=["reference_x", "reference_y", "reference_z"])
    df.insert(0, "edm_id", [f"EDM_{i + 1:02d}" for i in range(len(df))])

    if len(df) == 11:
        df["side"] = ["SIDE_A"] * 8 + ["SIDE_B"] * 3
    else:
        df["side"] = "SIDE_UNKNOWN"

    # Axis correction:
    # reference_x corresponds to focal-law y
    # reference_y corresponds to focal-law x
    df["edm_model_x"] = df["reference_y"]
    df["edm_model_y"] = df["reference_x"]
    df["edm_model_z"] = df["reference_z"]

    return df


def standardize_hardware_export(path: Path, condition_name: str) -> pd.DataFrame:
    df = read_csv_robust(path)

    col_scan = find_col(df, ["scan_id", "scan_index", "shot_id"])
    col_element = find_col(df, ["element_id", "element", "element_index"])
    col_delay = find_col(df, ["delay_us", "delay", "delay_microsecond"])

    col_xe = find_col(df, ["x_element", "element_x", "x_elem"])
    col_ye = find_col(df, ["y_element", "element_y", "y_elem"])
    col_ze = find_col(df, ["z_element", "element_z", "z_elem"])

    col_fx = find_col(df, ["focus_x", "x_focus", "focal_x"])
    col_fy = find_col(df, ["focus_y", "y_focus", "focal_y"])
    col_fz = find_col(df, ["focus_z", "z_focus", "focal_z"])

    required = {
        "scan_id": col_scan,
        "element_id": col_element,
        "delay_us": col_delay,
        "x_element": col_xe,
        "y_element": col_ye,
        "z_element": col_ze,
        "focus_x": col_fx,
        "focus_y": col_fy,
        "focus_z": col_fz,
    }

    missing = [k for k, v in required.items() if v is None]
    if missing:
        raise ValueError(f"{path.name} missing columns: {missing}")

    out = pd.DataFrame({
        "condition": condition_name,
        "scan_id": df[col_scan],
        "element_id": df[col_element],
        "delay_us": df[col_delay],
        "x_element": df[col_xe],
        "y_element": df[col_ye],
        "z_element": df[col_ze],
        "focus_x": df[col_fx],
        "focus_y": df[col_fy],
        "focus_z": df[col_fz],
    })

    for col in [
        "scan_id",
        "element_id",
        "delay_us",
        "x_element",
        "y_element",
        "z_element",
        "focus_x",
        "focus_y",
        "focus_z",
    ]:
        out[col] = pd.to_numeric(out[col], errors="coerce")

    out = out.dropna()
    return out


# ============================================================
# GRID
# ============================================================

def make_corrected_grid(edm_df: pd.DataFrame, hw: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    x_min = min(float(edm_df["edm_model_x"].min()), float(hw["focus_x"].min())) - 25.0
    x_max = max(float(edm_df["edm_model_x"].max()), float(hw["focus_x"].max())) + 25.0

    y_min = min(float(edm_df["edm_model_y"].min()), float(hw["focus_y"].min())) - 25.0
    y_max = max(float(edm_df["edm_model_y"].max()), float(hw["focus_y"].max())) + 25.0

    x = np.linspace(x_min, x_max, NX)
    y = np.linspace(y_min, y_max, NY)

    X, Y = np.meshgrid(x, y)
    return X, Y


# ============================================================
# GREEN + GAUSS
# ============================================================

def green_sum_for_scan(g: pd.DataFrame, X: np.ndarray, Y: np.ndarray, z_plane: float) -> np.ndarray:
    complex_field = np.zeros_like(X, dtype=np.complex128)

    for _, e in g.iterrows():
        xe = float(e["x_element"])
        ye = float(e["y_element"])
        ze = float(e["z_element"])
        delay_us = float(e["delay_us"])

        R = np.sqrt((X - xe) ** 2 + (Y - ye) ** 2 + (z_plane - ze) ** 2)
        R = np.maximum(R, 1e-6)

        phase = K_RAD_PER_MM * R - OMEGA_RAD_PER_US * delay_us
        attenuation = np.exp(-ALPHA_NP_PER_MM * R)

        G = attenuation * np.exp(1j * phase) / R
        complex_field += G

    return complex_field


def gaussian_envelope_from_focus(g: pd.DataFrame, X: np.ndarray, Y: np.ndarray, z_plane: float) -> np.ndarray:
    fx = float(g["focus_x"].mean())
    fy = float(g["focus_y"].mean())
    fz = float(g["focus_z"].mean())

    d2 = (X - fx) ** 2 + (Y - fy) ** 2 + (z_plane - fz) ** 2
    envelope = np.exp(-d2 / (2.0 * SIGMA_MM ** 2))
    return envelope


def compute_green_gauss_scan(hw: pd.DataFrame, X: np.ndarray, Y: np.ndarray) -> tuple[np.ndarray, pd.DataFrame]:
    scan_image = np.zeros_like(X, dtype=float)
    rows = []

    scan_ids = sorted(hw["scan_id"].dropna().unique())

    for scan_id in scan_ids:
        g = hw[hw["scan_id"] == scan_id]

        if len(g) == 0:
            continue

        green = green_sum_for_scan(g, X, Y, Z_PLANE_MM)
        gauss = gaussian_envelope_from_focus(g, X, Y, Z_PLANE_MM)

        response = np.abs(green) * gauss

        scan_image = np.maximum(scan_image, response)

        rows.append({
            "scan_id": int(scan_id),
            "focus_x": float(g["focus_x"].mean()),
            "focus_y": float(g["focus_y"].mean()),
            "focus_z": float(g["focus_z"].mean()),
            "condition": str(g["condition"].iloc[0]),
            "max_response_raw": float(np.max(response)),
            "mean_response_raw": float(np.mean(response)),
            "sigma_mm": SIGMA_MM,
            "n_elements": int(g["element_id"].nunique()),
            "physics_level": "V4.1b Green + Gaussian with validated reference-frame correction",
        })

    if np.max(scan_image) > 0:
        scan_percent = 100.0 * scan_image / np.max(scan_image)
    else:
        scan_percent = scan_image

    return scan_percent, pd.DataFrame(rows)


def create_edm_spots_axis_corrected(
    edm_df: pd.DataFrame,
    X: np.ndarray,
    Y: np.ndarray,
    scan_image: np.ndarray,
) -> tuple[np.ndarray, pd.DataFrame]:
    x_axis = X[0, :]
    y_axis = Y[:, 0]

    spot_image = np.zeros_like(X, dtype=float)
    rows = []

    for _, edm in edm_df.iterrows():
        mx = float(edm["edm_model_x"])
        my = float(edm["edm_model_y"])

        ix = int(np.argmin(np.abs(x_axis - mx)))
        iy = int(np.argmin(np.abs(y_axis - my)))

        amp = float(scan_image[iy, ix])

        d2 = (X - mx) ** 2 + (Y - my) ** 2
        spot = amp * np.exp(-d2 / (2.0 * SPOT_SIGMA_MM ** 2))

        spot_image = np.maximum(spot_image, spot)

        if amp >= 60.0:
            status = "DETECTED"
        elif amp >= 35.0:
            status = "TO_BE_CONFIRMED"
        else:
            status = "LOW_RESPONSE"

        rows.append({
            "edm_id": edm["edm_id"],
            "side": edm["side"],
            "reference_x": float(edm["reference_x"]),
            "reference_y": float(edm["reference_y"]),
            "reference_z": float(edm["reference_z"]),
            "edm_model_x": mx,
            "edm_model_y": my,
            "edm_model_z": float(edm["edm_model_z"]),
            "green_gauss_response_percent": amp,
            "green_gauss_response_db": 20.0 * np.log10(max(amp, 1e-9) / 100.0),
            "spot_sigma_mm": SPOT_SIGMA_MM,
            "status": status,
            "axis_correction": "model axes mapped from validated EDM reference frame",
            "physics_level": "V4.1b Green+Gauss sampled scan with corrected reference frame",
        })

    return spot_image, pd.DataFrame(rows)


# ============================================================
# EXPORT
# ============================================================

def image_to_dataframe(X: np.ndarray, Y: np.ndarray, image: np.ndarray, label: str) -> pd.DataFrame:
    return pd.DataFrame({
        "label": label,
        "model_x_mm": X.ravel(),
        "model_y_mm": Y.ravel(),
        "z_mm": np.full(X.size, Z_PLANE_MM),
        "amplitude_percent": image.ravel(),
        "frequency_hz": FREQ_HZ,
        "velocity_m_per_s": C_STEEL_MS,
        "wavelength_mm": WAVELENGTH_MM,
        "sigma_mm": SIGMA_MM,
        "spot_sigma_mm": SPOT_SIGMA_MM,
        "axis_correction": "model axes mapped from validated EDM reference frame",
        "physics_level": "V4.1b Green + Gaussian + corrected reference-frame sampled scan",
    })


# ============================================================
# PLOTS
# ============================================================

def plot_axis_corrected_scan(X: np.ndarray, Y: np.ndarray, scan_image: np.ndarray, edm_df: pd.DataFrame) -> Path:
    out = IMG_DIR / "BYTE_NDT_V41b_axis_corrected_scan.png"

    fig = plt.figure(figsize=(14, 10))
    fig.suptitle(
        "BYTE NDT - LSB941 V4.1b Axis-Corrected Green+Gauss Scan",
        fontsize=16,
        fontweight="bold",
    )

    ax = fig.add_subplot(1, 1, 1)

    im = ax.imshow(
        scan_image,
        origin="lower",
        extent=[X.min(), X.max(), Y.min(), Y.max()],
        aspect="auto",
        vmin=0,
        vmax=100,
    )

    ax.scatter(edm_df["edm_model_x"], edm_df["edm_model_y"], marker="x", s=100)

    for _, r in edm_df.iterrows():
        ax.text(r["edm_model_x"], r["edm_model_y"], r["edm_id"], fontsize=8)

    ax.set_title("Corrected reference frame for EDM / focal-law alignment")
    ax.set_xlabel("Model X (mm)")
    ax.set_ylabel("Model Y (mm)")
    ax.grid(True)

    fig.colorbar(im, ax=ax, label="Amplitude (%)")

    plt.tight_layout(rect=[0, 0, 1, 0.94])
    fig.savefig(out, dpi=200)
    plt.close(fig)

    shutil.copy2(out, STREAMLIT_DIR / out.name)
    return out


def plot_axis_corrected_edm_response(
    X: np.ndarray,
    Y: np.ndarray,
    spot_image: np.ndarray,
    edm_report: pd.DataFrame,
) -> Path:
    out = IMG_DIR / "BYTE_NDT_V41b_axis_corrected_EDM_response.png"

    fig = plt.figure(figsize=(14, 10))
    fig.suptitle(
        "BYTE NDT - LSB941 V4.1b Axis-Corrected EDM Response",
        fontsize=16,
        fontweight="bold",
    )

    ax = fig.add_subplot(1, 1, 1)

    im = ax.imshow(
        spot_image,
        origin="lower",
        extent=[X.min(), X.max(), Y.min(), Y.max()],
        aspect="auto",
        vmin=0,
        vmax=100,
    )

    ax.scatter(edm_report["edm_model_x"], edm_report["edm_model_y"], marker="x", s=100)

    for _, r in edm_report.iterrows():
        label = f"{r['edm_id']}\n{r['green_gauss_response_percent']:.1f}%"
        ax.text(r["edm_model_x"], r["edm_model_y"], label, fontsize=8)

    ax.set_title("Localized EDM spots after reference-frame correction")
    ax.set_xlabel("Model X (mm)")
    ax.set_ylabel("Model Y (mm)")
    ax.grid(True)

    fig.colorbar(im, ax=ax, label="EDM response amplitude (%)")

    plt.tight_layout(rect=[0, 0, 1, 0.94])
    fig.savefig(out, dpi=200)
    plt.close(fig)

    shutil.copy2(out, STREAMLIT_DIR / out.name)
    return out


# ============================================================
# MAIN
# ============================================================

def main() -> None:
    print("BYTE NDT - V4.1b Green + Gauss + axis-corrected scan")
    print(f"Frequency   : {FREQ_HZ / 1e6:.2f} MHz")
    print(f"Velocity    : {C_STEEL_MS:.1f} m/s")
    print(f"Wavelength  : {WAVELENGTH_MM:.4f} mm")
    print(f"Z plane     : {Z_PLANE_MM:.2f} mm")
    print(f"Sigma       : {SIGMA_MM:.2f} mm")
    print(f"Spot sigma  : {SPOT_SIGMA_MM:.2f} mm")

    print(f"Reading validated reference EDM file: {EDM_FILE}")
    edm_df = read_reference_edm_axis_corrected(EDM_FILE)

    print(
        edm_df[
            [
                "edm_id",
                "reference_x",
                "reference_y",
                "edm_model_x",
                "edm_model_y",
                "reference_z",
                "side",
            ]
        ]
    )

    print(f"Reading hardware A: {HW_A}")
    hw_a = standardize_hardware_export(HW_A, "A_PA1_to_C1")

    print(f"Reading hardware B: {HW_B}")
    hw_b = standardize_hardware_export(HW_B, "B_PA2_to_C2")

    hw_total = pd.concat([hw_a, hw_b], ignore_index=True)

    print("Building corrected grid")
    X, Y = make_corrected_grid(edm_df, hw_total)

    print("Computing corrected Green+Gauss scan")
    scan_image, scan_table = compute_green_gauss_scan(hw_total, X, Y)

    print("Creating corrected localized EDM response spots")
    spot_image, edm_report = create_edm_spots_axis_corrected(edm_df, X, Y, scan_image)

    print("Exporting CSV files")
    scan_df = image_to_dataframe(X, Y, scan_image, "V41b_axis_corrected_scan")
    spot_df = image_to_dataframe(X, Y, spot_image, "V41b_axis_corrected_EDM_spots")

    out_scan = SCAN_DIR / "green_gauss_V41b_scan_axis_corrected_2D8x8.csv"
    out_scan_table = SCAN_DIR / "green_gauss_V41b_scan_table_axis_corrected_2D8x8.csv"
    out_spot = EDM_DIR / "green_gauss_V41b_EDM_spot_image_axis_corrected_2D8x8.csv"
    out_report = EDM_DIR / "green_gauss_V41b_EDM_response_axis_corrected_2D8x8.csv"

    scan_df.to_csv(out_scan, index=False)
    scan_table.to_csv(out_scan_table, index=False)
    spot_df.to_csv(out_spot, index=False)
    edm_report.to_csv(out_report, index=False)

    for p in [out_scan, out_scan_table, out_spot, out_report]:
        shutil.copy2(p, STREAMLIT_DIR / p.name)

    print("Plotting corrected public images")
    img_scan = plot_axis_corrected_scan(X, Y, scan_image, edm_df)
    img_response = plot_axis_corrected_edm_response(X, Y, spot_image, edm_report)

    print("Done V4.1b.")
    print(f"Scan CSV      : {out_scan}")
    print(f"Scan table    : {out_scan_table}")
    print(f"EDM spot CSV  : {out_spot}")
    print(f"EDM report    : {out_report}")
    print(f"Image scan    : {img_scan}")
    print(f"Image response: {img_response}")
    print(f"Streamlit exports updated: {STREAMLIT_DIR}")


if __name__ == "__main__":
    main()