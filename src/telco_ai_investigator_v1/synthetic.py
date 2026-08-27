from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd
import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
CONFIG_DIR = PROJECT_ROOT / "config"

DB_FILE = PROJECT_ROOT / "telco.duckdb"
RULES_FILE = CONFIG_DIR / "alarm_rules.yaml"

TOPOLOGY_FILE = PROCESSED_DIR / "topology.parquet"
WINDOW_MAP_FILE = PROCESSED_DIR / "window_component_map.parquet"
ALARMS_FILE = PROCESSED_DIR / "alarms.parquet"


REGIONS = {
    "NORTH": {
        "sites": 10,
        "aggregation_router": "AGG-RTR-01",
        "upf": "CORE-UPF-01",
    },
    "CENTRAL": {
        "sites": 10,
        "aggregation_router": "AGG-RTR-02",
        "upf": "CORE-UPF-01",
    },
    "SOUTH": {
        "sites": 10,
        "aggregation_router": "AGG-RTR-03",
        "upf": "CORE-UPF-02",
    },
}


THRESHOLD_OPERATORS = {
    "greater_than": lambda s, t: s > t,
    "greater_than_or_equal": lambda s, t: s >= t,
    "less_than": lambda s, t: s < t,
    "less_than_or_equal": lambda s, t: s <= t,
}


def generate_topology() -> pd.DataFrame:
    """Generate the persistent fictional operator topology used by V1."""
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, Any]] = []
    site_number = 1

    for region, config in REGIONS.items():
        agg_router = config["aggregation_router"]
        upf = config["upf"]

        for _ in range(config["sites"]):
            site_id = f"SITE-{site_number:03d}"
            gnb_id = f"GNB-{site_number:03d}"

            for sector in ("A", "B", "C"):
                rows.append(
                    {
                        "source_component": f"CELL-{site_number:03d}-{sector}",
                        "target_component": gnb_id,
                        "relationship": "SERVED_BY",
                        "region": region,
                        "site_id": site_id,
                    }
                )

            rows.append(
                {
                    "source_component": gnb_id,
                    "target_component": agg_router,
                    "relationship": "ROUTED_THROUGH",
                    "region": region,
                    "site_id": site_id,
                }
            )
            site_number += 1

        rows.append(
            {
                "source_component": agg_router,
                "target_component": upf,
                "relationship": "CONNECTED_TO",
                "region": region,
                "site_id": None,
            }
        )

    rows.extend(
        [
            {
                "source_component": "CORE-UPF-01",
                "target_component": "5GC-CORE-01",
                "relationship": "CONNECTED_TO",
                "region": "CORE",
                "site_id": None,
            },
            {
                "source_component": "CORE-UPF-02",
                "target_component": "5GC-CORE-01",
                "relationship": "CONNECTED_TO",
                "region": "CORE",
                "site_id": None,
            },
        ]
    )

    topology = pd.DataFrame(rows)
    topology.to_parquet(TOPOLOGY_FILE, index=False)
    print(f"Topology generated: {len(topology):,} relationships")
    return topology


def generate_window_component_map(topology: pd.DataFrame) -> pd.DataFrame:
    """Map each TelecomTS window deterministically to one fictional cell."""
    if not DB_FILE.exists():
        raise FileNotFoundError(
            f"DuckDB file not found: {DB_FILE}. Run database.py first."
        )

    with duckdb.connect(str(DB_FILE), read_only=True) as con:
        windows = con.execute(
            """
            SELECT window_id, start_time, end_time
            FROM telemetry_windows
            ORDER BY window_id
            """
        ).df()

    cells = (
        topology[topology["relationship"] == "SERVED_BY"]
        [["source_component", "target_component", "region", "site_id"]]
        .rename(
            columns={
                "source_component": "component_id",
                "target_component": "gnb_id",
            }
        )
        .reset_index(drop=True)
    )

    if cells.empty:
        raise ValueError("Topology contains no SERVED_BY cell relationships.")

    assignments: list[dict[str, Any]] = []
    cell_count = len(cells)

    for index, window in windows.iterrows():
        cell = cells.iloc[index % cell_count]
        assignments.append(
            {
                "window_id": window["window_id"],
                "start_time": window["start_time"],
                "end_time": window["end_time"],
                "component_id": cell["component_id"],
                "gnb_id": cell["gnb_id"],
                "site_id": cell["site_id"],
                "region": cell["region"],
            }
        )

    mapping = pd.DataFrame(assignments)
    mapping.to_parquet(WINDOW_MAP_FILE, index=False)
    print(f"Window mappings generated: {len(mapping):,}")
    return mapping


