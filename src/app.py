from __future__ import annotations

import streamlit as st

from graph import (
    run_investigation,
)


# ============================================================
# PAGE
# ============================================================


st.set_page_config(
    page_title="Telco AI Investigator",
    page_icon="📡",
    layout="wide",
)


st.markdown(
    """
<style>

.block-container {
    max-width: 1400px;
    padding-top: 2rem;
    padding-bottom: 3rem;
}

.hero {
    font-size: 2.2rem;
    font-weight: 750;
    margin-bottom: .1rem;
}

.subtitle {
    opacity: .62;
    margin-bottom: 1.5rem;
}

.round-card {
    border: 1px solid rgba(128,128,128,.22);
    border-radius: 14px;
    padding: 16px;
    height: 100%;
}

.label {
    margin-top: 14px;
    margin-bottom: 4px;
    opacity: .55;
    font-size: .72rem;
    text-transform: uppercase;
    letter-spacing: .06rem;
}

.tool {
    display: inline-block;
    padding: 3px 9px;
    margin: 2px;
    border-radius: 999px;
    background: rgba(80,120,255,.12);
    font-size: .78rem;
    font-weight: 600;
}

.fact {
    padding: 9px 0;
    border-bottom: 1px solid rgba(128,128,128,.12);
}

</style>
""",
    unsafe_allow_html=True,
)


# ============================================================
# CREDENTIAL GATE
# ============================================================


