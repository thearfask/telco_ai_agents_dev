---
domain: telemetry
topic: poor_signal_quality
technology: generic
vendor: generic
version: 1.0
status: active
knowledge_type: troubleshooting_runbook
---

# Poor Signal Quality Investigation

## Purpose

Use this runbook when an incident may involve degraded radio signal quality, abnormal SNR, elevated BLER, reduced MCS, or degraded service despite apparently acceptable received signal strength.

The investigation should distinguish between:

- signal strength;
- signal quality;
- radio reliability;
- coverage-related degradation;
- resource congestion;
- link-adaptation behavior;
- possible mechanisms such as interference that require additional evidence.

Signal strength and signal quality are related but are not interchangeable.

Healthy RSRP does not prove healthy radio quality.

Poor signal quality does not by itself identify the physical mechanism causing it.

---

## Current Dataset Capability

The current telemetry dataset provides:

### Signal strength

- RSRP

### Uplink signal quality

- UL_SNR

### Reliability

- UL_BLER
- DL_BLER

### Link adaptation

- UL_MCS
- DL_MCS

### Resource behavior

- PRB_Utilization_UL
- PRB_Utilization_DL
- PRBs_UL_Current
- PRBs_DL_Current
- UL_NPRB

### Additional uplink context

- Estimated_UL_Buffer
- TX_Bytes
- UL_NumberOfPackets

The current dataset does not provide:

- DL SNR;
- DL SINR;
- UL SINR;
- RSRQ;
- explicit interference power;
- noise-floor measurements;
- CQI;
- HARQ ACK/NACK detail;
- retransmission reason categories.

Do not manufacture substitutes for unavailable measurements.

---

## First Investigation Question

Determine whether the suspected quality impairment is:

- uplink;
- downlink;
- bidirectional;
- not established by the available telemetry.

The current dataset provides a direct signal-quality measurement only for the uplink through UL_SNR.

Therefore, uplink and downlink investigations have different evidence limits.

---

## Distinguish Signal Strength From Signal Quality

### Signal Strength

RSRP represents received reference signal power.

It is primarily useful for evaluating received signal strength and supporting coverage-related analysis.

### Signal Quality

UL_SNR represents the relationship between the uplink signal and noise level represented by the measurement.

It provides evidence about uplink signal quality.

These metrics answer different questions.

Do not reason:

"RSRP is healthy, therefore radio quality is healthy."

Also do not reason:

"RSRP is poor, therefore interference exists."

---

## Investigate Uplink Signal Quality

For uplink quality analysis, prioritize:

- UL_SNR;
- UL_BLER;
- UL_MCS;
- RSRP;
- PRB_Utilization_UL;
- Estimated_UL_Buffer where relevant.

Start by establishing the behavior of UL_SNR.

Examine:

- average;
- minimum;
- distribution;
- persistence;
- temporal variation;
- degraded versus recovered periods.

Do not characterize an incident as intermittent using only average and minimum values.

---

## Pattern: Poor UL SNR + Elevated UL BLER

This is strong evidence that uplink signal-quality degradation is associated with uplink reliability impairment.

Check whether:

- UL SNR degradation aligns temporally with UL BLER;
- UL MCS changes during the same periods;
- RSRP also changes;
- the behavior is persistent or intermittent.

This can support a conclusion such as:

"Uplink signal-quality degradation is associated with the observed uplink reliability impairment."

It does not establish:

- interference;
- interference source;
- UE transmitter fault;
- radio hardware fault;
- antenna problem.

---

## Pattern: Poor UL SNR + Reduced UL MCS

This can indicate link adaptation responding to degraded uplink radio conditions.

Check:

- whether UL BLER is also elevated;
- whether MCS reduction follows or aligns with SNR degradation;
- whether RSRP remains stable;
- whether resource pressure is present.

If UL BLER remains healthy, poor SNR may not be producing a material reliability impairment during the observed scope.

Avoid escalating every abnormal KPI into a root-cause claim.

---

## Pattern: Healthy RSRP + Poor UL SNR

This is an important diagnostic pattern.

It suggests that weak received signal strength alone does not explain the observed uplink quality degradation.

This weakens a simple coverage explanation.

Investigate:

- UL BLER;
- UL MCS;
- temporal SNR behavior;
- resource utilization;
- other evidence sources.

Possible mechanisms may include radio-quality effects not represented directly by RSRP.

Interference may remain a hypothesis, but it is not confirmed by this pattern.

Do not conclude:

"RSRP is good and SNR is poor, therefore interference is confirmed."

---

## Pattern: Poor RSRP + Poor UL SNR

