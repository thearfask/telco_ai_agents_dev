from pathlib import Path
from datetime import datetime, timezone, timedelta
import json
import random
import pandas as pd
from datasets import load_dataset
import numpy as np

DATASET_NAME = "Govisha/TelecomTS"

PROJECT_ROOT = Path(__file__).resolve().parents[2]

RAW_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

RAW_FILE = RAW_DIR / "telecomts.parquet"
WINDOWS_FILE = PROCESSED_DIR / "telemetry_windows.parquet"
GROUND_TRUTH_FILE = PROCESSED_DIR / "telecomts_ground_truth.parquet"


def transform_telemetry_measurements(
    batch_size: int = 1000,
) -> None:
    """
    Transform nested TelecomTS KPI arrays into wide sample-level rows.

    32,000 windows × 128 samples ~= 4.1M rows.

    Output:
        data/processed/telemetry/
            part_000.parquet
            part_001.parquet
            ...
    """

    output_dir = PROCESSED_DIR / "telemetry"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Clean previous generated parts so reruns are deterministic.
    for old_file in output_dir.glob("part_*.parquet"):
        old_file.unlink()

    print("Reading raw TelecomTS...")

    df = pd.read_parquet(
        RAW_FILE,
        columns=[
            "start_time",
            "end_time",
            "sampling_rate",
            "KPIs",
        ],
    )

    total_windows = len(df)

    print(f"Windows: {total_windows:,}")
    print(f"Batch size: {batch_size:,}")

    part_number = 0
    total_measurements = 0

    for batch_start in range(0, total_windows, batch_size):

        batch_end = min(
            batch_start + batch_size,
            total_windows,
        )

        records = []

        for row_index in range(batch_start, batch_end):

            row = df.iloc[row_index]

            window_id = f"WIN-{row_index:06d}"

            start_time = pd.Timestamp(row["start_time"])
            end_time = pd.Timestamp(row["end_time"])

            kpis = row["KPIs"]

            # Determine sample count from KPI arrays.
            sample_count = len(kpis["RSRP"])

            if sample_count == 0:
                continue

            # TelecomTS sample timestamps span start_time → end_time.
            if sample_count == 1:
                timestamps = [start_time]
            else:
                timestamps = pd.date_range(
                    start=start_time,
                    end=end_time,
                    periods=sample_count,
                )

            # Build one row per sample.
            for sample_index in range(sample_count):

                record = {
                    "window_id": window_id,
                    "sample_index": sample_index,
                    "event_timestamp": timestamps[sample_index],
                }

                for kpi_name, values in kpis.items():

                    if values is None:
                        record[kpi_name] = None
                        continue

                    try:
                        record[kpi_name] = values[sample_index]
                    except (IndexError, TypeError):
                        record[kpi_name] = None

                records.append(record)

        batch_df = pd.DataFrame(records)

        if batch_df.empty:
            continue

        batch_df = batch_df.sort_values(
            ["window_id", "event_timestamp"]
        )

        output_file = (
            output_dir
            / f"part_{part_number:03d}.parquet"
        )

        batch_df.to_parquet(
            output_file,
            index=False,
            engine="pyarrow",
            compression="snappy",
        )

        total_measurements += len(batch_df)

        print(
            f"Part {part_number:03d}: "
            f"windows {batch_start:,}-{batch_end - 1:,} | "
            f"{len(batch_df):,} rows"
        )

        part_number += 1

    print()
    print("Telemetry transformation complete.")
    print(f"Files: {part_number:,}")
    print(f"Rows:  {total_measurements:,}")
    print(f"Path:  {output_dir}")


def extract_telecomts() -> None:
    """Download TelecomTS and persist the original dataset as Parquet."""

    RAW_DIR.mkdir(parents=True, exist_ok=True)

    print("Downloading TelecomTS...")

    dataset = load_dataset(DATASET_NAME, split="train")

    print(f"Rows received: {len(dataset):,}")

    dataset.to_parquet(str(RAW_FILE))

    print(f"Raw dataset saved: {RAW_FILE}")


def transform_telecomts() -> None:
    """
    Create query-friendly window metadata and isolated evaluation ground truth.

    We intentionally do NOT explode the KPI arrays yet.
    """

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    print("Reading raw TelecomTS...")

    df = pd.read_parquet(RAW_FILE)

    print(f"Rows read: {len(df):,}")

    # -------------------------
    # Observable window data
    # -------------------------

    windows = pd.DataFrame(
        {
            "window_id": [f"WIN-{i:06d}" for i in range(len(df))],
            "start_time": pd.to_datetime(df["start_time"]),
            "end_time": pd.to_datetime(df["end_time"]),
            "sampling_rate": df["sampling_rate"],
            "zone": df["labels"].apply(lambda x: x.get("zone")),
            "application": df["labels"].apply(lambda x: x.get("application")),
            "mobility": df["labels"].apply(lambda x: x.get("mobility")),
            "congestion": df["labels"].apply(lambda x: x.get("congestion")),
            "anomaly_present": df["labels"].apply(
                lambda x: x.get("anomaly_present")
            ),
        }
    )

    windows.to_parquet(WINDOWS_FILE, index=False)

    # -------------------------
    # Hidden evaluation truth
    # -------------------------

    ground_truth = pd.DataFrame(
        {
            "window_id": windows["window_id"],
            "anomaly_exists": df["anomalies"].apply(
                lambda x: x.get("exists")
            ),
            "anomaly_type": df["anomalies"].apply(
                lambda x: x.get("type")
            ),
            "anomaly_start": df["anomalies"].apply(
                lambda x: (
                    x.get("anomaly_duration", {}).get("start")
                    if x.get("anomaly_duration")
                    else None
                )
            ),
            "anomaly_end": df["anomalies"].apply(
                lambda x: (
                    x.get("anomaly_duration", {}).get("end")
                    if x.get("anomaly_duration")
                    else None
                )
            ),
            "affected_kpis": df["anomalies"].apply(
                lambda x: x.get("affected_kpis")
            ),
            "troubleshooting_ticket": df["anomalies"].apply(
                lambda x: x.get("troubleshooting_tickets")
            ),
        }
    )

    ground_truth.to_parquet(GROUND_TRUTH_FILE, index=False)

    print(f"Windows saved:      {WINDOWS_FILE}")
    print(f"Ground truth saved: {GROUND_TRUTH_FILE}")


def main() -> None:
    print(
        "ETL started:",
        datetime.now(timezone.utc).isoformat(),
    )

    # We already extracted TelecomTS.
    # Don't download it again every run.
    if not RAW_FILE.exists():
        extract_telecomts()

    transform_telecomts()

    transform_telemetry_measurements(
        batch_size=1000,
    )

    print("ETL complete.")


if __name__ == "__main__":
    main()