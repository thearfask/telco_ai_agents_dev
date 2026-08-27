from __future__ import annotations

import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

from .models import (
    IncidentContext,
    IncidentObjective,
)


load_dotenv()


MODEL = os.getenv(
    "POC_MODEL",
    "gpt-5.4-mini",
)


def _parser_model():

    llm = ChatOpenAI(
        model=MODEL,
        temperature=0,
        reasoning_effort=None,
        max_completion_tokens=1200,
    )

    return llm.with_structured_output(
        IncidentContext,
        method="json_schema",
    )


def parse_incident(
    incident_text: str,
) -> IncidentContext:

    prompt = f"""
ROLE|INCIDENT_INTAKE

Convert the production incident ticket into structured scope.

RULES|
- Extract only information supported by the ticket.
- Never diagnose root cause.
- Never invent IDs.
- Never invent telemetry windows.
- Preserve explicit window IDs when provided.
- Missing fields remain null or empty.
- problem_statement must summarize the reported problem,
  not solve it.
- investigation_goal must describe what the investigation
  needs to establish.
- raw_text will be overwritten by the application.

INCIDENT|
{incident_text}
"""

    result = _parser_model().invoke(
        prompt
    )

    result.raw_text = incident_text

    return result


def build_objective(
    incident: IncidentContext,
) -> IncidentObjective:

    return IncidentObjective(
        incident_id=incident.incident_id,

        problem_statement=(
            incident.problem_statement
        ),

        investigation_goal=(
            incident.investigation_goal
        ),

        symptoms=incident.symptoms[:8],

        window_ids=incident.window_ids,

        component_ids=incident.component_ids,

        site_ids=incident.site_ids,

        region=incident.region,

        zone=incident.zone,

        start_time=incident.start_time,

        end_time=incident.end_time,
    )