def load_alarm_config() -> dict[str, Any]:
    """Load and lightly validate the machine-readable alarm configuration."""
    if not RULES_FILE.exists():
        raise FileNotFoundError(
            f"Alarm rules not found: {RULES_FILE}. "
            "Place alarm_rules.yaml under config/."
        )

    with RULES_FILE.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle)

    if not isinstance(config, dict):
        raise ValueError("alarm_rules.yaml must contain a YAML mapping.")
    if "rules" not in config or not isinstance(config["rules"], list):
        raise ValueError("alarm_rules.yaml must contain a rules list.")

    return config


def metric_multiplier(config: dict[str, Any], metric: str) -> float:
    """Return source-to-rule scale multiplier; defaults to 1.0."""
    metric_config = config.get("metrics", {}).get(metric, {})
    return float(metric_config.get("multiplier", 1.0))


def _required_samples(
    rule: dict[str, Any],
    sample_rate_hz: float,
) -> int:
    evaluation = rule["evaluation"]
    persistence_seconds = float(evaluation.get("persistence_seconds", 0))
    minimum_samples = int(
        evaluation.get(
            "minimum_samples",
            rule.get("minimum_samples", 1),
        )
    )

    persistence_samples = math.ceil(persistence_seconds * sample_rate_hz)
    return max(1, minimum_samples, persistence_samples)


def _first_persistent_run(mask: pd.Series, required_samples: int) -> tuple[int, int] | None:
    """Return the first contiguous True run long enough to satisfy persistence."""
    run_start: int | None = None
    run_length = 0

    for position, is_true in enumerate(mask.fillna(False).astype(bool).tolist()):
        if is_true:
            if run_start is None:
                run_start = position
            run_length += 1
            if run_length >= required_samples:
                # Continue until the run ends so last_seen reflects the observed run.
                end = position
                while end + 1 < len(mask) and bool(mask.iloc[end + 1]):
                    end += 1
                return run_start, end
        else:
            run_start = None
            run_length = 0

    return None


def _normalized_series(
    frame: pd.DataFrame,
    config: dict[str, Any],
    metric: str,
) -> pd.Series:
    if metric not in frame.columns:
        raise KeyError(metric)

    values = pd.to_numeric(frame[metric], errors="coerce")
    return values * metric_multiplier(config, metric)


def _evaluate_condition(
    frame: pd.DataFrame,
    config: dict[str, Any],
    condition: dict[str, Any],
) -> pd.Series:
    operator = condition.get("operator")
    if operator not in THRESHOLD_OPERATORS:
        raise ValueError(f"Unsupported threshold operator: {operator}")

    metric = condition["metric"]
    threshold = float(condition["threshold"])
    values = _normalized_series(frame, config, metric)
    return THRESHOLD_OPERATORS[operator](values, threshold)


def _threshold_mask(
    frame: pd.DataFrame,
    config: dict[str, Any],
    rule: dict[str, Any],
) -> pd.Series:
    evaluation = rule["evaluation"]
    return _evaluate_condition(frame, config, evaluation)


def _composite_mask(
    frame: pd.DataFrame,
    config: dict[str, Any],
    rule: dict[str, Any],
) -> pd.Series:
    evaluation = rule["evaluation"]
    logic = str(evaluation.get("logic", "AND")).upper()
    conditions = evaluation.get("conditions", [])

    if not conditions:
        raise ValueError(f"Composite rule {rule['rule_id']} has no conditions")

    masks: list[pd.Series] = []
    for condition in conditions:
        operator = condition.get("operator")
        if operator not in THRESHOLD_OPERATORS:
            # Baseline operators are deliberately deferred until we have
            # continuous per-cell history rather than isolated 12.8s windows.
            raise NotImplementedError(
                f"Composite condition operator {operator} requires baseline/history"
            )
        masks.append(_evaluate_condition(frame, config, condition))

    result = masks[0]
    for mask in masks[1:]:
        result = (result & mask) if logic == "AND" else (result | mask)
    return result


