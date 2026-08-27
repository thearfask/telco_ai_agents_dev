---
domain: telemetry
topic: throughput_degradation
technology: generic
vendor: generic
version: 1.0
status: active
knowledge_type: troubleshooting_runbook
---

# Throughput Degradation Investigation

## Purpose

Use this runbook when an incident reports slow data transfer, reduced upload/download performance, throughput degradation, or periods where application traffic performs substantially worse than expected.

The telemetry investigation should determine which measured network condition best explains the reported degradation.

Potential contributors include:

- radio reliability impairment;
- poor signal conditions;
- radio resource congestion;
- link-adaptation behavior;
- uplink buffer pressure;
- directional impairment;
- intermittent degradation;
- mechanisms outside the telemetry domain.

The current dataset does not contain a directly validated throughput KPI.

Do not manufacture throughput from byte counters unless their semantics and time basis are established.

---

## Current Dataset Capability

The current telemetry dataset provides traffic-related fields including:

- TX_Bytes;
- RX_Bytes;
- UL_NumberOfPackets;
- DL_NumberOfPackets;
- UL_Protocol;
- DL_Protocol;
- Estimated_UL_Buffer.

It also provides radio-performance evidence including:

- DL_BLER;
- UL_BLER;
- DL_MCS;
- UL_MCS;
- RSRP;
- UL_SNR;
- PRB_Utilization_DL;
- PRB_Utilization_UL;
- PRBs_DL_Current;
- PRBs_UL_Current;
- UL_NPRB.

These metrics can help identify conditions associated with reported throughput degradation.

They do not automatically provide measured throughput.

---

## First Investigation Question

Determine the affected direction.

Classify the incident, where possible, as:

- uplink degradation;
- downlink degradation;
- bidirectional degradation;
- direction unknown.

Directionality determines which telemetry should be prioritized.

### Uplink

Prioritize:

- UL_BLER;
- UL_SNR;
- UL_MCS;
- PRB_Utilization_UL;
- PRBs_UL_Current;
- UL_NPRB;
- Estimated_UL_Buffer;
- TX_Bytes;
- UL_NumberOfPackets.

### Downlink

Prioritize:

- DL_BLER;
- DL_MCS;
- RSRP;
- PRB_Utilization_DL;
- PRBs_DL_Current;
- RX_Bytes;
- DL_NumberOfPackets.

Do not investigate every available KPI if the incident already establishes a clear direction.

---

## Establish Whether Traffic Behavior Actually Changes

Before attributing the incident to a radio mechanism, determine whether available traffic indicators change during the affected period.

Inspect:

- byte values;
- packet counts;
- traffic presence;
- protocol where relevant;
- temporal behavior.

The objective is to identify traffic activity and changes in traffic behavior.

Do not assume lower byte values automatically mean lower network throughput.

Traffic demand itself may have changed.

---

## Critical Byte-Counter Rule

TX_Bytes and RX_Bytes must not automatically be converted into throughput.

Before calculating a rate, establish whether these fields represent:

- cumulative counters;
- bytes during each sample interval;
- instantaneous measurements;
- another source-defined quantity.

Also establish:

- sampling interval;
- counter reset behavior;
- timestamp consistency;
- direction semantics.

Without this information, a calculation such as:

bytes × 8 / time

may be invalid.

If semantics are unknown, describe TX_Bytes and RX_Bytes as traffic or byte measurements, not throughput.

---

## Packet-Count Rule

UL_NumberOfPackets and DL_NumberOfPackets indicate packet activity according to the source measurement.

They do not establish:

- packet loss;
- packet error rate;
- retransmission rate;
- successful delivery rate.

Do not compare packet counts and infer packet loss unless the dataset provides the required sent/received semantics.

---

## Investigate Radio Reliability

Elevated BLER can reduce effective data delivery and should be evaluated early.

### Downlink

Compare:

- DL_BLER;
- DL_MCS;
- RSRP;
- DL resource utilization;
- DL traffic activity.

### Uplink

Compare:

- UL_BLER;
- UL_SNR;
- UL_MCS;
- UL resource utilization;
- Estimated_UL_Buffer;
- UL traffic activity.

### Pattern: reported degradation + elevated BLER

This supports radio reliability impairment as a candidate contributor.

Strengthen the hypothesis by checking whether BLER changes align temporally with traffic degradation.

### Pattern: reported degradation + healthy BLER

Radio block reliability becomes less supported as the dominant measured explanation.

Continue investigating resource pressure, signal conditions, buffering, and other mechanisms.

---

## Investigate Radio Resource Congestion

