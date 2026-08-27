TelecomTS KPI & Alarm Rule Reference

Purpose: Human-readable engineering reference to support a synthetic alarm
generator for a 4G/5G RAN incident-investigation AI system built on the
TelecomTS dataset.

Scope of alarms: Every alarm defined here reports an observation
("metric X crossed threshold Y for duration Z"). None of them assert a root
cause. Root cause is left to a downstream correlation/investigation layer
that combines alarms, topology, config changes, logs and historical
incidents.

Sampling context: TelecomTS samples KPIs at ~10 Hz, in windows of 128
samples (~12.8 s). This means:

A single sample is ~100 ms of radio-layer behaviour — inherently noisy
(fast fading, scheduling granularity, instantaneous retransmission
bursts).

A full window (~12.8 s) is a reasonable minimum unit for alarm
evaluation on fast-moving radio KPIs, and several consecutive windows are
more appropriate for congestion/traffic-type KPIs that are naturally
bursty.

All persistence values below are expressed in seconds and are also
expressed as an approximate sample count at 10 Hz for convenience.

Threshold provenance legend (used throughout):

STANDARD — defined or strongly implied by 3GPP/ETSI/ITU specifications,
or a value in near-universal vendor agreement (e.g. RSRP reporting
range).

VENDOR_OPERATOR — no single 3GPP number exists; this is a commonly used
range across major vendor (Ericsson, Nokia, Huawei) OMC/PM documentation
and operator engineering guidelines, cited as such. Real deployments tune
this per band/vendor/clutter type.

SIMULATION — no standardized or common industry number exists at all;
this is a reasonable, justified, and configurable value chosen for
synthetic alarm generation only. It should be treated as a YAML default,
not an engineering fact.

V1 Local Generator Compatibility Note

The current local TelecomTS pipeline profiles the source values before alarm evaluation. For V1, DL_BLER and UL_BLER are normalized by multiplying source values by 100 before comparing them with percentage thresholds in alarm_rules.yaml. PRB_Utilization_DL and PRB_Utilization_UL are already represented on a 0–100 percentage scale; RSRP, UL_SNR and MCS values are used without scaling.

The current TelecomTS records are isolated ~12.8-second windows. Therefore the V1 alarm generator executes only rules whose persistence and required history fit inside one window. Baseline-deviation rules, 30–60 second persistence rules, and composite rules requiring a rolling baseline remain in the YAML but are deliberately skipped until continuous per-cell timelines are introduced. This avoids manufacturing history that the source dataset does not actually contain.

1. KPI Reference

1.1 RSRP

Field

Value

Full name

Reference Signal Received Power

Domain

Radio quality

Plain language

How strong the signal from the serving cell is at the device, measured on the reference signal only (not noise/interference). It's the basic "how far / how obstructed" indicator.

Unit

dBm

Reporting range

−140 dBm to −44 dBm, 1 dB resolution (LTE, 3GPP TS 36.133); NR SS-RSRP range is −156 to −31 dBm (3GPP TS 38.133). STANDARD

Healthy

> −95 dBm (LTE) — commonly cited "good to excellent" band, close-in cells can be −75 dBm or better. VENDOR_OPERATOR

Warning

−95 to −110 dBm — usable but degraded. VENDOR_OPERATOR

Critical

< −110 dBm — cell-edge / poor coverage; below roughly −115 to −120 dBm service is commonly unreliable. VENDOR_OPERATOR

Direction of degradation

LOW_BAD

Absolute vs. baseline

