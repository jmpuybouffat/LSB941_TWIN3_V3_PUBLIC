# ============================================================
# BYTE NDT - LSB941 TWIN V3 STREAMLIT APP
# Operator view + reports + hardware exports
# ============================================================

from pathlib import Path
import streamlit as st
import pandas as pd


BASE_DIR = Path(r"D:\PROJET_BYTENDT_AI\01_SCRIPTS\09_RESULTS_REPORTS\LSB941_TWIN_V1")

IMG_DIR = BASE_DIR / "06_IMAGES"
REPORT_DIR = BASE_DIR / "07_REPORTS"
EXPORT_DIR = BASE_DIR / "08_EXPORT_FOR_STREAMLIT"
BEAM_DIR = BASE_DIR / "03_BEAM_FIELD"
EDM_DIR = BASE_DIR / "04_EDM_RESPONSE"
SCAN_DIR = BASE_DIR / "05_3D_SCAN"
FOCAL_DIR = BASE_DIR / "02_FOCAL_LAWS"

CONFIGS = ["1D16", "1D32", "2D8x8"]


st.set_page_config(
    page_title="BYTE NDT - LSB941 Twin V3",
    page_icon="🟦",
    layout="wide",
)


def file_download_button(path: Path, label: str):
    if path.exists():
        with open(path, "rb") as f:
            st.download_button(
                label=label,
                data=f,
                file_name=path.name,
                mime="application/octet-stream",
            )
    else:
        st.warning(f"Missing file: {path.name}")


def read_csv_safe(path: Path):
    if not path.exists():
        return None

    for sep in [",", ";", r"\s+"]:
        try:
            df = pd.read_csv(path, sep=sep, engine="python")
            if df.shape[1] >= 2:
                return df
        except Exception:
            pass

    return None


st.title("BYTE NDT - LSB941 Twin V3")
st.subheader("Digital Twin demonstrator for blade root ultrasonic inspection")

st.markdown(
    """
This demonstrator links the complete inspection chain:

**Geometry / PA trajectories → dynamic focal laws → calibrated beam field → EDM response → 3D groove scan → operator report → hardware-oriented delay export.**

FR : Ce démonstrateur relie la chaîne complète d'examen :

**Géométrie / trajectoires PA → lois focales dynamiques → champ faisceau calibré → réponse EDM → scan 3D de gorge → rapport opérateur → export de délais orienté hardware.**
"""
)

st.divider()

# ============================================================
# GLOBAL STATUS
# ============================================================

st.header("1. Global V3 status / État global V3")

global_report = REPORT_DIR / "LSB941_TWIN_V3_detection_report_ALL_CONFIGS.csv"
df_global = read_csv_safe(global_report)

if df_global is not None:
    st.success("Global V3 report loaded successfully.")
    st.dataframe(df_global, use_container_width=True)
    file_download_button(global_report, "Download global report CSV")
else:
    st.warning("Global report not found yet.")

st.divider()

# ============================================================
# OPERATOR VIEWS
# ============================================================

st.header("2. Operator views / Vues opérateur")

selected_config = st.selectbox(
    "Select PA configuration / Choisir la configuration PA",
    CONFIGS,
    index=2,
)

image_path = IMG_DIR / f"LSB941_TWIN_V3_OPERATOR_VIEW_{selected_config}.png"
report_path = REPORT_DIR / f"LSB941_TWIN_V3_detection_report_{selected_config}.csv"

col1, col2 = st.columns([2, 1])

with col1:
    st.subheader(f"Operator view - {selected_config}")
    if image_path.exists():
        st.image(str(image_path), use_container_width=True)
        file_download_button(image_path, f"Download operator image {selected_config}")
    else:
        st.error(f"Missing image: {image_path}")

with col2:
    st.subheader("Automatic report")
    df_report = read_csv_safe(report_path)
    if df_report is not None:
        st.dataframe(df_report, use_container_width=True)
        file_download_button(report_path, f"Download report {selected_config}")
    else:
        st.warning(f"Missing report: {report_path.name}")

st.divider()

# ============================================================
# FOCAL LAWS
# ============================================================

st.header("3. Dynamic focal laws / Lois focales dynamiques")

st.markdown(
    """
The focal law files contain the dynamic delays over the full sampled scan path.

They are currently technical CSV files and can be converted to the format required by Mantis/M2M or another PA controller.

FR : Les fichiers de lois focales contiennent les retards dynamiques sur l'ensemble du chemin de scan échantillonné.

Ce sont actuellement des CSV techniques, convertibles vers le format attendu par Mantis/M2M ou une autre carte PA.
"""
)

focal_files = [
    FOCAL_DIR / f"focal_laws_A_PA1_to_C1_{selected_config}.csv",
    FOCAL_DIR / f"focal_laws_B_PA2_to_C2_{selected_config}.csv",
]

for f in focal_files:
    st.write(f.name)
    file_download_button(f, f"Download {f.name}")

st.divider()

# ============================================================
# HARDWARE EXPORT
# ============================================================

