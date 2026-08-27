from __future__ import annotations

import json

import streamlit as st

from graph import run_investigation


st.set_page_config(
    page_title=(
        "Telco AI RCA"
    ),
    page_icon="📡",
    layout="wide",
)


st.title(
    "Telco AI RCA"
)

st.caption(
    "Agentic telecom investigation with "
    "compact shared evidence state."
)


with st.sidebar:

    st.header(
        "Runtime"
    )

    api_key = st.text_input(
        "OpenAI API Key",
        type="password",
        placeholder="sk-...",
    )

    st.markdown(
        """
Credentials are used only for the current runtime
and are not written to traces.
"""
    )


default_incident = """INC-COMPLEX-001

Users report intermittent uplink performance degradation during WIN-000037.

The degradation is not continuous. Upload performance appears to drop
sharply for short periods and then recover.

Initial monitoring suggests:
- UL_BLER may increase during some degraded periods.
- UL_SNR may fluctuate.
- UL_MCS appears unstable.
- Uplink PRB utilization may increase.
- Buffer buildup may occur.

Determine whether the telemetry evidence is more consistent with:

1. poor uplink signal quality,
2. uplink radio reliability degradation,
3. uplink resource congestion,
4. buffering/traffic-pressure effects,
5. interaction between multiple mechanisms,
6. or another mechanism.

Do not assume correlation proves causation.

If available evidence cannot distinguish the mechanisms, identify the
evidence gap rather than forcing a conclusion.
"""


incident_text = st.text_area(
    "Incident",
    value=default_incident,
    height=390,
)


run = st.button(
    "Run Investigation",
    type="primary",
    use_container_width=True,
)


if run:

    if not api_key.strip():

        st.error(
            "Enter an OpenAI API key."
        )

        st.stop()

    if not incident_text.strip():

        st.error(
            "Enter an incident."
        )

        st.stop()

    try:

        with st.spinner(
            "Investigating..."
        ):

            result = (
                run_investigation(
                    incident_text=(
                        incident_text
                        .strip()
                    ),
                    api_key=(
                        api_key.strip()
                    ),
                )
            )

    except Exception as exc:

        st.exception(
            exc
        )

        st.stop()

    final_result = result.get(
        "final_result",
        {}
    )

    final_rca = final_result.get(
        "final_rca",
        {}
    )

    st.header(
        "RCA Result"
    )

    st.subheader(
        final_rca.get(
            "conclusion",
            "No conclusion produced.",
        )
    )

    col1, col2 = st.columns(
        2
    )

    col1.metric(
        "Confidence",
        final_rca.get(
            "confidence",
            "UNKNOWN",
        ),
    )

    col2.metric(
        "Rounds",
        final_result.get(
            "rounds_used",
            0,
        ),
    )

    st.write(
        final_rca.get(
            "reasoning_summary",
            "",
        )
    )

    st.header(
        "Confirmed Facts"
    )

    st.json(
        final_result.get(
            "confirmed_facts",
            [],
        )
    )

    st.header(
        "Hypothesis Verdicts"
    )

    st.json(
        final_result.get(
            "hypothesis_verdicts",
            [],
        )
    )

    st.header(
        "Evidence Gaps"
    )

    st.json(
        final_result.get(
            "evidence_gaps",
            [],
        )
    )

    with st.expander(
        "Open Questions"
    ):

        st.json(
            final_result.get(
                "open_questions",
                [],
            )
        )

    with st.expander(
        "Development Trace"
    ):

        st.json(
            result.get(
                "trace",
                [],
            )
        )

    trace_file = result.get(
        "trace_file"
    )

    if trace_file:

        st.caption(
            f"Trace saved to: "
            f"{trace_file}"
        )