def _alarm_payload(
    *,
    alarm_number: int,
    config: dict[str, Any],
    rule: dict[str, Any],
    window: pd.DataFrame,
    mapping_row: pd.Series,
    run_start: int,
    run_end: int,
) -> dict[str, Any]:
    evaluation = rule["evaluation"]
    run = window.iloc[run_start : run_end + 1]
    evaluation_type = evaluation["type"]

    observed: dict[str, float | None] = {}
    thresholds: dict[str, Any] = {}

    if evaluation_type == "threshold":
        metric = evaluation["metric"]
        values = _normalized_series(run, config, metric)
        observed[metric] = None if values.dropna().empty else float(values.mean())
        thresholds[metric] = {
            "operator": evaluation["operator"],
            "threshold": evaluation["threshold"],
        }
    elif evaluation_type == "composite":
        for condition in evaluation["conditions"]:
            metric = condition["metric"]
            values = _normalized_series(run, config, metric)
            observed[metric] = None if values.dropna().empty else float(values.mean())
            thresholds[metric] = {
                key: value
                for key, value in condition.items()
                if key != "metric"
            }

    first_seen = pd.Timestamp(run.iloc[0]["event_timestamp"])
    last_seen = pd.Timestamp(run.iloc[-1]["event_timestamp"])

    metric_names = list(observed)
    primary_metric = metric_names[0] if len(metric_names) == 1 else None
    primary_value = observed.get(primary_metric) if primary_metric else None
    primary_threshold = None
    if primary_metric:
        primary_threshold = thresholds[primary_metric].get("threshold")

    return {
        "alarm_id": f"ALM-{alarm_number:07d}",
        "rule_id": rule["rule_id"],
        "rule_version": str(config.get("version", "unknown")),
        "window_id": mapping_row.name,
        "component_id": mapping_row["component_id"],
        "gnb_id": mapping_row["gnb_id"],
        "site_id": mapping_row["site_id"],
        "region": mapping_row["region"],
        "first_seen": first_seen,
        "last_seen": last_seen,
        "alarm_code": rule["alarm"]["code"],
        "alarm_name": rule["alarm"]["name"],
        "severity": rule["severity"],
        "source_system": rule["alarm"]["source_system"],
        "component_type": rule["alarm"]["component_type"],
        "evaluation_type": evaluation_type,
        "metric": primary_metric,
        "observed_value": primary_value,
        "threshold": primary_threshold,
        "observed_values_json": json.dumps(observed, sort_keys=True),
        "thresholds_json": json.dumps(thresholds, sort_keys=True),
        "sample_count": len(run),
        "persistence_seconds": evaluation.get("persistence_seconds"),
        "status": "OBSERVED",
        "category": rule.get("metadata", {}).get("category"),
        "threshold_type": rule.get("metadata", {}).get("threshold_type"),
    }