Inspect PRB utilization in the affected direction.

### Pattern: sustained high utilization + high demand + degradation

This supports radio resource pressure as a possible contributor.

Check:

- persistence;
- packet/byte activity;
- buffer pressure where available;
- BLER;
- MCS.

### Pattern: low utilization during degradation

Radio resource saturation becomes less supported.

Do not label the incident congestion simply because throughput is reported as poor.

### Pattern: high utilization + high BLER

Both resource pressure and reliability impairment may contribute.

Do not force a single-cause explanation prematurely.

---

## Investigate Signal Conditions

### Signal Strength

Use RSRP to assess received signal strength.

### Uplink Signal Quality

Use UL_SNR for uplink signal-quality assessment.

### Pattern: degraded RSRP + BLER degradation + MCS degradation

This supports a radio-condition or coverage-related contribution.

### Pattern: healthy RSRP + degraded UL SNR + elevated UL BLER

Weak signal strength alone becomes less supported.

An uplink signal-quality impairment may be contributing.

Do not conclude interference without additional evidence.

### Pattern: signal metrics remain stable

Available signal evidence does not explain the throughput degradation.

Continue with other hypotheses.

---

## Investigate Link Adaptation

MCS affects radio transmission efficiency and can help explain changing performance.

Inspect:

- DL_MCS with DL_BLER and RSRP;
- UL_MCS with UL_BLER and UL_SNR.

### Pattern: MCS decreases during degraded radio conditions

This is consistent with adaptation toward more robust but potentially less efficient transmission.

It may contribute to reduced effective data rate.

### Pattern: MCS stable while performance changes substantially

Link-adaptation behavior becomes less useful as the primary measured differentiator.

Do not declare an MCS or scheduler fault from MCS behavior alone.

---

## Investigate Uplink Buffer Pressure

For uplink incidents, inspect Estimated_UL_Buffer.

### Pattern: buffer increases + UL PRB utilization increases

This supports uplink demand/resource pressure.

### Pattern: buffer increases + UL BLER increases

Poor radio reliability may be preventing efficient uplink delivery and contributing to backlog.

### Pattern: buffer increases while UL resources remain available

Radio resource saturation may not explain the backlog.

Investigate:

- UL BLER;
- UL SNR;
- UL MCS;
- other-domain mechanisms.

### Pattern: buffer remains low

Buffer pressure becomes less supported as the dominant measured mechanism.

---

## Investigate Directional Asymmetry

Compare uplink and downlink evidence.

### Uplink degradation with healthy downlink telemetry

Prioritize uplink-specific mechanisms:

- UL reliability;
- UL signal quality;
- UL resource pressure;
- UL buffer pressure;
- UL link adaptation.

### Downlink degradation with healthy uplink telemetry

Prioritize:

- DL reliability;
- DL resource pressure;
- DL link adaptation;
- signal-strength behavior.

Do not assume a bidirectional network failure when the telemetry shows a strongly directional impairment.

---

## Investigate Intermittent Throughput Degradation

If the incident describes periodic slowdowns or stalls, avoid relying on window-level averages.

Use:

- event_timestamp;
- sample_index.

Identify:

1. degraded periods;
2. recovered periods;
3. radio metrics that change between them.

Compare:

- BLER;
- SNR where available;
- RSRP;
- MCS;
- PRB utilization;
- Estimated_UL_Buffer;
- traffic indicators.

The useful question is:

"What changes consistently when the reported or observable degradation appears?"

Repeated alignment is more useful than collecting additional unrelated metrics.

---

## Distinguishing Common Hypotheses

### Reliability Impairment

Strengthened by:

- elevated BLER;
- temporal alignment with degradation;
- related signal/MCS changes.

Weakens when:

- BLER remains healthy throughout the incident.

---

### Radio Resource Congestion

Strengthened by:

- sustained high PRB utilization;
- traffic demand;
- buffer pressure;
- temporal alignment with degradation.

Weakens when:

- resources remain consistently underutilized.

---

### Coverage-Related Degradation

Strengthened by:

- degraded RSRP;
- BLER changes aligned with RSRP;
- MCS changes aligned with RSRP.

Weakens when:

- RSRP remains strong and stable.

---

### Uplink Signal-Quality Degradation

Strengthened by:

- degraded UL_SNR;
- elevated UL_BLER;
- UL MCS changes.

Weakens when:

- UL_SNR remains stable and healthy during the degradation.

---

### Buffer / Queue Pressure

Strengthened by:

