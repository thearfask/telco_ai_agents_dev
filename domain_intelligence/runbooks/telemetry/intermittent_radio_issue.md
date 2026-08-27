---
domain: telemetry
topic: intermittent_radio_issue
technology: generic
vendor: generic
version: 1.0
status: active
knowledge_type: troubleshooting_runbook
---

# Intermittent Radio Issue Investigation

## Purpose

Use this runbook when an incident reports periodic, bursty, transient, or intermittent radio/service degradation with periods of recovery.

Examples include:

- intermittent throughput degradation;
- periodic upload/download stalls;
- short bursts of high BLER;
- temporary signal-quality degradation;
- recurring performance drops;
- degradation that appears and disappears within the telemetry window.

Intermittent incidents require time-resolved analysis.

Window-wide averages can hide short but operationally significant events.

The objective is to determine:

- whether the impairment is genuinely intermittent;
- when degraded periods occur;
- which telemetry metrics change during those periods;
- whether the same pattern repeats;
- which hypotheses are supported or contradicted;
- whether another domain contains the evidence required to explain the periodic behavior.

---

## Current Dataset Capability

The current telemetry dataset provides sample-level ordering and timing through:

- event_timestamp;
- sample_index.

Relevant time-varying radio measurements include:

### Reliability

- DL_BLER;
- UL_BLER.

### Signal conditions

- RSRP;
- UL_SNR.

### Link adaptation

- DL_MCS;
- UL_MCS.

### Resource behavior

- PRB_Utilization_DL;
- PRB_Utilization_UL;
- PRBs_DL_Current;
- PRBs_UL_Current;
- UL_NPRB.

### Buffer behavior

- Estimated_UL_Buffer.

### Traffic context

- TX_Bytes;
- RX_Bytes;
- UL_NumberOfPackets;
- DL_NumberOfPackets;
- UL_Protocol;
- DL_Protocol.

Use sample-level telemetry when investigating intermittency.

---

## First Investigation Question

Determine whether the issue is actually intermittent.

Do not infer intermittency from:

- high maximum values;
- low minimum values;
- a large difference between minimum and maximum;
- an abnormal average;
- a single outlier.

Intermittency requires evidence that telemetry moves between meaningfully different operating states over time.

A useful pattern is:

healthy
→ degraded
→ recovered

or repeated sequences such as:

healthy
→ degraded
→ recovered
→ degraded
→ recovered

---

## Step 1: Identify the Primary Impairment Metric

Start with the metric most directly related to the reported symptom.

Examples:

### Reliability complaint

Start with:

- DL_BLER;
- UL_BLER.

### Uplink quality complaint

Start with:

- UL_SNR;
- UL_BLER.

### Resource-pressure complaint

Start with:

- PRB_Utilization_DL;
- PRB_Utilization_UL;
- Estimated_UL_Buffer where relevant.

### Coverage-related complaint

Start with:

- RSRP.

Do not begin by analyzing every available metric.

First establish the behavior of the primary impairment.

---

## Step 2: Identify Degraded and Recovered Periods

Use event_timestamp or sample_index to locate periods where the primary metric is degraded.

Then identify periods where the metric returns toward its normal or healthier state.

The analysis should answer:

- when degradation begins;
- how long it persists;
- whether recovery occurs;
- how often the pattern repeats;
- whether intervals between events are similar.

Do not assume periodicity merely because multiple degraded samples exist.

---

## Step 3: Compare Degraded Versus Recovered States

Once degraded periods are identified, compare other telemetry between:

- degraded samples;
- recovered or healthier samples.

This is often more informative than calculating correlations across the entire window.

For example:

```text
Degraded period:
UL_BLER high
UL_SNR poor
UL_MCS lower

Recovered period:
UL_BLER lower
UL_SNR improves
UL_MCS improves