def generate_alarms() -> pd.DataFrame:
    """
    Generate V1 alarms from TelecomTS telemetry using alarm_rules.yaml.

    Supported now:
      - threshold rules
      - composite rules containing only absolute threshold conditions
      - persistence/minimum-sample enforcement
      - YAML-driven metric scaling

    Deliberately skipped for V1:
      - baseline_deviation rules
      - composite rules containing baseline operators
      - rules whose required persistence exceeds one TelecomTS window
      - full alarm clear/escalation lifecycle across windows

    Performance design:
      telemetry_measurements is scanned ONCE. Every eligible rule is then
      evaluated against each complete 128-sample window in memory.
    """
    if not WINDOW_MAP_FILE.exists():
        raise FileNotFoundError(
            f"Window mapping not found: {WINDOW_MAP_FILE}. Run Pass 1 first."
        )

    config = load_alarm_config()
    sample_rate_hz = float(config.get("defaults", {}).get("sample_rate_hz", 10))

    with duckdb.connect(str(DB_FILE), read_only=True) as con:
        available_columns = {
            row[0]
            for row in con.execute("DESCRIBE telemetry_measurements").fetchall()
        }

        enabled_rules = [rule for rule in config["rules"] if rule.get("enabled", True)]
        eligible_rules: list[tuple[dict[str, Any], int]] = []
        skipped_reasons: dict[str, str] = {}

        for rule in enabled_rules:
            rule_id = rule["rule_id"]
            evaluation = rule.get("evaluation", {})
            evaluation_type = evaluation.get("type")

            missing_metrics = [
                metric
                for metric in rule.get("metrics", [])
                if metric not in available_columns
            ]
            if missing_metrics:
                skipped_reasons[rule_id] = f"missing KPI(s): {missing_metrics}"
                continue

            if evaluation_type == "baseline_deviation":
                skipped_reasons[rule_id] = "baseline history not available in V1"
                continue

            required_samples = _required_samples(rule, sample_rate_hz)
            if required_samples > 128:
                skipped_reasons[rule_id] = (
                    f"needs {required_samples} samples; TelecomTS window has 128"
                )
                continue

            if evaluation_type == "composite":
                baseline_condition = any(
                    condition.get("operator") not in THRESHOLD_OPERATORS
                    for condition in evaluation.get("conditions", [])
                )
                if baseline_condition:
                    skipped_reasons[rule_id] = "composite requires baseline/history"
                    continue
            elif evaluation_type != "threshold":
                skipped_reasons[rule_id] = f"unsupported evaluation type: {evaluation_type}"
                continue

            eligible_rules.append((rule, required_samples))

        if not eligible_rules:
            raise RuntimeError("No alarm rules are eligible for the current V1 dataset.")

        print("Eligible V1 alarm rules:")
        for rule, required_samples in eligible_rules:
            print(f"  {rule['rule_id']:<35} persistence_samples={required_samples}")

        if skipped_reasons:
            print("\nDeferred rules:")
            for rule_id, reason in skipped_reasons.items():
                print(f"  {rule_id:<35} {reason}")

        mapping = pd.read_parquet(WINDOW_MAP_FILE).set_index("window_id")

        needed_metrics = sorted(
            {
                metric
                for rule, _ in eligible_rules
                for metric in rule.get("metrics", [])
            }
        )
        select_columns = ["window_id", "sample_index", "event_timestamp", *needed_metrics]
        sql_columns = ", ".join(f'"{column}"' for column in select_columns)

        cursor = con.execute(
            f"""
            SELECT {sql_columns}
            FROM telemetry_measurements
            ORDER BY window_id, sample_index
            """
        )

        alarms: list[dict[str, Any]] = []
        alarm_number = 1
        rule_alarm_counts: dict[str, int] = {}
        pending: dict[str, pd.DataFrame] = {}
        processed_windows = 0

        while True:
            batch = cursor.fetch_df_chunk(vectors_per_chunk=16)
            if batch.empty:
                break

            for window_id, group in batch.groupby("window_id", sort=False):
                if window_id in pending:
                    pending[window_id] = pd.concat(
                        [pending[window_id], group], ignore_index=True
                    )
                else:
                    pending[window_id] = group.copy()

                # TelecomTS currently has exactly 128 samples per window.
                if len(pending[window_id]) < 128:
                    continue

                window = (
                    pending.pop(window_id)
                    .sort_values("sample_index")
                    .reset_index(drop=True)
                )

                if len(window) != 128 or window_id not in mapping.index:
                    continue

                mapping_row = mapping.loc[window_id]

                for rule, required_samples in eligible_rules:
                    evaluation_type = rule["evaluation"]["type"]

                    try:
                        if evaluation_type == "threshold":
                            mask = _threshold_mask(window, config, rule)
                        else:
                            mask = _composite_mask(window, config, rule)
                    except (KeyError, ValueError, NotImplementedError) as exc:
                        # Config validation should normally prevent this; skip the
                        # individual rule/window rather than aborting the full run.
                        print(f"WARN {rule['rule_id']} on {window_id}: {exc}")
                        continue

                    run = _first_persistent_run(mask, required_samples)
                    if run is None:
                        continue

                    alarms.append(
                        _alarm_payload(
                            alarm_number=alarm_number,
                            config=config,
                            rule=rule,
                            window=window,
                            mapping_row=mapping_row,
                            run_start=run[0],
                            run_end=run[1],
                        )
                    )
                    alarm_number += 1
                    rule_id = rule["rule_id"]
                    rule_alarm_counts[rule_id] = rule_alarm_counts.get(rule_id, 0) + 1

                processed_windows += 1
                if processed_windows % 5000 == 0:
                    print(
                        f"Processed {processed_windows:,} / {len(mapping):,} windows | "
                        f"alarms={len(alarms):,}"
                    )

        if pending:
            print(f"WARN: {len(pending)} incomplete windows remained after scan")

    columns = [
        "alarm_id",
        "rule_id",
        "rule_version",
        "window_id",
        "component_id",
        "gnb_id",
        "site_id",
        "region",
        "first_seen",
        "last_seen",
        "alarm_code",
        "alarm_name",
        "severity",
        "source_system",
        "component_type",
        "evaluation_type",
        "metric",
        "observed_value",
        "threshold",
        "observed_values_json",
        "thresholds_json",
        "sample_count",
        "persistence_seconds",
        "status",
        "category",
        "threshold_type",
    ]

    alarm_df = pd.DataFrame(alarms, columns=columns)
    alarm_df.to_parquet(ALARMS_FILE, index=False)

    print("\nAlarm generation complete.")
    print(f"Processed windows: {processed_windows:,}")
    print(f"Generated alarms:  {len(alarm_df):,}")
    print(f"Output: {ALARMS_FILE}")

    if rule_alarm_counts:
        print("\nAlarms by rule:")
        for rule_id, count in sorted(rule_alarm_counts.items(), key=lambda item: -item[1]):
            print(f"  {rule_id:<35} {count:>7,}")

    return alarm_df

def main() -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    print("Synthetic data generation\n")

    if not TOPOLOGY_FILE.exists():
        topology = generate_topology()
    else:
        topology = pd.read_parquet(TOPOLOGY_FILE)
        print(f"Using existing topology: {len(topology):,} relationships")

    if not WINDOW_MAP_FILE.exists():
        generate_window_component_map(topology)
    else:
        mapping_count = len(pd.read_parquet(WINDOW_MAP_FILE, columns=["window_id"]))
        print(f"Using existing window mappings: {mapping_count:,}")

    generate_alarms()


if __name__ == "__main__":
    main()