st.header("4. Hardware-oriented export / Export orienté carte PA")

st.markdown(
    """
These files are the bridge between the Twin and a real PA acquisition system.

They include:

- scan index
- element index
- delay in microseconds
- PA position
- focal point
- element position

They do not yet directly drive a specific card. They are the clean basis for conversion to Mantis/M2M, FPGA delay tables, or future Byte NDT electronics.

FR : Ces fichiers font le lien entre le Twin et un système d'acquisition PA réel.

Ils contiennent :

- indice de scan
- numéro d'élément
- retard en microsecondes
- position PA
- point focal
- position élément

Ils ne pilotent pas encore directement une carte spécifique. Ils constituent la base propre pour conversion vers Mantis/M2M, tables FPGA ou future électronique Byte NDT.
"""
)

hardware_files = [
    EXPORT_DIR / f"hardware_export_A_PA1_to_C1_{selected_config}.csv",
    EXPORT_DIR / f"hardware_export_B_PA2_to_C2_{selected_config}.csv",
]

for f in hardware_files:
    st.write(f.name)
    df_hw = read_csv_safe(f)
    if df_hw is not None:
        st.dataframe(df_hw.head(20), use_container_width=True)
        st.caption(f"{len(df_hw)} rows")
    file_download_button(f, f"Download {f.name}")

st.divider()

# ============================================================
# BEAM / EDM / SCAN DATA
# ============================================================

st.header("5. Beam field, EDM response and 3D scan data")

data_tabs = st.tabs(["Beam field", "EDM response", "3D groove scan"])

with data_tabs[0]:
    beam_file = BEAM_DIR / f"beam_field_total_{selected_config}.csv"
    st.subheader(f"Beam field - {selected_config}")
    df = read_csv_safe(beam_file)
    if df is not None:
        st.dataframe(df.head(50), use_container_width=True)
        file_download_button(beam_file, f"Download {beam_file.name}")
    else:
        st.warning(f"Missing {beam_file.name}")

with data_tabs[1]:
    edm_file = EDM_DIR / f"edm_response_total_{selected_config}.csv"
    st.subheader(f"EDM response - {selected_config}")
    df = read_csv_safe(edm_file)
    if df is not None:
        st.dataframe(df.head(50), use_container_width=True)
        file_download_button(edm_file, f"Download {edm_file.name}")
    else:
        st.warning(f"Missing {edm_file.name}")

with data_tabs[2]:
    scan_file = SCAN_DIR / f"scan3D_groove_total_{selected_config}.csv"
    st.subheader(f"3D groove scan - {selected_config}")
    df = read_csv_safe(scan_file)
    if df is not None:
        st.dataframe(df.head(50), use_container_width=True)
        file_download_button(scan_file, f"Download {scan_file.name}")
    else:
        st.warning(f"Missing {scan_file.name}")

st.divider()

# ============================================================
# TECHNICAL EXPLANATION
# ============================================================

st.header("6. Technical explanation / Explication technique")

st.markdown(
    """
### Current V3 implementation

The current V3 demonstrator generates:

- dynamic focal laws for 1D16, 1D32 and 2D8x8 configurations,
- calibrated Gaussian / CIVA-like beam fields,
- EDM response relative to geometry echo,
- calibrated 3D groove scan datasets,
- operator-view images,
- automatic bilingual reports,
- hardware-oriented delay tables.

### Important note

This version is a demonstrator and procedure-building model.  
The high-fidelity physics layers are defined in the roadmap:

- Green functions,
- Sommerfeld radiation integrals,
- Kirchhoff approximation,
- Born approximation,
- edge / GTD diffraction.

These layers are not yet fully implemented as the final industrial solver, but the V3 structure is designed to receive them.

---

### Implémentation V3 actuelle

Le démonstrateur V3 génère :

- les lois focales dynamiques pour 1D16, 1D32 et 2D8x8,
- les champs faisceau calibrés de type gaussien / CIVA-like,
- la réponse EDM relative à l'écho de géométrie,
- les scans 3D calibrés de gorge,
- les images opérateur,
- les rapports automatiques bilingues,
- les tables de délais orientées hardware.

### Note importante

Cette version est un démonstrateur et un modèle de construction de procédure.  
Les couches physiques haute fidélité sont définies dans la feuille de route :

- fonctions de Green,
- intégrales de Sommerfeld,
- approximation de Kirchhoff,
- approximation de Born,
- diffraction de bord / GTD.

Ces couches ne sont pas encore complètement implémentées comme solveur industriel final, mais la structure V3 est conçue pour les recevoir.
"""
)

st.divider()

st.header("7. Message for Shaun / Message pour Shaun")

st.info(
    """
The LSB941 Byte NDT Twin V3 demonstrator is now structured with restored PA trajectories, dynamic focal laws, calibrated beam fields, EDM response, 3D groove scans, operator reports and hardware-oriented delay exports for three PA configurations: 1D16, 1D32 and 2D8x8.

This version is ready for review as a GitHub/Streamlit demonstrator.
"""
)