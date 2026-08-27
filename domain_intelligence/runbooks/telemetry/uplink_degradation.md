---
domain: telemetry
topic: uplink_degradation
technology: generic
vendor: generic
version: 1.0
status: active
knowledge_type: troubleshooting_runbook
---

# Uplink Degradation Investigation

## Purpose

Use this runbook when an incident indicates degraded uplink performance, upload problems, uplink reliability issues, increased uplink delay, or telemetry showing abnormal uplink behavior.

The investigation should determine whether the dominant measured mechanism is associated with:

- uplink radio reliability;
- uplink signal quality;
- link adaptation;
- uplink resource pressure;
- uplink buffer pressure;
- traffic behavior;
- a mechanism outside the available telemetry.

Do not assume an uplink incident is caused by interference, congestion, or poor coverage before discriminating between these hypotheses.

---

## Current Dataset Capability

The current telemetry dataset provides the following uplink-relevant measurements:

### Reliability

- UL_BLER

### Signal quality

- UL_SNR

### Signal strength context

- RSRP

### Link adaptation

- UL_MCS

### Resource behavior

- PRB_Utilization_UL
- PRBs_UL_Current
- UL_NPRB

### Buffer behavior

- Estimated_UL_Buffer

### Traffic context

- TX_Bytes
- UL_NumberOfPackets
- UL_Protocol

Downlink measurements can also be used as a directional comparison:

- DL_BLER
- DL_MCS
- PRB_Utilization_DL
- RX_Bytes
- DL_NumberOfPackets

---

## First Investigation Question

Establish whether the impairment is actually uplink-dominant.

Compare at minimum:

- UL_BLER versus DL_BLER;
- UL resource behavior versus DL resource behavior;
- relevant traffic behavior;
- reported incident direction.

### Pattern: UL clearly worse than DL

Prioritize uplink-specific mechanisms.

### Pattern: UL and DL both degraded

Do not force an uplink-only hypothesis.

A shared radio, resource, infrastructure, or other mechanism may be relevant.

### Pattern: DL is materially worse than UL

Reconsider whether uplink degradation is actually the dominant telemetry impairment.

---

## Step 1: Evaluate Uplink Reliability

Inspect UL_BLER.

Do not rely only on average or maximum values.

Where sample-level data is available, determine:

- distribution;
- persistence;
- frequency of elevated values;
- peaks;
- temporal pattern;
- periods of recovery.

### Pattern: UL BLER materially elevated

This supports an uplink radio reliability impairment.

It does not establish why the uplink blocks are failing.

### Pattern: UL BLER remains healthy

Radio block reliability becomes less supported as the dominant measured explanation.

Continue with:

- resource pressure;
- buffer behavior;
- traffic behavior;
- other mechanisms.

---

## Step 2: Evaluate Uplink Signal Quality

Inspect UL_SNR.

Compare:

- UL_SNR versus UL_BLER;
- UL_SNR versus UL_MCS;
- UL_SNR during degraded and recovered periods.

### Pattern: UL SNR degrades while UL BLER increases

This strongly supports an uplink signal-quality-related contribution to the reliability impairment.

### Pattern: UL SNR degrades while UL MCS decreases

This supports link adaptation responding to poorer uplink radio conditions.

### Pattern: UL SNR remains healthy while UL BLER is elevated

The available signal-quality evidence does not explain the reliability impairment.

Do not continue attempting to prove poor signal quality from the same metric.

Investigate other hypotheses.

---

## Step 3: Compare Signal Strength and Signal Quality

Use RSRP as signal-strength context.

Do not treat RSRP and UL_SNR as equivalent.

### Poor RSRP + poor UL SNR

This supports generally degraded radio conditions and may strengthen a coverage-related explanation.

Check whether:

- UL BLER increases;
- UL MCS changes;
- the behavior aligns temporally.

### Healthy RSRP + poor UL SNR

