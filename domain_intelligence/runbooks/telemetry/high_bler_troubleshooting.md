---
domain: telemetry
topic: high_bler
technology: generic
vendor: generic
version: 1.0
status: active
knowledge_type: troubleshooting_runbook
---

# High BLER Troubleshooting

## Purpose

Use this runbook when telemetry indicates elevated downlink BLER, uplink BLER, or both, or when an incident reports symptoms that may be associated with radio-link reliability degradation.

BLER is evidence of block-level radio transmission or decoding reliability. Elevated BLER can establish a radio reliability impairment, but BLER alone does not identify the underlying physical root cause.

The investigation should determine:

- whether the impairment is real and material;
- whether it is uplink, downlink, or bidirectional;
- whether it is persistent or intermittent;
- what other telemetry changes align with it;
- which plausible mechanisms are supported or contradicted;
- whether telemetry is sufficient to continue the investigation.

---

## Typical Symptoms

High BLER may be relevant when an incident reports:

- unstable or degraded data transfer;
- intermittent throughput degradation;
- upload or download degradation;
- periods of poor performance followed by recovery;
- radio performance degradation while connectivity remains established;
- asymmetric uplink/downlink performance;
- degraded application performance that may be associated with radio reliability.

Do not assume these symptoms are caused by BLER until telemetry establishes an association.

---

## First Investigation Question

Determine the direction of the reliability impairment.

Investigate:

- DL BLER;
- UL BLER;
- whether one direction is materially worse;
- whether both directions are affected.

Classify the measured impairment as one of:

- predominantly downlink;
- predominantly uplink;
- bidirectional;
- no material BLER impairment established.

Directionality should influence subsequent investigation.

---

## Establish the BLER Behavior

Do not rely only on an average or maximum.

Where sample-level telemetry is available, examine:

- distribution;
- frequency of elevated values;
- persistence;
- peaks;
- affected sample proportion;
- temporal behavior;
- periods of recovery.

A high maximum with otherwise healthy samples may represent an isolated event.

A materially elevated distribution across many samples provides stronger evidence of sustained reliability impairment.

If the incident describes intermittent degradation, use time-resolved evidence rather than average/min/max statistics alone.

---

## Check Temporal Alignment

Determine whether BLER degradation occurs during the same periods as the reported or measurable service degradation.

Useful comparisons may include:

- BLER versus traffic behavior;
- BLER versus packet activity;
- BLER versus MCS;
- BLER versus signal metrics;
- BLER versus resource utilization.

Temporal alignment strengthens an association.

Lack of temporal alignment weakens a claim that BLER is responsible for the reported service behavior.

Correlation or alignment does not by itself establish physical causation.

---

## Evaluate Signal Strength

Use RSRP to determine whether received signal strength may contribute to the impairment.

### Pattern: BLER elevated and RSRP degraded

This supports further investigation of a coverage-related or radio-condition-related mechanism.

Check whether:

- RSRP degradation is persistent;
- BLER increases when RSRP deteriorates;
- MCS changes during the same periods;
- available signal-quality metrics also degrade.

Do not conclude antenna failure, hardware failure, or a coverage hole from RSRP alone.

### Pattern: BLER elevated while RSRP remains healthy and stable

Weak received signal strength becomes less supported as the primary explanation.

Continue investigating:

- signal quality;
- link adaptation;
- resource behavior;
- temporal patterns;
- other domain evidence.

Healthy RSRP does not prove healthy signal quality and does not rule out interference or other radio mechanisms.

---

## Evaluate Signal Quality

For uplink investigation, use UL SNR when available.

Compare:

- UL SNR versus UL BLER;
- UL SNR versus UL MCS;
- UL SNR during degraded versus recovered periods.

### Pattern: UL SNR degrades while UL BLER increases

This supports a signal-quality-related contribution to the uplink reliability impairment.

### Pattern: UL BLER is elevated while UL SNR remains stable

The available SNR evidence does not explain the BLER behavior.

Continue investigating other mechanisms.

Do not automatically conclude interference.

The current telemetry dataset does not contain a direct interference-power measurement or an equivalent explicit interference-source indicator.

For downlink investigations, recognize that the current dataset does not contain a direct DL SNR/SINR metric. Do not substitute UL SNR as evidence of downlink signal quality.

---

## Evaluate Link Adaptation

Inspect the corresponding MCS.

For downlink:

- DL BLER;
- DL MCS;
- RSRP.

For uplink:

- UL BLER;
- UL MCS;
- UL SNR;
- RSRP where relevant.

### Pattern: MCS decreases as radio conditions degrade

This can be consistent with link adaptation responding to poorer conditions.

### Pattern: BLER remains high despite MCS adaptation

This supports persistent reliability impairment despite adaptation.

### Pattern: MCS remains stable while BLER changes materially

MCS behavior may not be the primary measured differentiator.

Do not conclude scheduler failure, link-adaptation algorithm failure, or software defect from MCS behavior alone.

---

## Evaluate Resource Congestion

