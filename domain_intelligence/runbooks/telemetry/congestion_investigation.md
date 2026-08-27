---
domain: telemetry
topic: congestion
technology: generic
vendor: generic
version: 1.0
status: active
knowledge_type: troubleshooting_runbook
---

# Radio Resource Congestion Investigation

## Purpose

Use this runbook when an incident reports degraded performance that may be caused by radio resource congestion, capacity pressure, high load, or insufficient available radio resources.

The purpose is to determine whether the available telemetry supports:

- radio resource pressure;
- demand-driven congestion;
- uplink or downlink resource saturation;
- temporal alignment between resource pressure and service degradation;
- an alternative mechanism when radio resources are not constrained.

High resource utilization can support a congestion hypothesis, but utilization alone does not establish that congestion caused the reported service degradation.

---

## Typical Symptoms

Radio resource congestion may be relevant when an incident reports:

- degraded throughput;
- slow uploads or downloads;
- degradation during busy periods;
- degradation associated with increased traffic;
- increased uplink buffering;
- performance degradation that improves when load decreases;
- repeated degradation during periods of high resource demand.

These symptoms are not sufficient to establish congestion.

---

## First Investigation Question

Determine whether meaningful radio resource pressure exists.

Inspect directionally:

### Downlink

- PRB_Utilization_DL;
- PRBs_DL_Current;
- RX_Bytes;
- DL_NumberOfPackets;
- DL_Protocol where useful.

### Uplink

- PRB_Utilization_UL;
- PRBs_UL_Current;
- UL_NPRB;
- Estimated_UL_Buffer;
- TX_Bytes;
- UL_NumberOfPackets;
- UL_Protocol where useful.

Do not assume the uplink and downlink are equally affected.

---

## Validate Resource Utilization Semantics

Before applying numeric congestion thresholds, verify the scale and semantics of:

- PRB_Utilization_DL;
- PRB_Utilization_UL;
- PRBs_DL_Current;
- PRBs_UL_Current;
- UL_NPRB.

If the dataset does not establish whether utilization is expressed as a fraction, percentage, normalized value, or another scale, do not apply arbitrary universal thresholds.

Use relative and temporal behavior where valid, while clearly stating the limitation.

---

## Establish Resource Pressure

Do not rely only on average utilization.

Where sample-level telemetry is available, examine:

- distribution;
- persistence;
- peaks;
- proportion of high-utilization samples;
- duration of elevated utilization;
- periods of recovery;
- directional differences.

### Pattern: persistently high resource utilization

This strongly supports radio resource pressure.

It does not yet establish that resource pressure caused the reported service degradation.

### Pattern: isolated utilization spike

An isolated peak is weaker evidence of congestion.

Determine whether it aligns with the affected period and whether service behavior changes with it.

### Pattern: consistently low utilization

This strongly weakens radio resource saturation as the primary mechanism.

Do not continue attempting to prove radio congestion if the relevant radio resources are clearly underutilized.

---

## Establish Demand

Congestion should normally have evidence of resource demand.

Inspect available traffic indicators:

- TX_Bytes;
- RX_Bytes;
- UL_NumberOfPackets;
- DL_NumberOfPackets;
- Estimated_UL_Buffer;
- PRB allocation behavior.

The objective is not simply to show that traffic exists.

The objective is to determine whether increased demand aligns with increased resource pressure.

### Pattern: traffic demand rises with PRB utilization

This supports a demand-driven resource-pressure hypothesis.

### Pattern: utilization is high without corresponding observable demand

Treat this carefully.

Possible explanations may require evidence outside the current telemetry dataset, including scheduler behavior, reserved resources, measurement semantics, or network configuration.

Do not invent the mechanism.

### Pattern: traffic increases while PRB utilization remains low

Available radio resources do not appear saturated.

Radio congestion becomes less supported as the explanation for degradation.

---

## Evaluate Uplink Buffer Pressure

For uplink incidents, inspect Estimated_UL_Buffer.

