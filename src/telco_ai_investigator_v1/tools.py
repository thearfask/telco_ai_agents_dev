from pathlib import Path
from typing import Any

import duckdb


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_FILE = PROJECT_ROOT / "telco.duckdb"

PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
ALARMS_FILE = PROCESSED_DIR / "alarms.parquet"
TOPOLOGY_FILE = PROCESSED_DIR / "topology.parquet"
WINDOW_MAP_FILE = PROCESSED_DIR / "window_component_map.parquet"


def _connect() -> duckdb.DuckDBPyConnection:
    """
    Open the local analytical database in read-only mode.
    """
    return duckdb.connect(str(DB_FILE), read_only=True)


def _rows_to_dicts(
    con: duckdb.DuckDBPyConnection,
) -> list[dict[str, Any]]:
    """
    Convert the latest DuckDB query result into dictionaries.
    """
    columns = [column[0] for column in con.description]
    rows = con.fetchall()

    return [
        dict(zip(columns, row))
        for row in rows
    ]


def get_window_health(
    window_id: str,
) -> dict[str, Any] | None:
    """
    Return the compact telemetry summary and component context
    for one TelecomTS window.

    This should normally be the investigator's first telemetry call.
    """

    con = _connect()

    try:
        result = con.execute(
            f"""
            SELECT
                s.*,
                m.component_id,
                m.gnb_id,
                m.site_id,
                m.region

            FROM telemetry_summary s

            LEFT JOIN read_parquet(
                '{WINDOW_MAP_FILE}'
            ) m
                ON s.window_id = m.window_id

            WHERE s.window_id = ?
            """,
            [window_id],
        )

        rows = _rows_to_dicts(result)

        if not rows:
            return None

        return rows[0]

    finally:
        con.close()


def get_telemetry_detail(
    window_id: str,
    metrics: list[str] | None = None,
    limit: int = 128,
) -> list[dict[str, Any]]:

    allowed_metrics = {
        "RSRP",
        "DL_BLER",
        "DL_MCS",
        "UL_BLER",
        "UL_MCS",
        "UL_NPRB",
        "UL_SNR",
        "TX_Bytes",
        "RX_Bytes",
        "Estimated_UL_Buffer",
        "PRBs_DL_Current",
        "PRBs_UL_Current",
        "PRB_Utilization_DL",
        "PRB_Utilization_UL",
        "UL_Protocol",
        "UL_NumberOfPackets",
        "DL_Protocol",
        "DL_NumberOfPackets",
    }

    metric_aliases = {

        "rsrp":
            "RSRP",

        "dl_bler":
            "DL_BLER",

        "dl_mcs":
            "DL_MCS",

        "ul_bler":
            "UL_BLER",

        "ul_mcs":
            "UL_MCS",

        "ul_nprb":
            "UL_NPRB",

        "snr":
            "UL_SNR",

        "ul_snr":
            "UL_SNR",

        "tx_bytes":
            "TX_Bytes",

        "rx_bytes":
            "RX_Bytes",

        "estimated_ul_buffer":
            "Estimated_UL_Buffer",

        "prbs_dl_current":
            "PRBs_DL_Current",

        "prbs_ul_current":
            "PRBs_UL_Current",

        "prb_utilization_dl":
            "PRB_Utilization_DL",

        "prb_utilization_ul":
            "PRB_Utilization_UL",

        "ul_protocol":
            "UL_Protocol",

        "dl_protocol":
            "DL_Protocol",

        "ul_numberofpackets":
            "UL_NumberOfPackets",

        "dl_numberofpackets":
            "DL_NumberOfPackets",
    }

    if metrics is None:

        metrics = [
            "RSRP",
            "DL_BLER",
            "DL_MCS",
            "UL_BLER",
            "UL_MCS",
            "UL_SNR",
            "TX_Bytes",
            "RX_Bytes",
        ]

    # --------------------------------------------------
    # Normalize model-friendly aliases
    # BEFORE validation.
    # --------------------------------------------------

    metrics = [

        metric_aliases.get(
            metric.strip().lower(),
            metric,
        )

        for metric
        in metrics
    ]

    invalid_metrics = (
        set(metrics)
        - allowed_metrics
    )

    if invalid_metrics:

        raise ValueError(
            "Unsupported metrics: "
            f"{sorted(invalid_metrics)}"
        )

    # --------------------------------------------------
    # Bound detail access.
    # --------------------------------------------------

    limit = max(
        1,
        min(
            int(limit),
            128,
        ),
    )

    metric_sql = ", ".join(
        metrics
    )

    con = _connect()

    try:

        result = con.execute(
            f"""
            SELECT
                window_id,
                sample_index,
                event_timestamp,
                {metric_sql}

            FROM telemetry_measurements

            WHERE window_id = ?

            ORDER BY sample_index

            LIMIT ?
            """,
            [
                window_id,
                limit,
            ],
        )

        return _rows_to_dicts(
            result
        )

    finally:
        con.close()

def get_alarms(
    window_id: str,
) -> list[dict[str, Any]]:
    """
    Return alarms associated with a telemetry window.
    """

    con = _connect()

    try:
        result = con.execute(
            f"""
            SELECT *
            FROM read_parquet('{ALARMS_FILE}')
            WHERE window_id = ?
            ORDER BY first_seen
            """,
            [window_id],
        )

        return _rows_to_dicts(result)

    finally:
        con.close()


def get_topology(
    window_id: str,
) -> dict[str, Any] | None:
    """
    Resolve a window to its component and return the component's
    dependency path through the fictional operator network.
    """

    con = _connect()

    try:
        mapping_result = con.execute(
            f"""
            SELECT
                window_id,
                component_id,
                gnb_id,
                site_id,
                region

            FROM read_parquet('{WINDOW_MAP_FILE}')

            WHERE window_id = ?
            """,
            [window_id],
        )

        mapping_rows = _rows_to_dicts(mapping_result)

        if not mapping_rows:
            return None

        mapping = mapping_rows[0]

        component_id = mapping["component_id"]

        topology_result = con.execute(
            f"""
            WITH RECURSIVE dependency_path AS (

                SELECT
                    source_component,
                    target_component,
                    relationship,
                    1 AS depth

                FROM read_parquet('{TOPOLOGY_FILE}')

                WHERE source_component = ?

                UNION ALL

                SELECT
                    t.source_component,
                    t.target_component,
                    t.relationship,
                    p.depth + 1

                FROM read_parquet('{TOPOLOGY_FILE}') t

                JOIN dependency_path p
                    ON t.source_component = p.target_component

                WHERE p.depth < 10
            )

            SELECT *
            FROM dependency_path
            ORDER BY depth
            """,
            [component_id],
        )

        dependencies = _rows_to_dicts(topology_result)

        return {
            "window_id": window_id,
            "component_id": component_id,
            "gnb_id": mapping["gnb_id"],
            "site_id": mapping["site_id"],
            "region": mapping["region"],
            "dependencies": dependencies,
        }

    finally:
        con.close()


def main() -> None:
    """
    Temporary manual smoke test.
    """

    window_id = "WIN-001287"

    print("\nWINDOW HEALTH")
    print(get_window_health(window_id))

    print("\nALARMS")
    print(get_alarms(window_id))

    print("\nTOPOLOGY")
    print(get_topology(window_id))

    print("\nTELEMETRY DETAIL")

    rows = get_telemetry_detail(
        window_id,
        metrics=[
            "RSRP",
            "DL_BLER",
            "DL_MCS",
            "UL_BLER",
            "UL_SNR",
        ],
        limit=10,
    )

    for row in rows:
        print(row)


if __name__ == "__main__":
    main()