Absolute thresholds are meaningful (physical dBm scale, standardized reporting range), but a per-cell/per-UE baseline deviation check is a useful secondary signal (e.g. sudden 10+ dB drop from a UE's own recent average may indicate a local event even if still "healthy" in absolute terms).

Persistence

Fast fading causes multi-dB swings sample-to-sample. Recommend averaging/filtering over ≥1 s (≈10 samples) before threshold comparison, and requiring the averaged value to remain below threshold for ≥5–10 s (≈50–100 samples) before alarming, mirroring 3GPP time-to-trigger (TTT) concepts used in handover events A1–A5 (TTT commonly configured 40 ms–5 s at the RRC layer; RAN OSS fault alarms are typically slower/coarser than RRC mobility events).

Related KPIs

UL_SNR, DL_BLER, DL_MCS, PRB_Utilization_DL

Symptoms when abnormal

Increased BLER, MCS downshift, throughput drop, possible dropped/failed connections.

Possible causes (documentation only)

Distance from site, physical obstruction/clutter, antenna/feeder fault, mistilt, power amplifier degradation, neighboring cell interference. Not to be used as an automatic alarm root cause.

Cross-KPI patterns

Low RSRP + high DL_BLER + low DL_MCS → classic coverage-quality signature. Low RSRP + healthy BLER/MCS is possible under strong interference cancellation or during idle-mode reporting; not proof of a coverage problem by itself.

1.2 DL_BLER

Field

Value

Full name

Downlink Block Error Rate

Domain

Radio quality / link adaptation

Plain language

The fraction of downlink data blocks the device could not decode correctly (before or after HARQ retransmissions). Higher = more data is being lost/retransmitted.

Unit

% (0–100)

Design reference

3GPP link-adaptation design commonly targets ~10% initial (first-transmission) BLER as the operating point at which the outer-loop link adaptation algorithm holds the MCS; residual BLER after HARQ combining is designed to be much lower (often quoted around 1% or less in vendor literature). This 10% figure is a widely used VENDOR_OPERATOR design convention, not a hard 3GPP fault threshold.

Healthy

< 10%

Warning

10–15%

Critical

> 15–20% sustained

(All three bands)

VENDOR_OPERATOR, consistent with the ~10% link-adaptation operating point above

Direction of degradation

HIGH_BAD

Absolute vs. baseline

Absolute threshold is meaningful and is the industry-standard framing (it's literally how link adaptation defines its target operating point), but per-cell baseline deviation is valuable to catch cells that run unusually clean and start drifting.

Persistence

BLER is measured over a block of scheduled transmissions and is naturally bursty at 100 ms granularity (a cell with low PRB usage may show 0% or 100% BLER in a single 100 ms sample just from small-number statistics). Recommend evaluating over a rolling window of ≥5 s (≈50 samples) with a minimum sample/transmission count, not a single sample.

Related KPIs

RSRP, UL_SNR, DL_MCS, PRB_Utilization_DL

Symptoms when abnormal

MCS downshift, throughput drop, retransmission-driven latency increase.

Possible causes (documentation only)

Poor coverage, interference, fast fading beyond link-adaptation tracking speed, hardware fault, misconfigured link adaptation. Not an automatic alarm root cause.

Cross-KPI patterns

High DL_BLER + poor RSRP → likely coverage/radio-quality issue. High DL_BLER + healthy RSRP + healthy PRB utilization → points away from simple coverage and toward interference or a link-adaptation/hardware issue; must not be auto-labeled.

1.3 DL_MCS

Field

Value

Full name

Downlink Modulation and Coding Scheme (index)

Domain

Scheduler / link adaptation

Plain language

A number chosen by the network each scheduling interval that says how "aggressively" data is packed onto the radio (higher = more bits per symbol = faster, but needs a cleaner channel). It rises and falls automatically as conditions change.

Unit

Index (unitless), LTE: 0–28 (3GPP TS 36.213 Table 7.1.7.1-1/1A); NR similarly uses MCS index tables 0–27/0–28 depending on modulation table (3GPP TS 38.214). STANDARD for the index range itself.

Healthy

Sustained in the upper third of the vendor's configured table for the current bandwidth/modulation scheme, while PRBs are actually being scheduled — context dependent, see below.

Warning

Sustained low-band MCS (roughly bottom third of table) while the UE has traffic and adequate PRB allocation.

Critical

Persistently at or near the lowest MCS indices (QPSK, low code rate) with traffic present.

(Bands)

SIMULATION — there is no universal "bad MCS number"; it is entirely relative to the active modulation table, bandwidth, and vendor scheduler policy.

Direction of degradation

CONTEXT_DEPENDENT (a low MCS is only meaningful in the context of whether the device had data to send and PRBs to use — during idle/near-idle periods MCS is not a meaningful quality signal at all).

Absolute vs. baseline

Baseline/deviation detection is strongly preferred over an absolute threshold.

Persistence

Because MCS is a per-TTI scheduler decision, treat single samples as noise. Recommend a rolling average over ≥1–2 s with a persistence requirement of ≥5 s before alarming, and gate the check on PRBs_DL_Current > 0 (don't alarm on low MCS during idle).

Related KPIs

RSRP, DL_BLER, UL_SNR, PRB_Utilization_DL

Symptoms when abnormal

Reduced DL throughput at a given PRB allocation.

Possible causes (documentation only)

Poor radio conditions, interference, conservative outer-loop link adaptation after BLER events. Not an automatic alarm root cause.

Cross-KPI patterns

Low DL_MCS + low RSRP + high DL_BLER, all sustained together, is a much stronger radio-quality signal than any one metric alone.

1.4 UL_BLER

Field

Value

Full name

Uplink Block Error Rate

Domain

Radio quality / link adaptation

Plain language

Same idea as DL_BLER but for data the device sends to the network.

Unit

% (0–100)

Reference

Same ~10% initial-BLER link-adaptation convention as DL, VENDOR_OPERATOR, since uplink power control and link adaptation target a similar operating point (3GPP TS 36.213 / 38.213 describe the mechanism; the numeric target is operator/vendor tuned).

Healthy / Warning / Critical

Same bands as DL_BLER: <10% / 10–15% / >15–20% sustained. VENDOR_OPERATOR

Direction of degradation

HIGH_BAD

Absolute vs. baseline

Same as DL_BLER: absolute is meaningful, baseline deviation is a useful secondary check.

Persistence

Same as DL_BLER — rolling window ≥5 s, minimum transmission count.

Related KPIs

UL_SNR, UL_MCS, UL_NPRB, PRB_Utilization_UL

Symptoms when abnormal

UL MCS downshift, degraded UL throughput, longer transport-layer retransmissions.

Possible causes (documentation only)

Uplink coverage limitation (UL is typically the limiting link at cell edge due to device power constraints), interference, power control misconfiguration, device hardware issue. Not an automatic alarm root cause.

Cross-KPI patterns

High UL_BLER + low UL_SNR → classic uplink coverage/quality issue. High UL_BLER + healthy UL_SNR → suggests interference or a scheduling/power-control anomaly rather than pure coverage.

1.5 UL_MCS

Field

Value

Full name

Uplink Modulation and Coding Scheme (index)

Domain

Scheduler / link adaptation

Plain language

Same as DL_MCS, but for the uplink direction.

Unit

Index (unitless); range per 3GPP TS 36.213/38.214 uplink MCS tables. STANDARD for index range.

Healthy/Warning/Critical

Same context-dependent treatment as DL_MCS. SIMULATION

Direction of degradation

CONTEXT_DEPENDENT

Absolute vs. baseline

Baseline/deviation preferred, gated on UL_NPRB > 0.

Persistence

Same as DL_MCS: rolling average ≥1–2 s, persistence ≥5 s, gated on active UL scheduling.

Related KPIs

UL_SNR, UL_BLER, UL_NPRB, PRB_Utilization_UL

Symptoms when abnormal

Reduced UL throughput at a given PRB allocation.

Possible causes (documentation only)

Poor UL radio conditions, device power limitation, interference. Not an automatic alarm root cause.

Cross-KPI patterns

Low UL_MCS + low UL_SNR + high UL_BLER together is a stronger uplink-quality signal than any single metric.

1.6 UL_NPRB

Field

Value

Full name

Number of Physical Resource Blocks scheduled on the uplink (per TTI/observation)

Domain

Radio resource / scheduler

Plain language

How much of the uplink "radio spectrum pie" was actually handed to this device/cell at a given moment.

Unit

Count (PRBs); max depends on channel bandwidth (e.g. 100 PRBs at 20 MHz LTE, up to 273 PRBs for 100 MHz NR numerology-dependent). STANDARD for the max-PRB-per-bandwidth mapping (3GPP TS 36.101/38.101).

Healthy/Warning/Critical

Not inherently good/bad in isolation — it is a resource-allocation quantity, not a quality metric. Used primarily as context for interpreting UL_BLER/UL_MCS and for congestion analysis together with PRB_Utilization_UL.

Direction of degradation

CONTEXT_DEPENDENT

Absolute vs. baseline

Baseline/deviation only makes sense against expected traffic demand; not a standalone alarm metric. Primarily used as a gating/denominator signal for other rules.

Persistence

N/A as a standalone alarm; relevant at the same granularity as the KPI it is gating (e.g. UL_BLER, UL_MCS checks).

Related KPIs

PRB_Utilization_UL, UL_BLER, UL_MCS, Estimated_UL_Buffer

Symptoms when abnormal

Not directly alarmed; low UL_NPRB despite a large Estimated_UL_Buffer is a resource-starvation symptom (see composite rules).

Possible causes (documentation only)

Cell congestion, scheduler prioritization, insufficient granted resources. Not an automatic alarm root cause.

Cross-KPI patterns

Falling UL_NPRB while Estimated_UL_Buffer grows → possible uplink congestion/starvation (see composite alarm).

1.7 UL_SNR

Field

Value

Full name

Uplink Signal-to-Noise Ratio (as reported/estimated at the receiver, e.g. eNB/gNB)

Domain

Radio quality

Plain language

How clean the uplink signal is relative to background noise — a core input to how aggressively the network can schedule modulation/coding on the uplink.

Unit

dB

Note on standardization

SINR/SNR reporting is not defined by a single 3GPP formula/range the way RSRP is; it is vendor/chipset specific in its exact computation. A commonly cited practical range (e.g. for the analogous DL SNR/RSSNR metric surfaced to applications) runs roughly −20 dB (worst) to +30 dB (best). VENDOR_OPERATOR

Healthy

> 20 dB

Warning

0–20 dB

Critical

< 0 dB

(Bands)

VENDOR_OPERATOR, consistent with typical LTE/NR link-budget engineering guidance where positive double-digit SNR supports high-order modulation and near-0-or-negative SNR is cell-edge/marginal.

Direction of degradation

LOW_BAD

Absolute vs. baseline

Absolute thresholds are reasonable given the wide, well-understood practical range; baseline deviation is a good secondary check per-cell since noise floor varies by site/equipment.

Persistence

Same fast-fading concern as RSRP: average over ≥1 s, require persistence ≥5–10 s.

Related KPIs

UL_BLER, UL_MCS, RSRP, UL_NPRB

Symptoms when abnormal

UL_BLER increase, UL_MCS downshift, uplink throughput drop.

Possible causes (documentation only)

Uplink interference (including inter-cell or external), device transmit power limitation, uplink coverage limit. Not an automatic alarm root cause.

Cross-KPI patterns

Low UL_SNR + high UL_BLER + low UL_MCS is a coherent uplink-degradation signature. Low UL_SNR with otherwise healthy uplink KPIs may just reflect a low-traffic period and should not alarm alone (see persistence/gating).

1.8 TX_Bytes / 1.9 RX_Bytes

Field

Value

Full name

Transmitted Bytes / Received Bytes (per observation interval)

Domain

Traffic / throughput

Plain language

How much data actually moved in each direction during the interval — the "how much stuff happened" counters.

Unit

Bytes (per sample interval; can be converted to a rate, e.g. bytes/sec or bps)

Counter behavior

These are counter-type KPIs (monotonic accumulation reset per reporting interval or free-running counter), not gauges. Any threshold logic must diff/rate-convert rather than compare raw cumulative values, and must handle counter resets/wraps.

Healthy/Warning/Critical

No universal absolute threshold exists — "normal" bytes/sec depends entirely on subscriber count, service mix, time of day, and cell capacity. SIMULATION/baseline-only.

Direction of degradation

LOW_BAD, but only relative to expected/baseline demand — a low value during genuinely low-demand periods is normal, not an anomaly.

Absolute vs. baseline

Baseline/deviation detection is strongly recommended (see Section 3 below) over any absolute threshold.

Persistence

Traffic KPIs are naturally bursty at 100 ms; use a rolling window of tens of seconds (e.g. 30–60 s) for baseline comparison to smooth burstiness, and require the deviation to persist across the full window rather than a single interval.

Related KPIs

RX_Bytes/TX_Bytes (each other), UL/DL_NumberOfPackets, PRB_Utilization_UL/DL, Estimated_UL_Buffer

Symptoms when abnormal

Sudden drop → possible outage/backhaul/congestion issue upstream of what BLER/MCS would show. Sudden spike → possible traffic surge, DDoS-like pattern, or misconfiguration (not to be labeled as such automatically).

Possible causes (documentation only)

Backhaul failure, congestion, radio-link failure, scheduled maintenance, genuine demand change. Not an automatic alarm root cause.

Cross-KPI patterns

RX_Bytes drop + healthy RSRP/BLER/MCS → points away from radio-layer cause, toward core/backhaul/application layer. RX_Bytes drop + degraded RSRP/BLER → consistent with radio-layer cause but still not proof.

1.10 Estimated_UL_Buffer

Field

Value

Full name

Estimated Uplink Buffer (occupancy), analogous to a Buffer Status Report (BSR) estimate

Domain

Scheduler / queue

Plain language

An estimate of how much data the device still has waiting to send uplink that hasn't been transmitted yet — a backlog gauge.

Unit

Bytes (or configured unit in TelecomTS export)

Standardization

The mechanism (Buffer Status Reporting) is standardized in 3GPP TS 36.321/38.321, but the specific numeric "this is a large backlog" threshold is not standardized — it depends on device class, QoS profile, and scheduler design. VENDOR_OPERATOR for the concept, SIMULATION for numeric thresholds.

Healthy

Near zero / rapidly draining relative to UL_NPRB granted.

Warning

Sustained growth over the evaluation window despite available UL_NPRB.

Critical

Large and monotonically growing while UL_NPRB stays flat or falls — backlog is not being served.

Direction of degradation

HIGH_BAD (specifically, growing and not draining)

Absolute vs. baseline

Baseline/rate-of-change detection preferred over a single absolute byte threshold, since "large" is relative to device/service/QoS class.

Persistence

Evaluate the trend over ≥5–10 s rather than an instantaneous value, since buffers naturally fluctuate with normal traffic bursts.

Related KPIs

UL_NPRB, PRB_Utilization_UL, UL_BLER, TX_Bytes

Symptoms when abnormal

Increased uplink latency, eventual throughput impact, possible packet drops upstream.

Possible causes (documentation only)

Uplink congestion, scheduler starvation, radio-quality degradation reducing effective throughput. Not an automatic alarm root cause.

Cross-KPI patterns

Growing Estimated_UL_Buffer + flat/low UL_NPRB + high PRB_Utilization_UL → resource congestion/starvation signature (see composite alarm). Growing buffer + healthy UL_NPRB/UL_MCS → may indicate the device itself is generating unusually high uplink demand rather than a network-side problem.

1.11 PRBs_DL_Current / 1.12 PRBs_UL_Current

Field

Value

Full name

Currently Allocated Physical Resource Blocks, Downlink / Uplink

Domain

Radio resource / scheduler

Plain language

The raw count of resource blocks assigned to this device/cell right now, in each direction.

Unit

Count (PRBs); max depends on bandwidth (see UL_NPRB entry; 3GPP TS 36.101/38.101). STANDARD for the max-per-bandwidth mapping.

Healthy/Warning/Critical

Not a quality metric by itself — used as denominator context (with PRB_Utilization_DL/UL) and as a gate for MCS/BLER checks (don't alarm on low MCS if no PRBs are even scheduled).

Direction of degradation

CONTEXT_DEPENDENT

Absolute vs. baseline

Not alarmed directly; feeds PRB_Utilization_DL/UL and gating logic.

Persistence

N/A standalone.

Related KPIs

PRB_Utilization_DL/UL, DL/UL_MCS, DL/UL_BLER

Symptoms when abnormal

N/A standalone (see composite congestion rule).

Possible causes (documentation only)

N/A standalone.

Cross-KPI patterns

See PRB_Utilization_DL/UL below.

1.13 PRB_Utilization_DL / 1.14 PRB_Utilization_UL

Field

Value

Full name

Physical Resource Block Utilization, Downlink / Uplink

Domain

Radio resource / congestion

Plain language

What percentage of the cell's total available radio capacity (in resource blocks) is currently in use. The classic "how full is the cell" gauge.

Unit

% (0–100), typically PRBs_..._Current / max-PRBs-for-bandwidth

Healthy

< 70%

Warning

70–90%

Critical

> 90% sustained

(Bands)

VENDOR_OPERATOR — widely used capacity-management rule-of-thumb bands in RAN engineering/OSS dashboards (exact cutovers vary by vendor and by whether the operator uses 80/90 or 70/85/95 style bands); no single 3GPP number defines "congested."

Direction of degradation

HIGH_BAD, but only meaningfully "bad" in combination with a throughput/BLER symptom — high utilization with healthy per-user throughput is just "busy," not "congested." This is why the primary congestion alarm in this reference is a composite rule (Section 2, Composite Alarms), not a standalone PRB_Utilization threshold.

Absolute vs. baseline

Absolute % thresholds are meaningful (it's already a normalized ratio), but should be paired with a throughput-impact condition rather than used alone for a "congestion" alarm.

Persistence

Recommend ≥30–60 s sustained high utilization before considering it a capacity concern, since brief bursts to high utilization are normal scheduler behavior.

Related KPIs

PRBs_DL/UL_Current, DL/UL_MCS, DL/UL_BLER, RX/TX_Bytes, Estimated_UL_Buffer

Symptoms when abnormal

Reduced per-user throughput, growing buffers, scheduling delay.

Possible causes (documentation only)

Genuine high demand, insufficient cell capacity, neighbor cell offload failure, traffic imbalance. Not an automatic alarm root cause.

Cross-KPI patterns

High PRB_Utilization + falling RX/TX_Bytes rate (throughput) per active user → congestion signature. High PRB_Utilization + stable/healthy throughput → likely just high legitimate load, not a fault.

1.15 UL_Protocol / 1.16 DL_Protocol

Field

Value

Full name

Uplink / Downlink Protocol (observed transport/application-layer protocol classification)

Domain

Protocol

Plain language

What kind of traffic protocol is being carried (e.g. TCP/UDP/application-layer classification), per direction.

Unit

Categorical (string/enum)

Healthy/Warning/Critical

Not applicable in the threshold sense — this is a categorical field, not a numeric gauge.

Direction of degradation

N/A (categorical)

Absolute vs. baseline

Change-detection is the only meaningful approach: compare the observed protocol-mix distribution over a window against a rolling baseline distribution. A large, sudden shift (e.g. dominant protocol changes, or a new protocol appears at high volume) is the kind of event worth surfacing — as an informational/anomaly note, not a fault alarm, since protocol-mix shifts are frequently legitimate (new app usage, OS update, etc.).

Persistence

Evaluate over a window long enough to be statistically meaningful (e.g. ≥60 s / many packets), not a single 100 ms sample.

Related KPIs

UL/DL_NumberOfPackets, TX/RX_Bytes

Symptoms when abnormal

N/A directly — used as investigative context, not as a primary alarm source.

Possible causes (documentation only)

Legitimate usage change, misclassification, or (in rare cases) anomalous traffic pattern. Not an automatic alarm root cause; this reference intentionally does not define a "protocol anomaly = security event" alarm, since that inference requires far more context than this KPI alone provides.

Cross-KPI patterns

Used only as corroborating context for other alarms (e.g. a traffic-volume anomaly co-occurring with a protocol-mix shift is more interesting than either alone).

1.17 UL_NumberOfPackets / 1.18 DL_NumberOfPackets

Field

Value

Full name

Number of Packets, Uplink / Downlink (per observation interval)

Domain

Traffic

Plain language

How many discrete packets moved in each direction — a packet-count companion to the byte-count KPIs.

Unit

Count (per interval)

Counter behavior

Counter-type, same handling as TX/RX_Bytes (rate/diff, handle resets).

Healthy/Warning/Critical

No universal absolute threshold — same reasoning as TX/RX_Bytes. SIMULATION/baseline-only.

Direction of degradation

LOW_BAD relative to baseline demand (a drop against expected traffic is the signal, not an absolute count).

Absolute vs. baseline

Baseline/deviation detection recommended, same approach as TX/RX_Bytes.

Persistence

Same rolling-window (30–60 s) approach as byte counters, to smooth burstiness.

Related KPIs

TX/RX_Bytes, UL/DL_Protocol

Symptoms when abnormal

Same as byte-count anomalies; also useful to distinguish "fewer, larger packets" vs "fewer packets, similar size" patterns when combined with byte counters (average packet size), which can hint at whether it's a volume drop or a protocol/behavior change — again, context only, not a conclusion.

Possible causes (documentation only)

Same as TX/RX_Bytes. Not an automatic alarm root cause.

Cross-KPI patterns

Falling packet count with stable byte count (or vice versa) → average-packet-size shift, useful investigative context but not alarmed directly in this reference.

2. Alarm Definitions (Single-KPI, Threshold-Based)

All alarms below are OBSERVATION alarms: they report that a metric crossed a
configured threshold for a configured duration. They do not assert why.

alarm_code

alarm_name

source_system

component_type

severity

metric

condition

threshold

persistence

clear_condition

description

RAN-RSRP-LOW-WARN

Low RSRP (Warning)

RAN_PM

CELL

WARNING

RSRP

LESS_THAN

−95 dBm

10 s

RSRP > −93 dBm for 10 s

Reference Signal Received Power dropped below the configured warning threshold.

RAN-RSRP-LOW-CRIT

Low RSRP (Critical)

RAN_PM

CELL

CRITICAL

RSRP

LESS_THAN

−110 dBm

10 s

RSRP > −108 dBm for 10 s

Reference Signal Received Power dropped below the configured critical threshold.

RAN-DL-BLER-HIGH

High Downlink Block Error Rate

RAN_PM

CELL

MAJOR

DL_BLER

GREATER_THAN

15 %

5 s

DL_BLER < 12 % for 5 s

Downlink block error rate remained above the configured threshold.

RAN-UL-BLER-HIGH

High Uplink Block Error Rate

RAN_PM

CELL

MAJOR

UL_BLER

GREATER_THAN

15 %

5 s

UL_BLER < 12 % for 5 s

Uplink block error rate remained above the configured threshold.

RAN-UL-SNR-LOW-WARN

Low Uplink SNR (Warning)

RAN_PM

CELL

WARNING

UL_SNR

LESS_THAN

5 dB

10 s

UL_SNR > 7 dB for 10 s

Uplink signal-to-noise ratio dropped below the configured warning threshold.

RAN-UL-SNR-LOW-CRIT

Low Uplink SNR (Critical)

RAN_PM

CELL

CRITICAL

UL_SNR

LESS_THAN

0 dB

10 s

UL_SNR > 2 dB for 10 s

Uplink signal-to-noise ratio dropped below the configured critical threshold.

RAN-DL-MCS-LOW

Sustained Low Downlink MCS

RAN_PM

CELL

MINOR

DL_MCS

LESS_THAN

index 6 (of scheduler table)

5 s (gated on PRBs_DL_Current > 0)

DL_MCS ≥ 8 for 5 s

Downlink MCS index remained persistently low while resources were actively scheduled.

RAN-UL-MCS-LOW

Sustained Low Uplink MCS

RAN_PM

CELL

MINOR

UL_MCS

LESS_THAN

index 6 (of scheduler table)

5 s (gated on UL_NPRB > 0)

UL_MCS ≥ 8 for 5 s

Uplink MCS index remained persistently low while resources were actively scheduled.

RAN-PRB-UTIL-DL-HIGH

High Downlink PRB Utilization

RAN_PM

CELL

WARNING

PRB_Utilization_DL

GREATER_THAN

90 %

60 s

PRB_Utilization_DL < 80 % for 60 s

Downlink PRB utilization remained above the configured congestion-watch threshold. (Observational only — see composite congestion alarm for a load-plus-impact rule.)

RAN-PRB-UTIL-UL-HIGH

High Uplink PRB Utilization

RAN_PM

CELL

WARNING

PRB_Utilization_UL

GREATER_THAN

90 %

60 s

PRB_Utilization_UL < 80 % for 60 s

Uplink PRB utilization remained above the configured congestion-watch threshold. (Observational only.)

RAN-UL-BUFFER-GROWTH

Growing Uplink Buffer Backlog

RAN_PM

CELL/UE

MINOR

Estimated_UL_Buffer

PERCENT_ABOVE_BASELINE

100 % above rolling baseline

10 s

Estimated_UL_Buffer < 30 % above baseline for 10 s

Estimated uplink buffer occupancy grew substantially above its recent baseline and did not drain.

RAN-RX-BYTES-DROP

RX Throughput Drop vs Baseline

RAN_PM

CELL

MAJOR

RX_Bytes

PERCENT_BELOW_BASELINE

50 % below rolling baseline

30 s

RX_Bytes < 20 % below baseline for 30 s

Received byte rate dropped substantially below its recent rolling baseline.

RAN-TX-BYTES-DROP

TX Throughput Drop vs Baseline

RAN_PM

CELL

MAJOR

TX_Bytes

PERCENT_BELOW_BASELINE

50 % below rolling baseline

30 s

TX_Bytes < 20 % below baseline for 30 s

Transmitted byte rate dropped substantially below its recent rolling baseline.

RAN-DL-PACKETS-DROP

DL Packet Count Drop vs Baseline

RAN_PM

CELL

MINOR

DL_NumberOfPackets

PERCENT_BELOW_BASELINE

50 % below rolling baseline

30 s

DL_NumberOfPackets < 20 % below baseline for 30 s

Downlink packet count dropped substantially below its recent rolling baseline.

RAN-UL-PACKETS-DROP

UL Packet Count Drop vs Baseline

RAN_PM

CELL

MINOR

UL_NumberOfPackets

PERCENT_BELOW_BASELINE

50 % below rolling baseline

30 s

UL_NumberOfPackets < 20 % below baseline for 30 s

Uplink packet count dropped substantially below its recent rolling baseline.

Notes:

All threshold values above marked implicitly VENDOR_OPERATOR/SIMULATION
per the KPI table in Section 1; none are asserted as universal 3GPP fault
thresholds.

RAN-DL-MCS-LOW / RAN-UL-MCS-LOW use a SIMULATION default index
(6) since no universal "bad MCS number" exists (Section 1.3/1.5); this
must be reviewed against whichever MCS table the simulator assumes
(64QAM vs 256QAM tables shift the meaningful range).

MCS-based alarms are only meaningful when gated on active scheduling
(PRBs_DL_Current / UL_NPRB > 0); this gating is expressed in
alarm_rules.yaml via minimum_samples plus an upstream data-quality
filter recommendation (Section 5), since the YAML schema in this
reference does not support arbitrary boolean gating expressions beyond
composite AND logic — so gating is implemented as a composite rule
(see RAN_DL_MCS_LOW_GATED in Section 2 composite equivalents, or
simply pre-filter idle samples before evaluation in the Python
generator, which is documented but out of scope for the YAML file
itself).

3. Composite / Multi-KPI Alarms

These require more than one condition to be true, evaluated over the same
window, and are intentionally more conservative than single-KPI alarms
since they combine evidence rather than asserting a diagnosis.

3.1 Degraded Radio Quality (Downlink)

required_metrics: RSRP, DL_BLER

conditions: RSRP < −105 dBm AND DL_BLER > 12%

persistence: 10 s, both conditions true concurrently

severity: MAJOR

alarm output: RAN-DL-RADIO-QUALITY-DEGRADED — "Downlink radio
quality degraded: low received power coincides with elevated block error
rate." (Reports co-occurrence only; does not claim RSRP caused the BLER.)

3.2 Degraded Radio Quality (Uplink)

required_metrics: UL_SNR, UL_BLER

conditions: UL_SNR < 5 dB AND UL_BLER > 12%

persistence: 10 s

severity: MAJOR

alarm output: RAN-UL-RADIO-QUALITY-DEGRADED — "Uplink radio quality
degraded: low signal-to-noise ratio coincides with elevated block error
rate."

3.3 Downlink Resource Congestion

required_metrics: PRB_Utilization_DL, RX_Bytes (baseline)

conditions: PRB_Utilization_DL > 90% AND RX_Bytes < 70% of rolling
baseline (i.e., high load but falling delivered throughput)

persistence: 30 s

severity: MAJOR

alarm output: RAN-DL-CONGESTION — "Downlink PRB utilization is high
while delivered downlink throughput is falling relative to baseline,
consistent with resource congestion." (Explicitly framed as
"consistent with," not "caused by.")

3.4 Uplink Resource Congestion / Starvation

required_metrics: Estimated_UL_Buffer, UL_NPRB

conditions: Estimated_UL_Buffer growing (> 100% above its own rolling
baseline) AND UL_NPRB flat-or-falling over the same window (not
increasing to serve the backlog)

persistence: 10 s

severity: MAJOR

alarm output: RAN-UL-CONGESTION-STARVATION — "Uplink buffer backlog
is growing while granted uplink resource blocks are not increasing to
serve it, consistent with uplink congestion or scheduling starvation."

3.5 Traffic Degradation (Bidirectional)

required_metrics: TX_Bytes, RX_Bytes

conditions: RX_Bytes < 50% of rolling baseline AND TX_Bytes < 50% of
rolling baseline, concurrently

persistence: 30 s

severity: CRITICAL

alarm output: RAN-TRAFFIC-DEGRADATION-BOTH-DIRECTIONS — "Both
uplink and downlink traffic volume dropped substantially below baseline
concurrently, a stronger signal of a service-affecting event than either
direction alone."

3.6 Coverage-Consistent vs. Non-Coverage-Consistent BLER (documentation-only distinction)

This is not a single alarm but a note on how to interpret two already-fired
alarms together, useful for the downstream investigator:

RAN-DL-BLER-HIGH and RAN-RSRP-LOW-* both active → "coverage-consistent"
pattern (Section 3.1 formalizes this as its own composite alarm).

RAN-DL-BLER-HIGH active without any RSRP alarm and with
PRB_Utilization_DL in the healthy band → "non-coverage-consistent"
pattern; worth flagging for the investigator as an open question
(possible interference, hardware, or link-adaptation misconfiguration)
but no alarm is generated for this negative/absence condition in
this reference, since alarming on the absence of another alarm is
fragile and better handled by the downstream correlation layer, not the
alarm generator.

4. Baseline / Anomaly Rules

KPIs without a meaningful universal absolute threshold — TX_Bytes,
RX_Bytes, UL_NumberOfPackets, DL_NumberOfPackets, Estimated_UL_Buffer —
use baseline-relative detection instead of fixed thresholds.

Recommended approach: rolling-window percentage deviation from a trailing
baseline, specifically:

baseline = rolling mean (or median) of the metric over a trailing window
           (recommended: 5–15 minutes of prior data, sampled/aggregated to
           1 Hz or coarser to smooth 10 Hz noise)
current  = short rolling mean over the evaluation window (recommended:
           30–60 s)
deviation_percent = (current - baseline) / baseline * 100

Why this over the alternatives:

Percent-change from rolling baseline (chosen approach): simple,
interpretable, robust to the wide legitimate range of traffic levels
across different cells/times of day, and easy to express in the
restricted YAML operator vocabulary (percent_above_baseline,
percent_below_baseline).

Z-score: statistically principled but requires a stable variance
estimate; traffic KPIs are heavy-tailed and bursty at 10 Hz, so the
variance estimate itself is noisy unless computed on a coarser
aggregation. Reasonable as a future enhancement on top of a coarser
(e.g. 1-minute-bucketed) series, but not recommended as the primary
method given the counter/burst nature of these KPIs.

Percentile-based (e.g. below 5th percentile of trailing distribution):
robust to outliers and skew, a good alternative to percent-of-mean, but
requires maintaining a distribution rather than a single baseline value,
which is more implementation overhead for comparable benefit in a
synthetic-generation context.

Recommendation: use rolling-mean percent-deviation as the default
(as reflected in alarm_rules.yaml's baseline_deviation evaluation
type), with percentile-based detection documented here as a viable
upgrade path if the synthetic data later shows the mean-based approach is
too sensitive to outlier bursts.

Baseline windows must handle:

Counter resets/wraps (TX_Bytes, RX_Bytes, UL/DL_NumberOfPackets are
counter-type): always diff/rate-convert before baselining; a
reset should be detected (current cumulative < previous cumulative) and
treated as a gap, not a legitimate drop to zero.

Missing samples: if the evaluation window has fewer than
minimum_samples valid points (see defaults in alarm_rules.yaml), the
rule should not fire — insufficient data, not evidence of anomaly.

Cold-start: a cell/UE with less than one full baseline window of
history should not generate baseline-deviation alarms until the baseline
window is populated.

5. Realism, Noise, and Alarm-Lifecycle Requirements

Noisy measurements / transient spikes: every threshold-type rule in
alarm_rules.yaml carries a persistence_seconds and minimum_samples
requirement; a single 100 ms sample should never fire an alarm on its
own outside of the rare cases noted in Section 1 (none identified among
these 18 KPIs — all warrant persistence).

Hysteresis: every alarm has a distinct clear_condition that is not
simply "no longer above threshold" but a meaningfully separated
clear-threshold with its own persistence, to avoid chatter/flapping when
a metric hovers near the trigger point.

Duplicate suppression: default 60 s minimum gap between repeated
firings of the same rule_id against the same entity (cell/UE), see
defaults.duplicate_suppression_seconds in alarm_rules.yaml.

Severity escalation: modeled as separate rules at different
severities on the same metric (e.g. RAN-RSRP-LOW-WARN and
RAN-RSRP-LOW-CRIT) rather than a single rule with dynamic severity,
to keep the YAML schema simple and deterministic; the generator should
suppress the WARNING-level alarm's "new" event while CRITICAL is active
on the same entity/metric (standard escalation behavior), which is a
generator-side dedup rule documented here rather than expressed in YAML.

Baseline-relative thresholds: see Section 4.

Missing samples: rules should require minimum_samples valid
(non-null) observations within the evaluation window before evaluating;
a window with too many gaps should be skipped, not treated as
passing or failing.

Counter-type vs. gauge-type KPIs: counter-type (TX_Bytes, RX_Bytes,
UL/DL_NumberOfPackets) must be diffed/rate-converted before any
threshold or baseline comparison; all other KPIs in this dataset are
gauge-type (instantaneous value, safe to compare directly).

Correlated KPIs: composite rules (Section 3) exist specifically to
capture the most operationally meaningful correlations without
overreaching into root-cause claims; the Section 1 "Cross-KPI patterns"
fields document further correlations for the downstream investigator
that are not wired into composite alarms, to avoid an explosion of
low-value composite rules.

Operator/vendor-specific thresholds: everywhere a threshold is
marked VENDOR_OPERATOR or SIMULATION in Section 1, the corresponding
YAML rule carries metadata.threshold_type and
metadata.explanation so the values are clearly not presented as
universal engineering fact.

6. Rules Intentionally Left Out of alarm_rules.yaml

Per the requirement that the YAML be free of natural-language conditions
requiring LLM interpretation, the following are documented here only:

UL_Protocol / DL_Protocol distribution-shift detection (Section
1.15/1.16): requires comparing categorical distributions
(e.g. a divergence measure between two distributions), which is outside
the threshold / baseline_deviation / composite numeric-operator
schema. Recommended for a future distribution_shift evaluation type
once the schema is extended; the Python generator can implement this
directly against the schema's metadata fields as a documented
extension rather than forcing it into the current YAML vocabulary.

MCS gating on "traffic present" (Section 2 note under
RAN-DL-MCS-LOW / RAN-UL-MCS-LOW): expressed as a composite rule in
the YAML (metric-greater-than-zero AND MCS-less-than-threshold) rather
than a boolean gate, to stay within the explicit operator vocabulary.

7. References

Standards and vendor/engineering sources used to ground definitions and
threshold provenance in this document:

3GPP TS 36.133 — E-UTRA Requirements for support of radio resource
management (RSRP/RSRQ reporting range and measurement definitions).

3GPP TS 38.133 — NR Requirements for support of radio resource
management (NR SS-RSRP/CSI-RSRP reporting range).

3GPP TS 36.211 / 38.211 — Physical channels and modulation (reference
signal structure underlying RSRP).

3GPP TS 36.213 / 38.213, 36.214 / 38.214 — Physical layer procedures
(MCS index tables, link adaptation and HARQ procedures underlying the
BLER operating-point convention).

3GPP TS 36.321 / 38.321 — MAC protocol specification (Buffer Status
Reporting mechanism underlying Estimated_UL_Buffer).

3GPP TS 36.101 / 38.101 — UE radio transmission and reception (channel
bandwidth to max-PRB mapping).

3GPP TS 36.331 / 38.331 — RRC protocol specification (RSRP-Range
encoding, measurement-event time-to-trigger concept referenced for
persistence justification).

ETSI (as 3GPP's publishing partner in Europe) — same specification
series as above; ETSI does not define separate numeric RAN fault
thresholds beyond the 3GPP specs it publishes.

ITU-T/ITU-R — general mobile network performance and QoS framework
references (e.g. ITU-T Y-series/E-series QoS frameworks); ITU does not
define RAN-internal PM fault thresholds either, consistent with this
document's treatment of PRB utilization and BLER "fault" bands as
vendor/operator conventions rather than ITU-standardized values.

General vendor OMC/PM engineering guidance patterns (Ericsson, Nokia,
Huawei RAN performance-management documentation styles) — used only to
justify the shape and typical range of VENDOR_OPERATOR bands
(e.g. RSRP good/fair/poor bands, PRB utilization congestion-watch
bands, ~10% BLER link-adaptation operating point); no single vendor's
proprietary numeric threshold is presented here as a specification —
all such values are explicitly marked VENDOR_OPERATOR or
SIMULATION and are meant to be reviewed/tuned before any
production-adjacent use.

Peer-reviewed / arXiv literature on LTE/NR signal metrics (e.g. surveys
covering RSRP/RSRQ/RSSNR practical ranges as surfaced to
applications) — used to corroborate practical SNR range framing.

Explicit disclaimer: Any threshold in this document not marked
STANDARD should be treated as a starting point for simulation, not as an
authoritative fault threshold for a real network. Real deployments tune
these per band, vendor, clutter type, and operator policy.