def credential_gate():
    st.markdown(
        '<div class="hero">📡 Telco AI Investigator</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        """
<div class="subtitle">
Agentic network incident investigation
</div>
""",
        unsafe_allow_html=True,
    )

    st.subheader(
        "Start Investigator"
    )

    st.write(
        "Enter your OpenAI API key for this runtime session."
    )

    api_key = st.text_input(
        "OpenAI API Key",
        type="password",
        placeholder="sk-...",
    )

    st.caption(
        "The key is kept only in the current Streamlit session "
        "and is not included in investigation state or downloads."
    )

    if st.button(
        "Start",
        type="primary",
    ):
        if not api_key.strip():
            st.error(
                "Enter an OpenAI API key."
            )
            return

        st.session_state[
            "openai_api_key"
        ] = api_key.strip()

        st.session_state[
            "authenticated"
        ] = True

        st.rerun()


if not st.session_state.get(
    "authenticated"
):
    credential_gate()
    st.stop()


# ============================================================
# HEADER
# ============================================================


header_left, header_right = st.columns(
    [5, 1]
)


with header_left:
    st.markdown(
        '<div class="hero">📡 Telco AI Investigator</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        """
<div class="subtitle">
LangGraph · RCA supervisor · specialist agents · autonomous tools
</div>
""",
        unsafe_allow_html=True,
    )


with header_right:
    if st.button(
        "End Session"
    ):
        st.session_state.clear()
        st.rerun()


# ============================================================
# INCIDENT
# ============================================================


incident_text = st.text_area(
    "Incident",
    height=280,
    placeholder=(
        "Paste the production incident ticket..."
    ),
)


if not st.button(
    "Run Investigation",
    type="primary",
):
    st.stop()


if not incident_text.strip():
    st.error(
        "Paste an incident first."
    )
    st.stop()


# ============================================================
# INVESTIGATION
# ============================================================


with st.spinner(
    "Investigating..."
):
    try:
        result = run_investigation(
            incident_text=incident_text,
            openai_api_key=(
                st.session_state[
                    "openai_api_key"
                ]
            ),
        )

    except Exception as exc:
        st.error(
            f"Investigation stopped: {exc}"
        )
        st.stop()


# ============================================================
# SUMMARY
# ============================================================


st.divider()


c1, c2, c3 = st.columns(3)


c1.metric(
    "Incident",
    result.incident.incident_id
    or "Unknown",
)


c2.metric(
    "Rounds",
    result.rounds_used,
)


c3.metric(
    "Confidence",
    result.final_rca.confidence.value,
)


# ============================================================
# FINAL RCA
# ============================================================


st.subheader(
    "Final RCA"
)


st.success(
    result.final_rca.conclusion
    or "No conclusion returned."
)


if result.final_rca.stop_reason:
    st.caption(
        "Stop reason: "
        + result.final_rca.stop_reason.value
    )


with st.expander(
    "RCA reasoning"
):
    st.write(
        result.final_rca.reasoning_summary
    )


# ============================================================
# EVIDENCE
# ============================================================


st.subheader(
    "Investigation State"
)


confirmed_tab, ruled_tab, open_tab = st.tabs(
    [
        (
            "✅ Confirmed "
            f"({len(result.evidence_state.confirmed)})"
        ),
        (
            "🚫 Ruled out "
            f"({len(result.evidence_state.ruled_out)})"
        ),
        (
            "❓ Open "
            f"({len(result.evidence_state.open_questions)})"
        ),
    ]
)


with confirmed_tab:
    if not result.evidence_state.confirmed:
        st.caption(
            "No confirmed findings."
        )

    for fact in (
        result.evidence_state.confirmed
    ):
        st.markdown(
            f"""
<div class="fact">
<b>{fact.statement}</b><br/>
<small>
{fact.domain.upper()}
 · {fact.confidence.value}
 · {fact.kind.value}
</small>
</div>
""",
            unsafe_allow_html=True,
        )


with ruled_tab:
    if not result.evidence_state.ruled_out:
        st.caption(
            "No hypotheses ruled out."
        )

    for item in (
        result.evidence_state.ruled_out
    ):
        st.markdown(
            f"""
<div class="fact">
<b>{item.hypothesis}</b><br/>
{item.reason}<br/>
<small>
{item.domain.upper()}
 · {item.confidence.value}
</small>
</div>
""",
            unsafe_allow_html=True,
        )


with open_tab:
    if not result.evidence_state.open_questions:
        st.caption(
            "No open questions."
        )

    for item in (
        result.evidence_state.open_questions
    ):
        st.markdown(
            f"""
<div class="fact">
<b>{item.question}</b><br/>
<small>
{item.availability.value.upper()}
 · suggested domain: {item.suggested_domain or "n/a"}
</small>
</div>
""",
            unsafe_allow_html=True,
        )


# ============================================================
# AGENT TRACE
# ============================================================


st.subheader(
    "Agent Decisions"
)


for entry in result.domain_history:
    with st.container(
        border=True
    ):
        left, right = st.columns(
            [1, 3]
        )

        with left:
            st.markdown(
                f"### Round {entry['round']}"
            )

            st.caption(
                "RCA selected"
            )

            st.write(
                entry["domain"].upper()
            )

            st.caption(
                "Tools chosen"
            )

            tools = (
                entry.get("tools")
                or []
            )

            if tools:
                for tool_name in tools:
                    st.markdown(
                        f"`{tool_name}`"
                    )
            else:
                st.markdown(
                    "`NO TOOL`"
                )

        with right:
            st.caption(
                "RCA request"
            )

            st.write(
                entry[
                    "request"
                ][
                    "question"
                ]
            )

            st.caption(
                "Domain assessment"
            )

            st.write(
                entry[
                    "domain_update"
                ][
                    "summary"
                ]
            )

            findings = (
                entry[
                    "domain_update"
                ].get(
                    "new_confirmed",
                    [],
                )
            )

            if findings:
                st.caption(
                    "New findings"
                )

                for finding in findings:
                    st.markdown(
                        f"• {finding['statement']}"
                    )


# ============================================================
# FULL AUDIT
# ============================================================


st.divider()


report = result.model_dump_json(
    indent=2
)


incident_id = (
    result.incident.incident_id
    or "investigation"
)


st.download_button(
    "Download Full Investigation Audit",
    data=report,
    file_name=(
        f"{incident_id}_analysis.json"
    ),
    mime="application/json",
)