from __future__ import annotations

from dotenv import load_dotenv

load_dotenv()

import streamlit as st

from telco_ai_investigator_v1.poc.investigation_graph import (
    run_investigation,
)


# ============================================================
# PAGE
# ============================================================


st.set_page_config(
    page_title="Telco RCA Investigator",
    page_icon="📡",
    layout="wide",
)


st.markdown(
    """
<style>

.block-container {
    max-width: 1450px;
    padding-top: 1.8rem;
    padding-bottom: 3rem;
}

.title {
    font-size: 2.25rem;
    font-weight: 750;
    margin-bottom: .15rem;
}

.subtitle {
    opacity: .65;
    margin-bottom: 1.4rem;
}

.round-card {
    border: 1px solid rgba(128,128,128,.22);
    border-radius: 15px;
    padding: 16px;
    height: 100%;
}

.label {
    margin-top: 14px;
    margin-bottom: 4px;
    opacity: .58;
    font-size: .72rem;
    text-transform: uppercase;
    letter-spacing: .07rem;
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
    padding: 8px 0;
    border-bottom: 1px solid rgba(128,128,128,.12);
}

</style>
""",
    unsafe_allow_html=True,
)


st.markdown(
    '<div class="title">📡 Telco RCA Investigator</div>',
    unsafe_allow_html=True,
)

st.markdown(
    """
<div class="subtitle">
LangGraph · specialist agents · autonomous tool selection · bounded evidence
</div>
""",
    unsafe_allow_html=True,
)


# ============================================================
# INPUT
# ============================================================


incident_text = st.text_area(
    "Incident",
    height=280,
    placeholder=(
        "Paste the production-style incident ticket..."
    ),
)


clicked = st.button(
    "Run Investigation",
    type="primary",
)


if not clicked:
    st.stop()


if not incident_text.strip():

    st.error(
        "Paste an incident first."
    )

    st.stop()


# ============================================================
# RUN
# ============================================================


with st.spinner(
    "Investigating..."
):

    try:

        result = run_investigation(
            incident_text
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


c1, c2, c3 = st.columns(
    3
)


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


st.caption(
    "Stop reason: "
    + (
        result.final_rca.stop_reason.value
        if result.final_rca.stop_reason
        else "unknown"
    )
)


with st.expander(
    "RCA reasoning"
):

    st.write(
        result.final_rca.reasoning_summary
    )


# ============================================================
# EVIDENCE STATE
# ============================================================


st.subheader(
    "Investigation State"
)


tab1, tab2, tab3 = st.tabs(
    [
        f"✅ Confirmed ({len(result.evidence_state.confirmed)})",
        f"🚫 Ruled out ({len(result.evidence_state.ruled_out)})",
        f"❓ Open ({len(result.evidence_state.open_questions)})",
    ]
)


with tab1:

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


with tab2:

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


with tab3:

    for item in (
        result.evidence_state.open_questions
    ):

        st.markdown(
            f"""
<div class="fact">
<b>{item.question}</b><br/>
<small>
{item.availability.value.upper()}
 · suggested: {item.suggested_domain or "n/a"}
</small>
</div>
""",
            unsafe_allow_html=True,
        )


# ============================================================
# ROUND TRACE
# ============================================================


st.subheader(
    "Agent Decisions"
)


if result.domain_history:

    columns = st.columns(
        len(
            result.domain_history
        )
    )

    for index, entry in enumerate(
        result.domain_history
    ):

        with columns[index]:

            st.markdown(
                '<div class="round-card">',
                unsafe_allow_html=True,
            )

            st.markdown(
                f"### Round {entry['round']}"
            )

            st.markdown(
                '<div class="label">RCA selected</div>',
                unsafe_allow_html=True,
            )

            st.write(
                entry["domain"].upper()
            )

            st.markdown(
                '<div class="label">Domain request</div>',
                unsafe_allow_html=True,
            )

            st.write(
                entry[
                    "request"
                ][
                    "question"
                ]
            )

            st.markdown(
                '<div class="label">Tools chosen</div>',
                unsafe_allow_html=True,
            )

            tools = (
                entry.get(
                    "tools"
                )
                or []
            )

            if not tools:

                st.markdown(
                    '<span class="tool">NO TOOL</span>',
                    unsafe_allow_html=True,
                )

            else:

                for tool_name in tools:

                    st.markdown(
                        f'<span class="tool">{tool_name}</span>',
                        unsafe_allow_html=True,
                    )

            update = entry[
                "domain_update"
            ]

            st.markdown(
                '<div class="label">Domain assessment</div>',
                unsafe_allow_html=True,
            )

            st.write(
                update[
                    "summary"
                ]
            )

            confirmed = (
                update.get(
                    "new_confirmed"
                )
                or []
            )

            if confirmed:

                st.markdown(
                    '<div class="label">New findings</div>',
                    unsafe_allow_html=True,
                )

                for fact in confirmed:

                    st.markdown(
                        f"• {fact['statement']}"
                    )

            st.markdown(
                "</div>",
                unsafe_allow_html=True,
            )


# ============================================================
# DOWNLOAD FULL AUDIT
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