Inspect the corresponding radio resource utilization.

For downlink:

- PRB_Utilization_DL;
- PRBs_DL_Current;
- relevant traffic indicators.

For uplink:

- PRB_Utilization_UL;
- PRBs_UL_Current;
- UL_NPRB;
- Estimated_UL_Buffer;
- relevant traffic indicators.

### Pattern: BLER elevated while absolute PRB utilization remains low

Radio resource saturation becomes less supported as the primary mechanism.

### Pattern: BLER and service degradation occur during persistently high resource utilization

Resource congestion becomes a relevant competing or contributing hypothesis.

Check whether demand indicators and buffer pressure support the same explanation.

High BLER alone does not prove congestion.

High PRB utilization alone does not prove congestion-related service impact.

---

## Investigate Directional Asymmetry

A strong UL/DL asymmetry can materially narrow the investigation.

### Uplink-dominant BLER

Prioritize:

- UL SNR;
- UL MCS;
- UL PRB utilization;
- UL NPRB;
- Estimated UL Buffer;
- uplink packet and byte activity.

Do not assume an uplink interference source without direct supporting evidence.

### Downlink-dominant BLER

Prioritize:

- DL MCS;
- RSRP;
- DL PRB utilization;
- downlink packet and byte activity.

Remember that the current dataset does not provide a direct downlink SNR/SINR metric.

---

## Investigate Intermittent BLER

When the incident describes periodic stalls, bursts, or recovery:

1. identify periods of elevated BLER;
2. identify periods where BLER recovers;
3. compare other metrics between those periods;
4. determine which metrics change consistently with BLER;
5. avoid relying on window-wide averages alone.

Useful aligned variables include:

- MCS;
- UL SNR;
- RSRP;
- PRB utilization;
- Estimated UL Buffer;
- packet activity;
- traffic indicators.

Repeated degradation/recovery patterns may justify checking alarm or event data for corresponding activation/clear cycles.

---

## Evidence That Can Be Confirmed From Telemetry

When supported by the measurements, the telemetry specialist may conclude:

- a radio reliability impairment exists;
- whether the impairment is UL, DL, or bidirectional;
- whether it is persistent or intermittent;
- whether signal strength degradation is associated with it;
- whether available uplink signal-quality degradation is associated with it;
- whether link-adaptation behavior changes with it;
- whether resource congestion is supported or contradicted;
- whether measured telemetry variables align temporally with the impairment.

---

## Conclusions Telemetry Must Not Make Without Additional Evidence

High BLER alone does not establish:

- interference;
- interference source;
- antenna failure;
- radio hardware failure;
- scheduler defect;
- software defect;
- transport failure;
- packet loss;
- handover failure;
- physical root cause.

These may remain hypotheses, but they must be clearly distinguished from confirmed evidence.

---

## Cross-Domain Escalation

### Request Alarm / Event Analysis When

- reliability impairment is confirmed but the mechanism remains unexplained;
- equipment or processing failure is suspected;
- repeated telemetry degradation may correspond to alarm activation/clear cycles;
- radio, scheduler, transport, or hardware events could discriminate remaining hypotheses.

A useful request is:

"Determine whether radio, hardware, processing, transport, or related alarms/events align temporally with the confirmed BLER impairment."

### Request Topology Analysis When

- affected entities may share infrastructure;
- degradation appears localized to a network element;
- a common radio or transport dependency is suspected;
- blast radius or dependency relationships may distinguish hypotheses.

A useful request is:

"Determine whether the affected entities share a common radio, site, processing, or transport dependency that could explain the observed impairment."

---

## When Telemetry Is Insufficient

Stop expanding telemetry queries when the remaining root-cause hypotheses require evidence that telemetry does not contain.

Examples include:

- direct interference measurements;
- HARQ/retransmission reason information;
- hardware diagnostics;
- antenna-path faults;
- detailed scheduler diagnostics;
- explicit handover events;
- software fault information;
- topology relationships.

Return the confirmed telemetry impairment, supported and contradicted hypotheses, missing evidence, and recommended domain escalation to the RCA agent.

Do not continue generating increasingly complex SQL when the required evidence is unavailable.

---

## Common Investigation Mistakes

Avoid:

- treating BLER as packet loss;
- treating BLER as the physical root cause;
- declaring interference because BLER is high;
- declaring congestion without absolute resource pressure;
- using healthy RSRP to claim all radio conditions are healthy;
- using UL SNR to explain downlink signal quality;
- calling an impairment intermittent based only on average/min/max values;
- deriving throughput from byte fields without validated time and counter semantics;
- assuming correlation establishes causation;
- repeatedly querying telemetry for evidence that the schema does not contain;
- expanding SQL complexity when a simpler discriminating check is sufficient.

---

## Recommended Investigation Principle

Use the smallest amount of evidence necessary to distinguish the active hypotheses.

The objective is not to collect every available KPI.

The objective is to determine what telemetry establishes, what it contradicts, what remains plausible, and what evidence or domain is required next.