- increasing Estimated_UL_Buffer;
- alignment with uplink degradation;
- supporting demand/resource or reliability evidence.

Weakens when:

- buffer remains consistently low.

---

### Non-Radio Bottleneck

Consider escalation when:

- degradation is reported or supported by traffic behavior;
- BLER is healthy;
- signal evidence is healthy;
- radio resources are not saturated;
- buffer behavior does not explain the issue.

The telemetry specialist may conclude:

"Available radio telemetry does not provide a sufficient explanation for the reported degradation."

Do not convert this into:

"Transport is the root cause."

Transport or another domain must provide its own evidence.

---

## Baseline Comparison

Where an appropriate baseline is available, compare the affected period with:

- previous healthy windows;
- comparable windows with the same application;
- comparable mobility conditions;
- comparable zone/context;
- other genuinely equivalent operating periods.

Baseline selection must be defensible.

Do not compare unrelated windows simply because they exist.

A baseline can help determine whether:

- BLER changed;
- MCS changed;
- resource utilization changed;
- signal conditions changed;
- traffic behavior changed.

A baseline difference supports a change in network behavior.

It does not automatically establish causation.

---

## Protocol Context

UL_Protocol and DL_Protocol may help determine whether traffic composition differs across samples or windows.

Use protocol context when it is relevant to the incident.

Do not assume protocol type itself explains degradation without supporting evidence.

Avoid adding protocol analysis merely because the fields are available.

---

## Evidence That Can Be Confirmed From Telemetry

When supported by measurements, the telemetry specialist may conclude:

- a radio reliability impairment exists;
- resource pressure exists or is contradicted;
- signal-strength degradation exists;
- uplink signal-quality degradation exists;
- link-adaptation behavior changed;
- uplink buffer pressure exists;
- degradation is directionally asymmetric;
- measured conditions align temporally with traffic behavior;
- radio telemetry does or does not provide a plausible explanation for the reported degradation.

---

## Conclusions Telemetry Must Not Make Without Additional Evidence

The current telemetry alone should not establish:

- exact user throughput unless derivation is validated;
- packet loss;
- transport congestion;
- backhaul failure;
- application-server bottleneck;
- scheduler software failure;
- hardware failure;
- interference source;
- physical root cause outside measurable radio behavior.

---

## Cross-Domain Escalation

### Request Alarm / Event Analysis When

- telemetry identifies degradation but the physical mechanism remains unresolved;
- performance changes abruptly;
- equipment, processing, scheduler, or transport events may explain the timing;
- recurring degradation may align with repeated operational events.

A useful request is:

"Check whether radio, processing, capacity, hardware, transport, or related alarms/events align with the degraded periods."

### Request Topology Analysis When

- multiple affected entities may share infrastructure;
- radio telemetry does not explain the full impact;
- a shared transport, site, processing, or network dependency may create the observed blast radius.

A useful request is:

"Determine whether affected entities share infrastructure or network dependencies that could explain the reported performance degradation."

---

## When Telemetry Is Insufficient

Stop expanding telemetry queries when:

- radio reliability has been evaluated;
- radio resource pressure has been evaluated;
- available signal conditions have been evaluated;
- link adaptation has been evaluated where relevant;
- buffer pressure has been evaluated where relevant;
- remaining hypotheses require evidence outside the telemetry schema.

Return:

- confirmed findings;
- materially ruled-out hypotheses;
- remaining hypotheses;
- missing evidence;
- recommended domain escalation.

Do not compensate for missing evidence by generating increasingly complicated SQL.

---

## Common Investigation Mistakes

Avoid:

- treating TX_Bytes or RX_Bytes as throughput without validated semantics;
- treating packet counts as packet loss;
- assuming poor throughput means congestion;
- assuming high BLER is the root cause rather than an impairment;
- ignoring UL/DL directionality;
- ignoring signal quality because RSRP looks healthy;
- declaring interference from poor UL_SNR;
- declaring transport congestion because radio congestion was ruled out;
- comparing unrelated windows as a baseline;
- querying every available KPI instead of selecting discriminating evidence;
- repeatedly investigating a hypothesis that has already been materially contradicted.

---

## Recommended Investigation Principle

Reported throughput degradation is a symptom, not a diagnosis.

The telemetry specialist should ask:

"What measured network condition changes when performance degrades?"

Then discriminate between:

- reliability;
- signal conditions;
- resource pressure;
- link adaptation;
- buffering;
- directionality;
- non-radio mechanisms.

The goal is not to manufacture a throughput number.

The goal is to identify the strongest telemetry-supported explanation and clearly state what telemetry cannot determine.