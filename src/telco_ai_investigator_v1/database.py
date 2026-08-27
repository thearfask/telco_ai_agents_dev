from pathlib import Path

import duckdb


PROJECT_ROOT = Path(__file__).resolve().parents[2]

DB_PATH = PROJECT_ROOT / "telco.duckdb"
WINDOWS_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "telemetry_windows.parquet"
)

TELEMETRY_DIR = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "telemetry"
)


def create_database() -> None:
    print(f"Project root : {PROJECT_ROOT}")
    print(f"Database path: {DB_PATH}")
    print(f"Parquet path : {WINDOWS_FILE}")

    if not WINDOWS_FILE.exists():
        raise FileNotFoundError(
            f"Parquet file not found: {WINDOWS_FILE}"
        )

    con = duckdb.connect(str(DB_PATH))

    try:
        # Create a persistent DuckDB table for now.
        con.execute("DROP VIEW IF EXISTS telemetry_windows")
        con.execute("DROP TABLE IF EXISTS telemetry_windows")

        parquet_path = str(WINDOWS_FILE).replace("'", "''")

        con.execute(
            f"""
            CREATE VIEW telemetry_windows AS
            SELECT *
            FROM read_parquet('{parquet_path}')
            """
        )
        
        con.execute(
            "DROP VIEW IF EXISTS telemetry_measurements"
        )

        telemetry_glob = str(
            TELEMETRY_DIR / "*.parquet"
        ).replace("'", "''")

        con.execute(
            f"""
            CREATE VIEW telemetry_measurements AS
            SELECT *
            FROM read_parquet('{telemetry_glob}')
            """
        )
        
        con.execute("DROP TABLE IF EXISTS telemetry_summary")

        con.execute(
            """
            CREATE TABLE telemetry_summary AS
            SELECT
                window_id,

                MIN(event_timestamp) AS start_time,
                MAX(event_timestamp) AS end_time,
                COUNT(*) AS sample_count,

                ROUND(AVG(RSRP), 4) AS avg_rsrp,
                MIN(RSRP) AS min_rsrp,
                MAX(RSRP) AS max_rsrp,

                ROUND(AVG(DL_BLER), 4) AS avg_dl_bler,
                MAX(DL_BLER) AS max_dl_bler,

                ROUND(AVG(UL_BLER), 4) AS avg_ul_bler,
                MAX(UL_BLER) AS max_ul_bler,

                ROUND(AVG(UL_SNR), 4) AS avg_ul_snr,
                MIN(UL_SNR) AS min_ul_snr,

                ROUND(AVG(DL_MCS), 4) AS avg_dl_mcs,
                ROUND(AVG(UL_MCS), 4) AS avg_ul_mcs,

                ROUND(AVG(PRB_Utilization_DL), 4)
                    AS avg_prb_utilization_dl,

                ROUND(AVG(PRB_Utilization_UL), 4)
                    AS avg_prb_utilization_ul,

                ROUND(AVG(TX_Bytes), 4) AS avg_tx_bytes,
                ROUND(AVG(RX_Bytes), 4) AS avg_rx_bytes

            FROM telemetry_measurements
            GROUP BY window_id
            """
        )

        print("\nAvailable objects:")

        for obj in con.execute("SHOW TABLES").fetchall():
            print(f"  - {obj[0]}")

        window_count = con.execute(
            "SELECT COUNT(*) FROM telemetry_windows"
        ).fetchone()[0]

        measurement_count = con.execute(
            "SELECT COUNT(*) FROM telemetry_measurements"
        ).fetchone()[0]

        summary_count = con.execute(
            "SELECT COUNT(*) FROM telemetry_summary"
        ).fetchone()[0]

        print(f"telemetry_summary:      {summary_count:,}")
        print(f"\ntelemetry_windows:      {window_count:,}")
        print(f"telemetry_measurements: {measurement_count:,}")
    finally:
        con.close()

    print(f"\nDatabase saved to: {DB_PATH}")


if __name__ == "__main__":
    create_database()