Weak received signal strength becomes less supported as the primary explanation.

An uplink signal-quality impairment may still exist.

Possible interference or other RF mechanisms may remain hypotheses, but are not confirmed.

### Poor RSRP + healthy UL SNR

Weak received signal strength is observed, but the available uplink signal-quality metric does not show corresponding degradation.

Determine whether UL BLER or UL MCS is materially affected before attributing the incident to coverage.

### Healthy RSRP + healthy UL SNR

The available signal metrics do not provide a strong explanation for uplink degradation.

Continue with reliability, resources, buffering, and other-domain evidence.

---

## Step 4: Evaluate Uplink Link Adaptation

Inspect UL_MCS together with:

- UL_BLER;
- UL_SNR;
- RSRP.

### Pattern: UL MCS decreases as UL SNR deteriorates

This is consistent with link adaptation responding to poorer conditions.

### Pattern: UL BLER remains elevated despite MCS reduction

The uplink reliability impairment persists despite adaptation.

This may justify deeper investigation but does not establish a scheduler or software defect.

### Pattern: UL MCS remains stable while UL BLER changes substantially

MCS behavior may not explain the changing impairment.

Avoid forcing a link-adaptation explanation.

---

## Step 5: Evaluate Uplink Resource Pressure

Inspect:

- PRB_Utilization_UL;
- PRBs_UL_Current;
- UL_NPRB.

Where semantics permit, determine:

- absolute utilization;
- distribution;
- persistence;
- peaks;
- temporal relationship with degradation.

### Pattern: persistently high UL resource utilization

This supports uplink radio resource pressure.

Strengthen the congestion hypothesis by checking:

- traffic demand;
- buffer pressure;
- temporal alignment with degradation.

### Pattern: consistently low UL resource utilization

Radio resource saturation becomes substantially less supported.

Do not label the incident uplink congestion simply because uplink performance is poor.

### Pattern: high utilization only during isolated samples

Determine whether those samples align with the affected period before treating them as material evidence.

---

## Step 6: Evaluate Uplink Buffer Pressure

Inspect Estimated_UL_Buffer.

### Pattern: buffer increases + UL resource utilization increases

This supports demand-driven uplink resource pressure.

### Pattern: buffer increases + UL BLER increases

Poor uplink reliability may be reducing effective delivery and contributing to backlog.

Inspect:

- UL_SNR;
- UL_MCS;
- resource utilization.

### Pattern: buffer increases while UL resources remain underutilized

Simple radio resource saturation does not explain the backlog.

Investigate:

- reliability impairment;
- signal quality;
- link adaptation;
- other-domain mechanisms.

### Pattern: buffer remains low throughout degradation

Buffer pressure becomes less supported as the dominant measured mechanism.

---

## Step 7: Evaluate Traffic Context

Use:

- TX_Bytes;
- UL_NumberOfPackets;
- UL_Protocol where relevant.

Determine whether traffic demand changes during the affected period.

Do not automatically interpret TX_Bytes as throughput.

Do not interpret UL_NumberOfPackets as packet loss.

Traffic evidence should answer:

"Was there meaningful uplink demand during the observed degradation?"

rather than:

"What exact throughput did the user receive?"

unless the measurement semantics allow that calculation.

---

## High-Value Diagnostic Combinations

### Pattern A: High UL BLER + Poor UL SNR + Lower UL MCS

Supports:

- uplink signal-quality impairment;
- uplink reliability impairment;
- corresponding link-adaptation response.

Does not prove:

- interference;
- interference source;
- hardware failure.

---

### Pattern B: High UL BLER + Healthy RSRP + Poor UL SNR

Supports:

- uplink reliability impairment;
- uplink signal-quality degradation;
- weak received signal strength is less supported as the primary explanation.

Possible RF-quality mechanisms remain open.

Do not declare interference confirmed.

---

### Pattern C: High UL BLER + Healthy UL SNR + Low Resource Utilization

