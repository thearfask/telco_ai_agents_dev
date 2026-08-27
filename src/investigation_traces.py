from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parents[1]
)

TRACE_DIR = (
    PROJECT_ROOT
    / "traces"
)


class InvestigationTrace:
    def __init__(
        self,
        incident_id: str | None = None,
    ):
        self.incident_id = (
            incident_id
            or "UNKNOWN"
        )

        self.started_at = (
            datetime.now()
            .astimezone()
            .isoformat()
        )

        self.stages: list[
            dict[str, Any]
        ] = []

    def set_incident_id(
        self,
        incident_id: str,
    ) -> None:
        if incident_id:
            self.incident_id = (
                incident_id
            )

    def add_stage(
        self,
        *,
        stage: str,
        agent: str,
        input_data: Any = None,
        output_data: Any = None,
        metadata: dict | None = None,
    ) -> None:

        self.stages.append(
            {
                "stage": stage,
                "agent": agent,
                "timestamp": (
                    datetime.now()
                    .astimezone()
                    .isoformat()
                ),
                "input": (
                    self._serialize(
                        input_data
                    )
                ),
                "output": (
                    self._serialize(
                        output_data
                    )
                ),
                "metadata": (
                    metadata or {}
                ),
            }
        )

    def save(self) -> Path:
        TRACE_DIR.mkdir(
            parents=True,
            exist_ok=True,
        )

        timestamp = (
            datetime.now()
            .strftime(
                "%Y%m%d_%H%M%S"
            )
        )

        safe_incident_id = (
            self.incident_id
            .replace("/", "_")
            .replace("\\", "_")
            .replace(" ", "_")
        )

        path = (
            TRACE_DIR
            / (
                f"{safe_incident_id}_"
                f"{timestamp}.json"
            )
        )

        payload = {
            "incident_id": (
                self.incident_id
            ),
            "started_at": (
                self.started_at
            ),
            "completed_at": (
                datetime.now()
                .astimezone()
                .isoformat()
            ),
            "stages": (
                self.stages
            ),
        }

        with path.open(
            "w",
            encoding="utf-8",
        ) as handle:
            json.dump(
                payload,
                handle,
                indent=2,
                default=str,
                ensure_ascii=False,
            )

        return path

    @staticmethod
    def _serialize(
        value: Any,
    ) -> Any:

        if value is None:
            return None

        if hasattr(
            value,
            "model_dump",
        ):
            return value.model_dump(
                exclude_none=True
            )

        if isinstance(
            value,
            (
                dict,
                list,
                str,
                int,
                float,
                bool,
            ),
        ):
            return value

        return str(value)