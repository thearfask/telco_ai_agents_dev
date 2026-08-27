┌──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                      TELCO AI INCIDENT INVESTIGATOR — LOCAL V1                                               │
└──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘


     DATA SOURCES                 LOCAL DATA / ETL                 DATA ACCESS                 AI INVESTIGATION                USER
          │                              │                             │                              │                         │
          │                              │                             │                              │                         │
          ▼                              ▼                             ▼                              ▼                         ▼

┌───────────────────┐          ┌─────────────────────┐        ┌───────────────────┐        ┌──────────────────────┐     ┌──────────────────┐
│ PUBLIC DATASETS   │          │ LOCAL PYTHON ETL    │        │    DUCKDB         │        │ INVESTIGATION        │     │ STREAMLIT ITSM   │
│                   │          │                     │        │                   │        │ ORCHESTRATOR         │     │                  │
│ TelecomTS         │─────────▶│ Extract             │───────▶│ Telemetry         │───┐    │                      │     │ Incident Queue   │
│ TeleLogs          │          │ Validate            │        │ Alarms            │   │    │ Receives INC-124     │     │                  │
│ NIST (later)      │          │ Normalize           │        │ Changes           │   │    │                      │     │ INC-124          │
└───────────────────┘          │ Enrich              │        │ Topology          │   │    │ Creates investigation│     │ Priority: P1     │
                               │                     │        │ Incidents         │   │    └──────────┬───────────┘     │ Status: New      │
┌───────────────────┐          │ Python + uv         │        └───────────────────┘   │               │                 └────────┬─────────┘
│ SYNTHETIC DATA    │          └──────────┬──────────┘                                │               │                          │
│                   │                     │                                           │               ▼                          │
│ Topology          │─────────────────────┤                                           │    ┌──────────────────────┐              │
│ Alarms            │                     │                                           │    │ DOMAIN AGENTS        │              │
│ Changes           │                     ▼                                           │    │                      │              │
│ Incidents         │          ┌─────────────────────┐                                ├───▶│ Telemetry Agent      │              │
│ Config history    │          │ CURATED PARQUET     │                                │    │ Log Agent            │              │
└───────────────────┘          │                     │                                │    │ Topology Agent       │              │
                               │ telemetry.parquet   │                                │    │ Change Agent         │              │
┌───────────────────┐          │ alarms.parquet      │                                │    │ History Agent        │              │
│ LOCAL RAW LOGS    │          │ topology.parquet    │                                │    └──────────┬───────────┘              │
│                   │─────────▶│ changes.parquet     │                                │               │                          │
│ RAN logs          │          │ incidents.parquet   │                                │               │ tool calls               │
│ Transport logs    │          └─────────────────────┘                                │               ▼                          │
│ Core logs         │                                                                 │     ┌──────────────────────┐             │
└───────────────────┘                                                                 │     │ LOCAL MCP / TOOLS    │             │
                                                                                      │     │                      │             │
┌───────────────────┐          ┌─────────────────────┐        ┌───────────────────┐   └───-▶│ get_telemetry()      │             │
│ KNOWLEDGE         │          │ DOCUMENT PIPELINE   │        │      QDRANT       │────────▶│ search_logs()        │             │
│                   │─────────▶│                     │───────▶│                   │         │ get_topology()       │             │
│ Runbooks          │          │ Clean               │        │ Historical RCA    │         │ get_changes()        │             │
│ Historical RCA    │          │ Chunk               │        │ Runbooks          │         │ search_history()     │             │
│ Troubleshooting   │          │ Embed               │        │ Troubleshooting   │         │ search_runbooks()    │             │
└───────────────────┘          └─────────────────────┘        └───────────────────┘         └──────────┬───────────┘             │
                                                                                                       │                         │
                                                                                                       ▼                         │
                                                                                           ┌──────────────────────┐              │
                                                                                           │       GROQ           │              │
                                                                                           │                      │              │
                                                                                           │ Cloud LLM inference  │              │
                                                                                           │ Reasoning            │              │
                                                                                           │ Tool selection       │              │
                                                                                           └──────────┬───────────┘              │
                                                                                                      │                          │
                                                                                                      ▼                          │
                                                                                           ┌──────────────────────┐              │
                                                                                           │ RCA / VERIFIER       │              │
                                                                                           │                      │              │
                                                                                           │ Correlate evidence   │              │
                                                                                           │ Rank hypotheses      │              │
                                                                                           │ Reject false causes  │              │
                                                                                           │ Confidence           │              │
                                                                                           │ Recommended action   │              │
                                                                                           └──────────┬───────────┘              │
                                                                                                      │                          │
                                                                                                      ▼                          ▼
                                                                                           ┌──────────────────────────────────────┐
                                                                                           │          AI INITIAL FINDINGS         │
                                                                                           │                                      │
                                                                                           │ Likely RCA                           │
                                                                                           │ Evidence                             │
                                                                                           │ Incident timeline                    │
                                                                                           │ Correlated changes                   │
                                                                                           │ Affected components                  │
                                                                                           │ Rejected hypotheses                  │
                                                                                           │ Confidence                           │
                                                                                           │ Recommended next action              │
                                                                                           └──────────────────┬───────────────────┘
                                                                                                              │
                                                                                                              ▼
                                                                                                   ┌──────────────────────┐
                                                                                                   │   HUMAN ENGINEER     │
                                                                                                   │                      │
                                                                                                   │ Reviews findings     │
                                                                                                   │ Investigates further │
                                                                                                   │ Takes action         │
                                                                                                   │ Resolves incident    │
                                                                                                   └──────────────────────┘