Supports:

- uplink reliability impairment.

Contradicts or weakens:

- measured signal-quality degradation as the explanation;
- radio resource congestion.

The physical mechanism may not be observable in the current telemetry.

Consider cross-domain escalation.

---

### Pattern D: Healthy UL BLER + High UL PRB + Growing UL Buffer

Supports:

- uplink resource pressure;
- possible demand-driven congestion.

Radio reliability impairment becomes less supported as the dominant mechanism.

---

### Pattern E: High UL PRB + Growing Buffer + High UL BLER

Multiple contributing mechanisms may coexist:

- resource pressure;
- reliability impairment.

Determine whether:

- BLER worsens only during high load;
- buffer pressure follows BLER;
- signal quality also changes;
- one mechanism clearly precedes another.

Do not force a single-cause conclusion without evidence.

---

### Pattern F: Low UL PRB + Growing Buffer + High UL BLER

Simple resource saturation is contradicted.

Poor radio reliability may be preventing efficient uplink delivery.

Investigate:

- UL_SNR;
- UL_MCS;
- temporal alignment.

---

### Pattern G: Low UL PRB + Healthy UL BLER + Healthy UL SNR

Available radio telemetry provides little support for a radio-layer explanation.

If uplink degradation remains established, escalate rather than repeatedly querying healthy radio metrics.

---

## Investigate Intermittent Uplink Degradation

If the incident reports intermittent uploads, stalls, or periodic recovery:

1. identify affected periods using timestamps or sample order;
2. compare UL_BLER between degraded and recovered periods;
3. compare UL_SNR;
4. compare UL_MCS;
5. compare UL resource utilization;
6. compare Estimated_UL_Buffer;
7. compare traffic activity.

Look for a repeatable sequence.

For example:

UL_SNR deteriorates
→ UL_BLER increases
→ UL_MCS changes
→ UL buffer grows
→ degradation occurs
→ metrics recover

Such a sequence can provide stronger diagnostic evidence than window-level averages.

Do not infer the causal direction automatically.

---

## Correlation Analysis

Useful exploratory relationships include:

- UL_SNR versus UL_BLER;
- UL_SNR versus UL_MCS;
- UL_BLER versus UL_MCS;
- UL_BLER versus Estimated_UL_Buffer;
- UL resource utilization versus buffer;
- RSRP versus UL_BLER.

Correlation can identify relationships worth investigating.

It should not be used as the sole basis for root-cause determination.

A weak global correlation does not rule out:

- threshold effects;
- intermittent relationships;
- time-localized relationships;
- nonlinear relationships;
- multiple operating regimes.

Prefer temporal comparison when the incident is intermittent.

---

## Interference Hypothesis

Interference is a plausible mechanism for some uplink signal-quality impairments.

However, the current telemetry dataset does not contain:

- explicit interference power;
- noise-floor detail sufficient to identify a source;
- spectrum information;
- interferer identity.

A pattern such as:

- healthy RSRP;
- degraded UL_SNR;
- elevated UL_BLER;
- reduced UL_MCS;

may justify keeping interference among the remaining hypotheses.

It does not confirm interference.

A suitable telemetry conclusion is:

"Uplink signal-quality and reliability degradation are confirmed and are not explained by weak received signal strength alone. The underlying RF mechanism remains unresolved."

---

## Coverage Hypothesis

Coverage becomes more plausible when:

- RSRP is degraded;
- poor RSRP persists;
- UL SNR also degrades;
- UL BLER increases;
- UL MCS changes;
- these behaviors align temporally.

Coverage becomes less supported when:

- RSRP remains strong and stable throughout the affected period.

Healthy RSRP does not rule out other uplink radio impairments.

---

## Congestion Hypothesis

Uplink congestion becomes more plausible when:

- UL resource utilization is persistently high;
- traffic demand is present;
- Estimated_UL_Buffer grows;
- degradation aligns with resource pressure.

