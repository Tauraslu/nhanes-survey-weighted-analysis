
import os
import numpy as np
import pandas as pd
import pymysql
from sqlalchemy import create_engine, text

# =========================
# Config
# =========================
DB_URI = "mysql+pymysql://root:password@localhost:3306/etf_df"  
DATA_DIR = "/Users/tauras/Downloads" 
OUT_DIR = os.path.join(os.path.dirname(__file__), "output")

FILES = {
    "demo_g": "DEMO_G.xpt",
    "bpx_g":  "BPX_G.xpt",
    "bmx_g":  "BMX_G.xpt",
    "smq_g":  "SMQ_G.xpt",
    "diq_g":  "DIQ_G.xpt",
    "bpq_g":  "BPQ_G.xpt",
}

# =========================
# Helpers
# =========================
def read_xpt_safe(path: str) -> pd.DataFrame:
    if not os.path.exists(path):
        raise FileNotFoundError(f"File not found: {path}")
    df = pd.read_sas(path, format="xport", encoding="utf-8")
    # Normalize column names (MySQL-friendly)
    df.columns = [c.upper() for c in df.columns]
    return df

def coerce_numeric(df: pd.DataFrame) -> pd.DataFrame:
    # SAS XPT may load as object; try to coerce numeric-like columns
    for c in df.columns:
        if df[c].dtype == "object":
            df[c] = pd.to_numeric(df[c], errors="ignore")
    return df

def upload_table(df: pd.DataFrame, table_name: str, engine, if_exists: str = "replace") -> None:
    df = coerce_numeric(df)
    df.to_sql(table_name, engine, if_exists=if_exists, index=False, chunksize=2000, method="multi")
    print(f"Uploaded: {table_name} ({len(df):,} rows, {df.shape[1]} cols)")

# =========================
# Main
# =========================
def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    engine = create_engine(DB_URI, pool_pre_ping=True)

    # 1) Load XPT and upload to MySQL
    for table, fname in FILES.items():
        fpath = os.path.join(DATA_DIR, fname)
        df = read_xpt_safe(fpath)
        upload_table(df, table, engine, if_exists="replace")

    # 2) Build analysis_dataset in MySQL
    #    - Use mean of available SBP/DBP readings (handles missing)
    #    - Keep survey design vars (SDMVPSU/SDMVSTRA/WTMEC2YR)
    #    - Add smoker/diabetes/bp_med flags
    build_sql = """
    DROP TABLE IF EXISTS analysis_dataset;

    CREATE TABLE analysis_dataset AS
    SELECT
        d.SEQN,
        d.RIDAGEYR AS age,
        d.RIAGENDR AS sex,
        d.SDMVPSU,
        d.SDMVSTRA,
        d.WTMEC2YR,

        m.BMXBMI AS bmi,

        -- mean SBP across non-missing readings
        (
          IF(b.BPXSY1 IS NULL, 0, b.BPXSY1) +
          IF(b.BPXSY2 IS NULL, 0, b.BPXSY2) +
          IF(b.BPXSY3 IS NULL, 0, b.BPXSY3) +
          IF(b.BPXSY4 IS NULL, 0, b.BPXSY4)
        ) /
        NULLIF(
          (b.BPXSY1 IS NOT NULL) +
          (b.BPXSY2 IS NOT NULL) +
          (b.BPXSY3 IS NOT NULL) +
          (b.BPXSY4 IS NOT NULL)
        , 0) AS sbp_mean,

        (
          IF(b.BPXDI1 IS NULL, 0, b.BPXDI1) +
          IF(b.BPXDI2 IS NULL, 0, b.BPXDI2) +
          IF(b.BPXDI3 IS NULL, 0, b.BPXDI3) +
          IF(b.BPXDI4 IS NULL, 0, b.BPXDI4)
        ) /
        NULLIF(
          (b.BPXDI1 IS NOT NULL) +
          (b.BPXDI2 IS NOT NULL) +
          (b.BPXDI3 IS NOT NULL) +
          (b.BPXDI4 IS NOT NULL)
        , 0) AS dbp_mean,

        (
          (b.BPXSY1 IS NOT NULL) +
          (b.BPXSY2 IS NOT NULL) +
          (b.BPXSY3 IS NOT NULL) +
          (b.BPXSY4 IS NOT NULL)
        ) AS n_sbp,

        -- Smoking: SMQ020==1 ever smoked 100 cigarettes
        CASE WHEN smq.SMQ020 = 1 THEN 1
             WHEN smq.SMQ020 IN (2, 7, 9) THEN 0
             ELSE NULL END AS smoker,

        -- Diabetes: DIQ010==1 told have diabetes
        CASE WHEN diq.DIQ010 = 1 THEN 1
             WHEN diq.DIQ010 IN (2, 3) THEN 0
             ELSE NULL END AS diabetes,

        -- BP medication: BPQ050A==1 now taking prescribed medicine for HBP
        CASE WHEN bpq.BPQ050A = 1 THEN 1
             WHEN bpq.BPQ050A IN (2, 7, 9) THEN 0
             ELSE NULL END AS bp_med

    FROM demo_g d
    JOIN bpx_g b ON d.SEQN = b.SEQN
    JOIN bmx_g m ON d.SEQN = m.SEQN
    LEFT JOIN smq_g smq ON d.SEQN = smq.SEQN
    LEFT JOIN diq_g diq ON d.SEQN = diq.SEQN
    LEFT JOIN bpq_g bpq ON d.SEQN = bpq.SEQN
    WHERE d.RIDAGEYR >= 20;
    """

    with engine.begin() as conn:
        for stmt in build_sql.strip().split(";"):
            if stmt.strip():
                conn.execute(text(stmt))
    print("Created table: analysis_dataset")

    # 3) QC summary (duplicates, missingness, range checks)
    qc_sql = """
    SELECT 'n_rows' AS metric, COUNT(*) AS value FROM analysis_dataset
    UNION ALL
    SELECT 'dup_seqn', COUNT(*) - COUNT(DISTINCT SEQN) FROM analysis_dataset
    UNION ALL
    SELECT 'missing_bmi', SUM(bmi IS NULL) FROM analysis_dataset
    UNION ALL
    SELECT 'missing_sbp_mean', SUM(sbp_mean IS NULL) FROM analysis_dataset
    UNION ALL
    SELECT 'missing_weights', SUM(WTMEC2YR IS NULL) FROM analysis_dataset
    UNION ALL
    SELECT 'bmi_out_of_range', SUM(bmi < 10 OR bmi > 80) FROM analysis_dataset
    UNION ALL
    SELECT 'sbp_out_of_range', SUM(sbp_mean < 70 OR sbp_mean > 250) FROM analysis_dataset;
    """

    qc_df = pd.read_sql(qc_sql, engine)
    qc_path = os.path.join(OUT_DIR, "qc_summary.csv")
    qc_df.to_csv(qc_path, index=False)
    print(f"Saved: {qc_path}")

    # 4) Export analysis dataset for R
    extract_df = pd.read_sql("SELECT * FROM analysis_dataset", engine)
    out_csv = os.path.join(OUT_DIR, "analysis_dataset.csv")
    extract_df.to_csv(out_csv, index=False)
    print(f"Saved: {out_csv}")

    print("\nDone. Next step: use R to run survey-weighted models on output/analysis_dataset.csv")

if __name__ == "__main__":
    main()