### Pattern: UL buffer increases while UL resource utilization is high

This supports uplink demand exceeding or approaching available service capacity.

Strengthen the assessment by checking:

- UL packet activity;
- TX byte activity;
- UL NPRB;
- UL BLER;
- UL MCS.

### Pattern: UL buffer remains low while UL PRB utilization remains low

Uplink resource congestion becomes substantially less supported.

### Pattern: UL buffer grows while UL PRB utilization remains low

Do not immediately conclude radio congestion.

This may indicate that another mechanism is preventing efficient uplink delivery.

Investigate:

- UL BLER;
- UL SNR;
- UL MCS;
- other domain evidence.

---

## Check Reliability Before Declaring Congestion

High BLER can reduce effective radio performance even when resources are available.

Compare:

### Downlink

- PRB_Utilization_DL;
- DL_BLER;
- DL_MCS;
- RSRP.

### Uplink

- PRB_Utilization_UL;
- UL_BLER;
- UL_MCS;
- UL_SNR;
- Estimated_UL_Buffer.

### Pattern: poor performance + low PRB utilization + high BLER

This contradicts resource saturation as the primary explanation and supports investigating radio reliability.

### Pattern: poor performance + high PRB utilization + healthy BLER

Resource pressure becomes more plausible.

### Pattern: high PRB utilization + high BLER

Multiple impairments may coexist.

Do not force the incident into a single hypothesis prematurely.

Determine whether:

- resource pressure precedes or aligns with BLER;
- BLER appears only under high load;
- both independently align with degradation.

The RCA may ultimately require more than one contributing factor.

---

## Check Signal Conditions

Poor radio conditions can create degraded performance that resembles congestion.

Inspect:

- RSRP;
- UL_SNR where applicable;
- BLER;
- MCS.

### Pattern: resources are not saturated but radio quality/reliability is degraded

Radio congestion becomes less likely as the dominant mechanism.

Prioritize the radio-quality or reliability hypothesis.

### Pattern: resources are saturated while radio conditions remain comparatively stable

This strengthens resource pressure as a possible dominant driver.

---

## Establish Temporal Alignment

Congestion is much more convincing when resource pressure aligns with degraded periods.

Use sample-level timestamps where possible.

Compare:

- high-utilization periods;
- traffic-demand periods;
- buffer growth;
- BLER behavior;
- MCS behavior;
- reported degradation period.

### Strong pattern

Resource utilization increases, demand increases, buffer pressure appears, and service degradation occurs during the same periods.

### Weak pattern

Window-wide utilization is elevated but no temporal relationship with degradation is established.

Avoid converting a window-level association into a causal conclusion.

---

## Investigate Directionality

### Downlink-dominant resource pressure

Prioritize:

- PRB_Utilization_DL;
- PRBs_DL_Current;
- DL traffic activity;
- DL BLER;
- DL MCS;
- RSRP.

Determine whether downlink resource pressure aligns with downlink degradation.

### Uplink-dominant resource pressure

Prioritize:

- PRB_Utilization_UL;
- PRBs_UL_Current;
- UL_NPRB;
- Estimated_UL_Buffer;
- UL traffic activity;
- UL BLER;
- UL MCS;
- UL SNR.

Determine whether uplink demand and buffering align with resource pressure.

---

## Distinguishing Common Competing Hypotheses

### Congestion vs Radio Reliability Impairment

Congestion is strengthened by:

- sustained high resource utilization;
- corresponding demand;
- buffer pressure;
- temporal alignment with degradation.

Radio reliability impairment is strengthened by:

- elevated BLER;
- degraded signal quality;
- MCS adaptation;
- degradation despite available radio resources.

Both may coexist.

---

### Congestion vs Coverage Degradation

Coverage degradation is strengthened by:

- degraded RSRP;
- alignment between RSRP deterioration and BLER/MCS changes.

Congestion is strengthened by:

- high resource utilization;
- high demand;
- buffer pressure.

