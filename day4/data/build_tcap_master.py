"""
build_tcap_master.py
Reads all TCAP district-level files (2015–2025), normalizes columns,
extracts MSCS (system=792) and TN average, saves tcap_master.xlsx.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from openpyxl import load_workbook
from openpyxl.styles import PatternFill, Font, Alignment
from openpyxl.utils import get_column_letter

DATA_DIR = Path(__file__).parent
OUT = DATA_DIR / "tcap_master.xlsx"

TEAL   = "FF0F6E56"
LIGHT  = "FFE8F5F0"  # alternating row fill
WHITE  = "FFFFFFFF"

SUBJECTS_MAP = {
    "rla": "ELA", "ela": "ELA", "english language arts": "ELA",
    "math": "Math", "mathematics": "Math",
    "science": "Science",
    "social studies": "Social Studies",
}
KEEP_SUBJECTS = {"ELA", "Math", "Science", "Social Studies"}

MSCS_ID = 792
SPECIAL_MIN = 900  # systems >= 900 are special/state programs, exclude from TN avg

# ── file catalogue ────────────────────────────────────────────────────────────
FILES = {
    2015: ("data_2015_district_base.xlsx",       "xlsx"),
    # 2016 file is End-of-Course only (Algebra I, English I, grades 9-12) — no TCAP 3-8
    2017: ("data_2017_district_base.csv",         "csv"),
    2018: ("data_2018_district_base.csv",         "csv"),
    2019: ("district_assessment_file_suppressed.csv", "csv"),
    # 2020 → COVID waiver, no data
    2021: ("district_assessment_file_suppressed_upd422.csv", "csv"),
    2022: ("district_assessment_file_suppressed_upd32323.xlsx", "xlsx"),
    2023: ("district_assessment_file_suppressed_2023.xlsx", "xlsx"),
    2024: ("district_assessment_file_suppressed_2024.xlsx", "xlsx"),
    2025: ("district_assessment_file_suppressed_2025.xlsx", "xlsx"),
}


def load_raw(year, fname, ftype):
    path = DATA_DIR / fname
    if ftype == "csv":
        df = pd.read_csv(path, low_memory=False)
    else:
        df = pd.read_excel(path)
    # lowercase column names for easier matching
    df.columns = [c.strip() for c in df.columns]
    return df


def normalize(year, df):
    """Return DataFrame with columns: year, system, system_name, subject, grade, subgroup, pct"""
    cols = {c.lower(): c for c in df.columns}
    print(f"\n[{year}] raw columns: {list(df.columns)}")

    # ── system id ────────────────────────────────────────────────────────────
    if year == 2016:
        sys_col = "District"
        name_col = "District Name"
    else:
        sys_col  = next((cols[k] for k in ("system", "district number", "district_number") if k in cols), None)
        name_col = next((cols[k] for k in ("system_name", "district name", "district_name") if k in cols), None)

    # ── subgroup ─────────────────────────────────────────────────────────────
    if year == 2016:
        sub_col = "Subgroup"
    elif year >= 2022:
        sub_col = next((cols[k] for k in ("student_group", "student group") if k in cols), None)
    else:
        sub_col = next((cols[k] for k in ("subgroup",) if k in cols), None)

    # ── subject ──────────────────────────────────────────────────────────────
    subj_col = next((cols[k] for k in ("subject",) if k in cols), None)

    # ── grade ────────────────────────────────────────────────────────────────
    grade_col = next((cols[k] for k in ("grade", "grade_band", "grade band") if k in cols), None)

    # ── proficiency metric ────────────────────────────────────────────────────
    if year == 2015:
        pct_col = next((cols[k] for k in ("pct_prof_adv", "% proficient/advanced") if k in cols), None)
    elif year == 2016:
        pct_col = next((c for lc, c in cols.items() if "on track or mastered" in lc), None)
    elif year <= 2021:
        pct_col = next((cols[k] for k in ("pct_on_mastered",) if k in cols), None)
    else:  # 2022+
        pct_col = next((cols[k] for k in ("pct_met_exceeded",) if k in cols), None)

    print(f"  sys={sys_col}, name={name_col}, sub={sub_col}, subj={subj_col}, grade={grade_col}, pct={pct_col}")

    if not all([sys_col, sub_col, subj_col, pct_col]):
        print(f"  ⚠ SKIPPING {year} — missing required column(s)")
        return pd.DataFrame()

    n = len(df)
    subject_raw = df[subj_col].astype(str).str.strip()
    # test column (TNReady vs DLM/Alt etc.) — present in 2018+ files
    test_col = next((cols[k] for k in ("test",) if k in cols), None)
    out = pd.DataFrame({
        "year":        [year] * n,
        "system":      pd.to_numeric(df[sys_col], errors="coerce").values,
        "system_name": df[name_col].astype(str).str.strip().values if name_col else [""] * n,
        "subgroup":    df[sub_col].astype(str).str.strip().values,
        "subject_raw": subject_raw.values,
        "subject":     subject_raw.str.lower().map(SUBJECTS_MAP).values,
        "grade":       df[grade_col].astype(str).str.strip().values if grade_col else ["All Grades"] * n,
        "pct":         pd.to_numeric(df[pct_col], errors="coerce").values,
        "test":        df[test_col].astype(str).str.strip().values if test_col else ["TNReady"] * n,
    })

    return out


def filter_rows(df):
    """Keep All Students, All Grades, KEEP_SUBJECTS, TNReady only, valid systems."""
    if df.empty:
        return df
    # subgroup filter — various spellings
    df = df[df["subgroup"].str.lower().isin(["all students", "all", "all students (non-tested enrolled)"])]
    # subject filter
    df = df[df["subject"].isin(KEEP_SUBJECTS)]
    # grade filter — keep "All Grades" or aggregates
    df = df[df["grade"].str.lower().isin(["all grades", "all", "3-8", "grades 3-8", ""])]
    # valid system
    df = df[df["system"].notna() & (df["system"] > 0)]
    # test filter — keep main assessment only (TNReady 2018-2024, ACH 2025)
    # exclude DLM/Alt alternate assessments for students with significant disabilities
    if "test" in df.columns:
        main = df[df["test"].str.strip().str.lower().isin(["tnready", "ach"])]
        if not main.empty:
            df = main
    return df


def build_master():
    frames = []
    for year, (fname, ftype) in FILES.items():
        raw = load_raw(year, fname, ftype)
        norm = normalize(year, raw)
        filtered = filter_rows(norm)
        print(f"  → {len(filtered)} rows after filter")
        frames.append(filtered)

    master = pd.concat([f for f in frames if not f.empty], ignore_index=True)
    master = master[["year", "system", "system_name", "subject", "grade", "subgroup", "pct"]].copy()
    master = master.dropna(subset=["year"])
    master["year"] = master["year"].astype(int)
    return master


def mscs_trend(master):
    mscs = master[master["system"] == MSCS_ID].copy()
    pivot = mscs.pivot_table(index="year", columns="subject", values="pct", aggfunc="mean")
    pivot = pivot.reindex(columns=sorted(KEEP_SUBJECTS))
    pivot = pivot.reset_index()
    pivot.insert(1, "entity", "Memphis-Shelby County Schools")
    return pivot


def tn_avg_trend(master):
    regular = master[(master["system"] < SPECIAL_MIN) & (master["system"] != MSCS_ID)].copy()
    pivot = regular.groupby(["year", "subject"])["pct"].mean().unstack("subject")
    pivot = pivot.reindex(columns=sorted(KEEP_SUBJECTS))
    pivot = pivot.reset_index()
    pivot.insert(1, "entity", "TN State Average (all districts)")
    return pivot


def subject_sheet(master, subj):
    sub = master[master["subject"] == subj].copy()
    # MSCS row + TN avg side by side by year
    mscs_rows = sub[sub["system"] == MSCS_ID][["year", "pct"]].rename(columns={"pct": "MSCS %"})
    tn_rows   = sub[sub["system"] < SPECIAL_MIN][["year", "pct"]].groupby("year").mean().rename(columns={"pct": "TN Avg %"})
    merged = mscs_rows.set_index("year").join(tn_rows, how="outer").reset_index()
    merged["Gap (MSCS – TN)"] = merged["MSCS %"] - merged["TN Avg %"]
    merged.columns = ["Year", "MSCS %", "TN Avg %", "Gap (MSCS – TN)"]
    return merged.sort_values("Year")


def all_districts(master):
    # Latest year per district
    latest_year = master["year"].max()
    latest = master[master["year"] == latest_year].copy()
    pivot = latest.pivot_table(index=["system", "system_name"], columns="subject", values="pct", aggfunc="mean")
    pivot = pivot.reindex(columns=sorted(KEEP_SUBJECTS))
    pivot = pivot.reset_index()
    pivot.columns.name = None
    pivot = pivot[pivot["system"] < SPECIAL_MIN].copy()
    return pivot.sort_values("system")


def metadata():
    rows = []
    for year, (fname, _) in FILES.items():
        rows.append({"Year": year, "File": fname, "Notes": ""})
    df = pd.DataFrame(rows)
    df.loc[df["Year"] == 2015, "Notes"] = "Metric: pct_prof_adv; Subject 'RLA'→ELA; MSCS='Shelby County (New)'"
    df.loc[df["Year"] == 2016, "Notes"] = "Metric: % On Track or Mastered; different column names"
    df.loc[(df["Year"] >= 2017) & (df["Year"] <= 2021), "Notes"] = "Metric: pct_on_mastered (TNReady)"
    df.loc[df["Year"] >= 2022, "Notes"] = "Metric: pct_met_exceeded (new benchmark)"
    extra = pd.DataFrame([{"Year": 2020, "File": "N/A", "Notes": "COVID assessment waiver — no data"},
                           {"Year": 2016, "File": "data_2016_suppressed_district_base.xlsx", "Notes": "EOC only (Algebra I, English I) — grades 9-12, no TCAP 3-8; excluded"}])
    df = pd.concat([df, extra], ignore_index=True)
    df = df.sort_values("Year").reset_index(drop=True)
    return df


# ── Excel formatting ──────────────────────────────────────────────────────────

def style_sheet(ws):
    teal_fill  = PatternFill("solid", fgColor=TEAL)
    light_fill = PatternFill("solid", fgColor=LIGHT)
    white_fill = PatternFill("solid", fgColor=WHITE)
    bold_white = Font(bold=True, color="FFFFFFFF", size=11)

    # Header row
    for cell in ws[1]:
        cell.fill = teal_fill
        cell.font = bold_white
        cell.alignment = Alignment(horizontal="center", vertical="center")

    # Alternating rows
    for row_idx, row in enumerate(ws.iter_rows(min_row=2), start=2):
        fill = light_fill if row_idx % 2 == 0 else white_fill
        for cell in row:
            cell.fill = fill
            cell.alignment = Alignment(horizontal="center")

    # Auto-fit columns
    for col in ws.columns:
        max_len = max((len(str(c.value)) if c.value is not None else 0) for c in col)
        ws.column_dimensions[get_column_letter(col[0].column)].width = min(max_len + 4, 40)

    # Freeze header
    ws.freeze_panes = "A2"


def pct_format(ws, col_letters):
    for col in col_letters:
        for cell in ws[col]:
            if cell.row == 1:
                continue
            if cell.value is not None:
                try:
                    cell.number_format = "0.0"
                except Exception:
                    pass


def write_sheet(writer, df, sheet_name, pct_cols=None):
    df.to_excel(writer, sheet_name=sheet_name, index=False)
    ws = writer.sheets[sheet_name]
    style_sheet(ws)
    if pct_cols:
        letters = []
        for i, col in enumerate(df.columns, 1):
            if col in pct_cols:
                letters.append(get_column_letter(i))
        pct_format(ws, letters)


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("Building TCAP master from all years...")
    print("=" * 60)

    master = build_master()
    print(f"\nTotal rows in master: {len(master)}")
    print(master.groupby("year")["system"].nunique().rename("districts").to_string())

    # Check MSCS coverage
    mscs_check = master[master["system"] == MSCS_ID].groupby(["year", "subject"]).size().unstack(fill_value=0)
    print("\nMSCS (792) row counts by year × subject:")
    print(mscs_check.to_string())

    # Build sheets
    trend   = mscs_trend(master)
    tn_avg  = tn_avg_trend(master)
    combined_trend = pd.concat([trend, tn_avg], ignore_index=True).sort_values(["year", "entity"])

    ela_df  = subject_sheet(master, "ELA")
    math_df = subject_sheet(master, "Math")
    sci_df  = subject_sheet(master, "Science")
    ss_df   = subject_sheet(master, "Social Studies")
    all_df  = all_districts(master)
    meta_df = metadata()

    subj_pct = {"ELA", "Math", "Science", "Social Studies"}
    pct_flat = {"MSCS %", "TN Avg %", "Gap (MSCS – TN)"}

    with pd.ExcelWriter(OUT, engine="openpyxl") as writer:
        write_sheet(writer, combined_trend, "TREND",
                    pct_cols=subj_pct)
        write_sheet(writer, ela_df,  "ELA",           pct_cols=pct_flat)
        write_sheet(writer, math_df, "MATH",          pct_cols=pct_flat)
        write_sheet(writer, sci_df,  "SCIENCE",       pct_cols=pct_flat)
        write_sheet(writer, ss_df,   "SOCIAL_STUDIES",pct_cols=pct_flat)
        write_sheet(writer, all_df,  "ALL_DISTRICTS", pct_cols=subj_pct)
        write_sheet(writer, meta_df, "METADATA")

    print(f"\n✅ Saved: {OUT}")

    # Summary table
    print("\n── MSCS vs TN Average Summary ──────────────────────────────")
    print(f"{'Year':>5}  {'ELA MSCS':>9} {'ELA TN':>7}  {'Math MSCS':>10} {'Math TN':>8}  {'Sci MSCS':>9} {'Sci TN':>7}  {'SS MSCS':>8} {'SS TN':>7}")
    for yr in sorted(master["year"].unique()):
        def get(entity_mask, subj):
            v = master[entity_mask & (master["year"] == yr) & (master["subject"] == subj)]["pct"].mean()
            return f"{v:6.1f}" if pd.notna(v) else "   N/A"
        mscs_m = master["system"] == MSCS_ID
        tn_m   = (master["system"] < SPECIAL_MIN) & (master["system"] != MSCS_ID)
        print(f"{yr:>5}  {get(mscs_m,'ELA'):>9} {get(tn_m,'ELA'):>7}  "
              f"{get(mscs_m,'Math'):>10} {get(tn_m,'Math'):>8}  "
              f"{get(mscs_m,'Science'):>9} {get(tn_m,'Science'):>7}  "
              f"{get(mscs_m,'Social Studies'):>8} {get(tn_m,'Social Studies'):>7}")
    print(f"\n  * 2020 skipped — COVID assessment waiver")
    print(f"  * 2015–2021 metric: On Track/Mastered; 2022+ metric: Met/Exceeded (different benchmarks)")


if __name__ == "__main__":
    main()