Congestion becomes less supported when:

- UL resource utilization remains low;
- buffer pressure is absent;
- reliability or signal-quality degradation provides a stronger explanation.

Do not use relative UL-versus-DL utilization alone to establish congestion.

---

## Evidence That Can Be Confirmed From Telemetry

When supported by measurements, the telemetry specialist may conclude:

- the incident is uplink-dominant;
- uplink reliability impairment exists;
- uplink signal-quality degradation exists;
- received signal strength is degraded or healthy;
- link-adaptation behavior changes;
- uplink resource pressure exists or is contradicted;
- uplink buffer pressure exists or is contradicted;
- measured variables align temporally;
- available radio telemetry does or does not sufficiently explain the uplink degradation.

---

## Conclusions Telemetry Must Not Make Without Additional Evidence

Do not conclude from current telemetry alone:

- interference is confirmed;
- a specific interferer exists;
- UE transmitter failure;
- antenna failure;
- radio-unit hardware failure;
- scheduler defect;
- software defect;
- transport congestion;
- backhaul failure;
- packet loss;
- handover failure;
- exact physical root cause.

---

## Cross-Domain Escalation

### Request Alarm / Event Analysis When

- uplink impairment is confirmed but its mechanism remains unresolved;
- hardware, processing, scheduler, transport, or configuration issues remain plausible;
- degradation starts or clears abruptly;
- intermittent telemetry may align with recurring operational events.

A useful request is:

"Check for radio, hardware, processing, scheduler, transport, configuration, or related alarms/events aligned with the confirmed uplink degradation."

### Request Topology Analysis When

- multiple affected entities may share infrastructure;
- a site, radio, processing, or transport dependency may explain the impact;
- radio telemetry does not fully explain the blast radius.

A useful request is:

"Determine whether affected entities share radio, site, processing, or transport dependencies relevant to the uplink degradation."

---

## When Telemetry Is Insufficient

Stop expanding telemetry queries when the remaining hypothesis requires unavailable evidence.

Examples include:

- direct interference measurements;
- spectrum analysis;
- HARQ reason information;
- retransmission cause detail;
- UE hardware diagnostics;
- radio hardware diagnostics;
- scheduler internals;
- transport performance;
- topology relationships;
- detailed configuration state.

Return to RCA:

- confirmed uplink impairment;
- strongest supported mechanism;
- materially contradicted hypotheses;
- unresolved hypotheses;
- missing evidence;
- recommended next domain.

Do not keep requesting increasingly complex telemetry analysis when the discriminating evidence belongs to another domain.

---

## Common Investigation Mistakes

Avoid:

- assuming every uplink problem is interference;
- assuming every uplink slowdown is congestion;
- using RSRP as a substitute for UL_SNR;
- treating healthy RSRP as proof of healthy uplink quality;
- treating UL BLER as packet loss;
- treating MCS as root cause;
- interpreting TX_Bytes as throughput without validated semantics;
- interpreting packet count as packet loss;
- ignoring Estimated_UL_Buffer;
- ignoring DL telemetry when determining directionality;
- using global correlation to dismiss intermittent relationships;
- repeatedly querying evidence already shown to be healthy;
- requesting metrics that do not exist in the schema.

---

## Recommended Investigation Principle

For uplink degradation, reason through the evidence in this order:

1. Is the impairment actually uplink-dominant?
2. Is uplink reliability degraded?
3. Is uplink signal quality degraded?
4. Does signal strength explain the quality impairment?
5. Is link adaptation responding?
6. Are uplink resources constrained?
7. Is uplink buffer pressure present?
8. Does traffic demand support the resource hypothesis?
9. What remains unexplained?
10. Which domain owns the missing evidence?

The objective is not to prove a preferred hypothesis.

The objective is to eliminate explanations efficiently until the strongest evidence-supported mechanism remains.