Poor performance with weak RSRP and low PRB utilization does not support radio resource congestion as the primary explanation.

---

### Congestion vs Unexplained Upstream Bottleneck

If:

- service degradation is present;
- radio utilization is not saturated;
- radio reliability appears healthy;
- demand exists;

then radio telemetry may not explain the bottleneck.

A transport, processing, application, or shared infrastructure mechanism may need investigation.

Do not label this as transport congestion without transport evidence.

---

## Traffic Counter Caution

TX_Bytes and RX_Bytes are available in the current dataset.

Do not automatically interpret them as throughput.

Before deriving throughput, confirm:

- whether values are counters or interval measurements;
- sampling interval;
- reset behavior;
- direction semantics;
- whether values represent bytes during the interval or cumulative bytes.

The same caution applies when comparing byte values across samples.

Packet counts indicate traffic activity but do not establish packet loss.

---

## Evidence That Can Be Confirmed From Telemetry

When supported by measurements, the telemetry specialist may conclude:

- whether DL or UL radio resource pressure exists;
- whether resource pressure is persistent or transient;
- whether demand increases with resource utilization;
- whether uplink buffer pressure is present;
- whether resource pressure aligns temporally with degradation;
- whether radio congestion is supported or contradicted;
- whether reliability degradation provides a stronger alternative explanation.

---

## Conclusions Telemetry Must Not Make Without Additional Evidence

Radio resource telemetry alone does not establish:

- transport congestion;
- backhaul congestion;
- scheduler software failure;
- hardware failure;
- processing bottleneck;
- application-server congestion;
- capacity planning failure;
- exact customer throughput impact when throughput cannot be derived reliably.

These may be hypotheses requiring another evidence source.

---

## Cross-Domain Escalation

### Request Topology Analysis When

- degradation affects multiple entities that may share infrastructure;
- radio resources are not saturated but a shared bottleneck remains plausible;
- a transport or processing dependency may explain the blast radius.

A useful request is:

"Determine whether the affected entities share a transport, processing, site, or other infrastructure dependency that could explain the observed degradation."

### Request Alarm / Event Analysis When

- utilization behavior appears abnormal rather than demand-driven;
- capacity, scheduler, processing, transport, or hardware problems remain plausible;
- telemetry degradation begins or clears abruptly;
- a repeated operational event may align with congestion-like symptoms.

A useful request is:

"Check for capacity, scheduler, processing, transport, hardware, or related alarms/events aligned with the affected period."

---

## When Telemetry Is Insufficient

Stop the telemetry investigation when the remaining question requires evidence unavailable from telemetry.

Examples include:

- transport-link utilization;
- scheduler internal state;
- hardware processing capacity;
- configuration limits;
- transport packet loss;
- application/server capacity;
- topology dependency relationships.

Return to RCA:

- whether radio resource pressure was confirmed;
- whether congestion was supported or contradicted;
- relevant directional evidence;
- competing hypotheses;
- missing evidence;
- recommended next domain.

Do not keep generating increasingly complex SQL to investigate a mechanism outside telemetry's observable scope.

---

## Common Investigation Mistakes

Avoid:

- declaring congestion from a high maximum utilization value;
- declaring congestion from DL versus UL utilization differences;
- using arbitrary PRB thresholds without validated scale or policy;
- ignoring traffic demand;
- ignoring buffer behavior;
- ignoring BLER and radio quality;
- assuming all poor throughput is congestion;
- interpreting TX/RX byte measurements as throughput without validated semantics;
- interpreting packet counts as packet loss;
- assuming radio congestion proves transport congestion;
- repeatedly querying telemetry after radio resource saturation has been strongly contradicted.

---

## Recommended Investigation Principle

Congestion is a relationship between demand, available capacity, resource pressure, and service impact.

Do not ask only:

"Is utilization high?"

Ask:

"Is demand creating sustained resource pressure, and does that pressure align with the observed degradation?"

If the answer is no, investigate another mechanism.