This supports degraded radio conditions where received signal strength and uplink signal quality are both impaired.

Check whether:

- UL BLER increases;
- UL MCS decreases;
- degradation aligns temporally;
- poor RSRP is persistent.

This strengthens a coverage-related or broader radio-condition hypothesis.

It still does not establish the physical reason for the degraded conditions.

---

## Pattern: Poor RSRP + Healthy UL SNR

Received signal strength may be weak without a corresponding measured uplink signal-quality degradation.

Investigate:

- UL BLER;
- UL MCS;
- persistence of poor RSRP;
- reported service impact.

Do not assume poor RSRP automatically causes reliability degradation.

The available evidence may support weak coverage conditions without establishing that those conditions caused the incident.

---

## Pattern: Healthy UL SNR + Elevated UL BLER

The available signal-quality metric does not explain the uplink reliability impairment.

Investigate:

- UL MCS;
- RSRP;
- PRB utilization;
- temporal behavior;
- available alarm/event evidence.

Possible mechanisms may remain outside the observable telemetry.

Do not repeatedly query UL_SNR once it has been established that it does not discriminate the remaining hypotheses.

---

## Downlink Signal-Quality Investigation

The current dataset does not provide a direct downlink SNR, SINR, RSRQ, or equivalent explicit downlink signal-quality measurement.

For downlink degradation, available evidence includes:

- DL_BLER;
- DL_MCS;
- RSRP;
- PRB_Utilization_DL;
- PRBs_DL_Current;
- RX_Bytes;
- DL_NumberOfPackets.

These metrics can establish:

- downlink reliability impairment;
- link-adaptation behavior;
- signal-strength behavior;
- resource pressure.

They cannot directly establish downlink signal-quality degradation in the same way UL_SNR can for the uplink.

---

## Critical Directionality Rule

Never use UL_SNR as a direct explanation for downlink signal quality.

For example:

Incorrect:

"DL BLER is high because UL SNR is poor."

Correct:

"DL reliability impairment is confirmed, but the current dataset lacks a direct downlink signal-quality metric required to determine whether degraded DL signal quality explains it."

UL and DL conditions may be related in some environments, but this dataset does not provide sufficient evidence to assume that relationship for a specific incident.

---

## Evaluate Reliability

Signal-quality degradation becomes more operationally meaningful when it aligns with reliability degradation.

For uplink:

- UL_SNR ↔ UL_BLER

For downlink:

- direct signal-quality comparison is unavailable;
- use DL_BLER to establish reliability impairment separately.

### Strong uplink pattern

UL SNR deteriorates and UL BLER rises during the same periods.

### Weak pattern

UL SNR is abnormal but UL BLER and service behavior remain stable.

Do not overstate operational impact without supporting evidence.

---

## Evaluate Link Adaptation

For uplink:

- UL_SNR;
- UL_MCS;
- UL_BLER.

For downlink:

- DL_MCS;
- DL_BLER;
- RSRP.

### Expected diagnostic behavior

Poorer radio conditions may be accompanied by more conservative MCS selection.

This is supporting evidence of link adaptation responding to conditions.

MCS itself is not a root cause.

### Persistent BLER despite adaptation

If BLER remains elevated while MCS changes toward more robust operation, the reliability impairment may be persisting despite adaptation.

This still does not establish why.

---

## Evaluate Resource Pressure

Poor signal quality and congestion can both contribute to degraded service.

Check resource utilization independently.

### Poor signal quality + low resource utilization

Radio resource saturation becomes less supported.

Signal-quality/reliability mechanisms deserve greater attention.

### Poor signal quality + high resource utilization

Multiple contributing mechanisms may coexist.

Do not automatically choose one.

Determine:

- which aligns more strongly with degradation;
- whether resource pressure occurs only during poor quality;
- whether BLER changes independently of utilization;
- whether buffer pressure is present.

---

## Investigate Intermittent Signal Quality

If the incident reports intermittent degradation:

1. identify periods of degraded UL_SNR;
2. identify recovered periods;
3. compare UL_BLER;
4. compare UL_MCS;
5. compare RSRP;
6. compare resource utilization;
7. compare traffic/buffer behavior where relevant.

Look for repeated relationships such as:

UL_SNR deteriorates
→ UL_BLER increases
→ UL_MCS changes
→ service behavior degrades
→ metrics recover

Repeated temporal alignment provides stronger evidence than window-level correlation alone.

---

## Correlation Analysis

Correlation can help identify relationships worth investigating.

For example:

- UL_SNR versus UL_BLER;
- UL_SNR versus UL_MCS;
- RSRP versus BLER;
- RSRP versus MCS.

Use correlation as supporting analytical evidence.

Do not interpret weak correlation as proof that no relationship exists.

Radio impairments may be:

- nonlinear;
- threshold-dependent;
- intermittent;
- delayed;
- influenced by multiple variables.

Likewise, strong correlation does not establish physical causation.

Where possible, combine correlation with temporal and distributional analysis.

---

## Interference Hypothesis

Interference may produce degraded signal quality and reliability.

However, the current dataset does not contain a direct interference measurement.

Patterns that may justify keeping interference as a hypothesis include:

- degraded UL_SNR;
- elevated UL_BLER;
- comparatively healthy RSRP;
- degraded UL MCS;
- temporal alignment between these behaviors.

This evidence may support:

"An uplink signal-quality impairment exists and is not explained by weak signal strength alone."

It does not support:

"Interference is confirmed."

The distinction is important.

---

## Coverage vs Signal Quality

### Coverage-related hypothesis strengthened by

- degraded RSRP;
- persistent weak signal strength;
- BLER degradation aligned with RSRP;
- MCS changes aligned with RSRP.

### Signal-quality hypothesis strengthened by

- degraded UL_SNR;
- BLER aligned with UL_SNR;
- MCS aligned with UL_SNR.

### Simple coverage hypothesis weakened by

- strong and stable RSRP during degradation.

### Interference remains unconfirmed when

- signal quality is degraded but no direct interference measurement or corroborating domain evidence exists.

---

## Evidence That Can Be Confirmed From Telemetry

When supported by measurements, the telemetry specialist may conclude:

- uplink signal quality is degraded;
- received signal strength is degraded;
- uplink quality degradation aligns with UL reliability impairment;
- uplink quality degradation aligns with MCS behavior;
- weak signal strength is supported or contradicted as an explanation;
- radio resource congestion is supported or contradicted;
- the available telemetry cannot directly measure downlink signal quality;
- the physical mechanism remains unresolved.

---

## Conclusions Telemetry Must Not Make Without Additional Evidence

Do not conclude from signal metrics alone:

- interference is confirmed;
- a specific interference source exists;
- antenna failure;
- radio hardware failure;
- UE hardware failure;
- scheduler defect;
- software defect;
- handover failure;
- physical root cause.

These require additional evidence.

---

## Cross-Domain Escalation

### Request Alarm / Event Analysis When

- signal-quality impairment is confirmed but its mechanism remains unclear;
- hardware or radio processing problems remain plausible;
- quality degradation begins or clears abruptly;
- repeated degradation may align with operational events.

A useful request is:

"Determine whether radio, hardware, processing, configuration, or related alarms/events align with the confirmed signal-quality degradation."

### Request Topology Analysis When

- multiple affected entities may share radio infrastructure;
- degradation appears localized;
- a common site, radio element, or transport dependency may explain the pattern.

A useful request is:

"Determine whether the affected entities share network infrastructure that could explain the observed radio-quality pattern."

---

## When Telemetry Is Insufficient

Stop expanding telemetry analysis when the remaining hypothesis requires measurements that are unavailable.

Examples include:

- direct interference power;
- noise-floor behavior;
- downlink SINR/SNR;
- detailed RF spectrum information;
- hardware diagnostics;
- antenna-path measurements;
- configuration state;
- handover events.

Return to RCA:

- what signal-quality impairment was confirmed;
- directionality;
- associated reliability behavior;
- supported hypotheses;
- contradicted hypotheses;
- missing evidence;
- recommended next domain.

Do not replace missing evidence with proxy metrics unless the metric catalog explicitly defines that relationship.

---

## Common Investigation Mistakes

Avoid:

- treating RSRP as signal quality;
- treating SNR as signal strength;
- assuming healthy RSRP means healthy radio conditions;
- declaring interference from poor SNR;
- using UL_SNR to explain downlink quality;
- treating BLER as a signal-quality metric;
- treating MCS as a root cause;
- using correlation as proof of causation;
- declaring a physical cause when telemetry establishes only an impairment;
- repeatedly requesting unavailable SINR, RSRQ, interference, or HARQ fields;
- inventing proxy metrics for unavailable evidence.

---

## Recommended Investigation Principle

Separate three questions:

1. Is received signal strength degraded?
2. Is measured signal quality degraded?
3. Is radio reliability degraded?

Then determine how those observations relate.

Only after establishing those relationships should the investigation consider possible physical mechanisms.

Telemetry should identify the impairment accurately before RCA attempts to identify the root cause.