# SIH 2026 Hardware Prototype Opportunity Map

Source audited: [Official SIH 2026 Problem Statements](https://sih.gov.in/sih2026PS)  
Audit date: 5 September 2026  
Page totals observed: **233 statements = 57 Hardware + 176 Software**.

## What this screening optimizes for

The objective is not merely to find the cheapest object to build. A strong candidate should have:

1. a credible working prototype made from commonly available modules;
2. hardware that can remain stable while value improves through collected data;
3. a measurable optimization or prediction problem;
4. a safe tabletop or small-field demonstration;
5. no dependence on rare chemicals, certified laboratories, defence equipment, ships, mines, or full industrial machinery;
6. a path from prototype data to a deployable system without pretending that a student demo proves field readiness.

Indicative costs below are planning ranges, not supplier quotations. They exclude laptops, phones, tools, shipping, and team labour.

## Result

**Recommended problem statement: SIH26025 — AI-enabled low-cost real-time mine subsidence monitoring, prediction and early warning.**

Why it wins:

- The official statement explicitly permits ESP32/Raspberry Pi, low-cost tilt, vibration, displacement and crack sensors, and LoRa/Zigbee/Wi-Fi mesh.
- A four-node tabletop terrain rig can show the entire sensing-to-warning loop safely.
- The physical node is stable and reusable; differentiation lives in sensor fusion, spatial anomaly detection, warning calibration, node placement and power scheduling.
- Controlled deformation can generate labelled data without needing access to an actual mine.
- It has a more defensible hardware story than a camera attached to an existing AI application, but is much easier than sonar, explosives detection, certified electrical testing or ocean hardware.

## Shortlist

| Rank | PS | Prototype concept | Indicative prototype BOM | Data/optimization core | Main caveat |
|---:|---|---|---:|---|---|
| 1 | SIH26025 | Four-node LoRa subsidence mesh + deformable terrain bed | ₹9k–₹15k | spatial-temporal sensor fusion, early warning, node placement | field thresholds require mine data |
| 2 | SIH26008 | Tabletop conveyor with vibration/current/thermal/vision monitoring | ₹8k–₹16k | remaining-useful-life and fault classification | simulated belt defects differ from mine wear |
| 3 | SIH26172 | ESP32-S3 custom wake-word activator | ₹1.5k–₹4k | model compression, quantization, false-trigger/latency optimization | mostly embedded ML; less custom hardware |
| 4 | SIH26178 | Three modular environmental edge nodes | ₹8k–₹18k | multi-hazard anomaly detection and adaptive transmission | scope must be narrowed to one hazard first |
| 5 | SIH26232 | Rugged cold-chain logger with offline signed records | ₹3k–₹7k | sampling, battery and sync optimization | ethylene sensing/calibration can dominate cost |
| 6 | SIH26180 | Camera + soil/weather smart-farm node | ₹5k–₹12k | irrigation scheduling and multimodal crop-risk inference | crop ground truth takes time |
| 7 | SIH26179 | Edge camera for shelves and checkout queues | ₹5k–₹12k | queue forecasting, tracking and replenishment priority | hardware novelty is modest |
| 8 | SIH26022 | Sensor-controlled solar agarbatti dryer + sealer | ₹8k–₹18k | drying endpoint and energy scheduling | chamber fabrication and repeated drying trials |
| 9 | SIH26004 | Wearable IMU gait kit for OA risk screening | ₹3k–₹7k | gait-feature fusion and risk calibration | screening only; clinical claims need validation |
| 10 | SIH26109 | Udder-health sensing node for mastitis risk | ₹5k–₹12k | longitudinal risk forecasting | ethical access and labelled animal data |
| 11 | SIH26040 | Water-quality monitor controlling modular treatment stages | ₹7k–₹18k | sensor calibration and treatment selection | low-cost sensors cannot certify potability |
| 12 | SIH26048 | Load-cell-controlled smart decoction maker | ₹7k–₹15k | process-time optimization under yield constraints | chemical equivalence needs laboratory assays |

## Proposed solution: SubSense Mesh for SIH26025

### One-line pitch

A solar-ready network of low-cost surface nodes that measures relative ground deformation, learns the normal behaviour of each location, and produces a confidence-calibrated risk map before visible subsidence occurs.

### Prototype boundary

The prototype demonstrates sensing, networking, data integrity, spatial inference and warning on a controlled deformable test bed. It **does not claim** to establish mine-safe thresholds or replace geotechnical instrumentation. Field deployment would require site calibration, ruggedization and validation with mine engineers.

### Reusable node hardware

Build four identical nodes so manufacturing and software remain simple:

- ESP32 development board;
- SX1278 LoRa module and antenna;
- MPU6050-class IMU for tilt and vibration;
- waterproof DS18B20 temperature sensor for drift compensation;
- one linear displacement channel: sliding potentiometer for the first demo, then a sealed draw-wire sensor or magnetic encoder;
- crack loop or conductive break-wire input;
- microSD storage or local flash buffer;
- 18650 cell, protected holder/charger and 5 V mini solar panel;
- buzzer/status LEDs and a simple splash-resistant enclosure.

Gateway:

- ESP32 or an existing laptop-connected LoRa receiver;
- laptop-hosted dashboard for the prototype;
- optional GSM module only after the core system works.

Test bed:

- approximately 1 m × 1 m plywood frame;
- four independently adjustable surface plates or a sand/foam terrain layer;
- threaded rods, wedges or a small jack to introduce slow deformation;
- printed grid and overhead phone video as an independent reference measurement.

### Indicative BOM

| Item | Qty | Planning range |
|---|---:|---:|
| ESP32 boards | 5 | ₹1,500–₹2,500 |
| LoRa modules + antennas | 5 | ₹1,500–₹3,000 |
| IMUs | 4 | ₹400–₹800 |
| temperature sensors | 4 | ₹400–₹800 |
| prototype displacement sensors | 4 | ₹600–₹1,600 |
| battery, charging and small solar parts | 4 sets | ₹1,600–₹3,000 |
| storage, indicators, wiring and enclosures | — | ₹1,500–₹2,500 |
| deformable test-bed materials | — | ₹1,500–₹3,000 |
| **Total** |  | **about ₹9,000–₹17,000** |

The minimum demonstration can omit solar, microSD and custom enclosures and target roughly ₹7,000–₹10,000.

### Where the real optimization happens

The project should not be sold as “sensors plus an AI dashboard.” Its technical core is a constrained decision system:

1. **Drift compensation:** estimate temperature-related IMU/displacement drift during stable periods.
2. **Per-node baseline:** learn normal tilt, vibration energy and relative displacement rather than applying one universal threshold.
3. **Spatial consistency:** require neighbouring nodes to support a deformation hypothesis; isolate a bumped or faulty node.
4. **Temporal forecasting:** predict short-horizon deformation velocity and acceleration with a lightweight state-space model or gradient-boosted regressor.
5. **Risk calibration:** map model evidence to green/amber/red warnings with explicit persistence and hysteresis, reducing alert chatter.
6. **Placement optimization:** use recorded experiments to determine which node positions maximize lead time under a fixed node budget.
7. **Energy-aware sampling:** increase sample and radio rates when precursors appear; sleep aggressively in stable conditions.

Start with explainable baselines—rolling z-score, EWMA/CUSUM, linear trend and Kalman filtering—before trying an autoencoder or temporal neural network. The winning result is an improvement against those baselines, not simply the presence of deep learning.

### Data contract

Every record should contain:

`timestamp, node_id, tilt_x, tilt_y, vibration_rms, vibration_kurtosis, displacement, crack_state, temperature, battery_voltage, packet_rssi, packet_sequence`

Experiment metadata:

`run_id, deformation_location, deformation_profile, start_time, ground_truth_mm, node_positions, sampling_policy, random_seed, notes`

Generate at least these controlled scenarios:

- stable bed with temperature variation;
- isolated sensor bump/noise;
- slow monotonic settlement;
- accelerating settlement;
- localized crack between two nodes;
- broad uniform movement;
- packet loss and delayed synchronization;
- node/battery failure.

Keep train, validation and test splits separated by **entire experimental run**, not random rows, to prevent leakage.

### Evaluation gates

| Gate | Prototype target |
|---|---|
| Network reliability | ≥95% packets received in the indoor test area |
| Detectable movement | characterize empirically; target ≤2 mm on the test bed |
| Warning lead time | report median and worst case before the chosen failure point |
| Event recall | ≥90% on held-out controlled deformation runs |
| False alarms | <1 per node-hour during stable held-out runs |
| Fault isolation | identify a single disturbed/failed node without site-wide red alert |
| Power | measured energy per stable hour and per alert episode |
| Explainability | dashboard shows which sensors/nodes caused each warning |

These are design targets, not claims about real mine performance.

### Fast build plan

**Days 1–2:** assemble one wired node; log IMU, displacement and temperature.  
**Days 3–4:** clone four nodes; implement sequence-numbered LoRa packets and gateway logging.  
**Days 5–6:** construct deformable bed and independent video/reference measurement.  
**Days 7–9:** record repeatable normal and deformation runs; freeze the data schema.  
**Days 10–11:** implement baselines, spatial voting, hysteresis and calibrated risk levels.  
**Days 12–13:** dashboard, replay mode, packet-loss/fault scenarios and energy measurements.  
**Day 14:** blind held-out demo, metrics table, failure analysis and pitch video.

### Demonstration sequence

1. Show all nodes green while the bed is stable.
2. Bump one sensor: the system labels a local sensor anomaly but does not issue a site evacuation warning.
3. Introduce slow settlement beneath one region.
4. Show neighbouring displacement/tilt agreement and the risk heatmap moving green → amber → red.
5. Disconnect a node and demonstrate buffered/offline handling.
6. Replay the run, compare baseline versus fused model, and show lead time and false-alarm metrics.

### What would make this entry distinctive

- relative deformation between nodes rather than four independent threshold alarms;
- uncertainty/confidence attached to every risk level;
- explicit faulty-node detection;
- energy-aware adaptive sampling;
- a reproducible labelled deformation rig and held-out evaluation;
- a migration path from cheap potentiometers/IMUs to geotechnical-grade sensors without changing the analytics contract.

## Complete hardware-labelled inventory

Legend: **A** = prototype-friendly and data-rich; **B** = possible but validation/fabrication is harder; **C** = poor match for a quick cheap credible prototype; **Open** = broad student-innovation bucket, not a sharply specified sponsor problem.

| PS | Short title | Class | Reason |
|---|---|:---:|---|
| SIH26004 | AI-assisted OA risk-marker screening | A | cheap IMUs/phone; clinical validation limits |
| SIH26005 | Solar smart mini cold storage | B | expensive chamber/cooling and shelf-life trials |
| SIH26007 | Mine vehicles in fog | B | tabletop ADAS possible; mine validation inaccessible |
| SIH26008 | Conveyor belt rupture prediction | A | excellent tabletop rig and time-series data |
| SIH26010 | Rural agricultural land resurvey | C | RTK/DGPS/drone accuracy drives cost |
| SIH26020 | Improved hand-spinning equipment | B | fabricable, but mechanical iteration dominates data |
| SIH26022 | Solar agarbatti dryer and packager | A | affordable fabrication and controllable process |
| SIH26025 | Mine subsidence sensor mesh | **A+** | explicit cheap modules, labelled rig and rich optimization |
| SIH26026 | Narcotics/explosives detector | C | controlled substances, selectivity and certification |
| SIH26029 | High-current MCB compliance tester | C | dangerous currents and standards-lab validation |
| SIH26030 | Automated cable specimen preparation | B | custom precision mechanics and standards validation |
| SIH26039 | Underground mine rescue system | B | broad safety-critical scope and inaccessible environment |
| SIH26040 | Water purification and quality monitoring | A | buildable; cannot infer potability from cheap probes alone |
| SIH26048 | Smart standardized Kwatha maker | A | buildable process control; assay validation is harder |
| SIH26049 | Electronics for subzero/low-pressure altitude | C | environmental chamber required |
| SIH26050 | High-altitude anti-drone optimization | C | defence system and altitude validation inaccessible |
| SIH26052 | Embedded adaptive defence ANC | B | hardware cheap; realistic impulsive-noise validation difficult |
| SIH26058 | Adaptive sonar transmitter for AUV | C | underwater/acoustic transducer validation costly |
| SIH26064 | Seafloor metal-detection sensor | C | pressure, corrosion and ocean testing |
| SIH26065 | Polar ocean observation platform | C | marine survivability and deployment cost |
| SIH26087 | Cooperative AI/LMS/ERP ecosystem | C | appears mislabelled; essentially software |
| SIH26088 | Governance/legal chatbot | C | hardware label does not match software problem |
| SIH26096 | Digital heritage archive | C | hardware label does not match core deliverable |
| SIH26098 | Artillery precision guidance/fuze | C | weapon component; unsafe and unsuitable |
| SIH26109 | Bovine mastitis forecasting | A | cheap sensing; labelled animal data is the bottleneck |
| SIH26110 | Lightweight milk chilling can | B | thermal fabrication dominates optimization |
| SIH26112 | Modular autonomous warehouse robot | B | common prototype, but cost/mechanics rise quickly |
| SIH26113 | Human augmentation technology | B | broad; narrow assistive device could be buildable |
| SIH26118 | Passive H2S dosimeter wristband | B | clever, but H2S chemistry/exposure testing is hazardous |
| SIH26144 | High-sensitivity microbarometer | B | custom analog/mechanical design and calibration |
| SIH26172 | Low-latency edge voice activator | A | very cheap and strongly measurable TinyML problem |
| SIH26177 | Autonomous search-and-rescue drone | B | expensive crowded space; flight testing and safety |
| SIH26178 | Edge environmental sensor network | A | modular, reusable, data-rich; must narrow hazard scope |
| SIH26179 | Edge retail intelligence | A | fast camera prototype; hardware novelty limited |
| SIH26180 | Edge smart-farming assistant | A | common sensors/camera; biological ground truth is slower |
| SIH26181 | Private personal health companion | B | accessible sensors, but medical validation/privacy burden |
| SIH26185 | Helmet conformal tactical antenna | C | RF fabrication, VNA/anechoic testing and defence context |
| SIH26210 | Student innovation: agriculture | Open | viable if converted into a narrow measurable problem |
| SIH26211 | Student innovation: blockchain | Open | category is broad and hardware link is weak |
| SIH26212 | Student innovation: waste/sanitation | Open | promising but requires a newly formulated problem |
| SIH26213 | Student innovation: fitness | Open | cheap wearables possible; problem is unspecified |
| SIH26214 | Student innovation: heritage | Open | problem and hardware need formulation |
| SIH26215 | Student innovation: health technology | Open | broad; validation burden depends on chosen claim |
| SIH26216 | Student innovation: tertiary sectors | Open | too broad for direct scoring |
| SIH26217 | Student innovation: renewable energy | Open | many prototype paths; no sponsor-specific requirement |
| SIH26218 | Student innovation: drones/robots | Open | buildable, but crowded and mechanically intensive |
| SIH26219 | Student innovation: smart automation | Open | broad; must define user, setting and metric |
| SIH26220 | Student innovation: transportation devices | Open | broad; safety scope can escalate quickly |
| SIH26221 | Student innovation: tourism | Open | hardware need is unclear |
| SIH26222 | Student innovation: smart cities/logistics | Open | broad; could reuse sensor network platform |
| SIH26223 | Student innovation: disaster management | Open | good sensor-network fit after narrowing one hazard |
| SIH26224 | Student innovation: smart education | Open | typically software-first |
| SIH26225 | Student innovation: toys and games | Open | fast hardware possible but optimization story must be created |
| SIH26226 | Student innovation: space technology | Open | credible validation may be difficult |
| SIH26230 | Breath-based drug-consumption detector | C | selectivity, controlled substances and clinical/legal validation |
| SIH26232 | Low-cost IoT blockchain traceability node | A | standard sensors, offline integrity and energy optimization |
| SIH26233 | Inline microbial detection using hyperspectral edge sensors | C | hyperspectral hardware and microbial ground truth are costly |

## Reusable hardware platform across multiple shortlisted statements

About half of the A-class ideas can share one base platform:

`ESP32-S3 + microSD + battery/solar power + LoRa/Wi-Fi + modular I2C/ADC sensor ports + signed timestamped packets`

Only the sensor head changes:

- subsidence: IMU + displacement/crack channel;
- environmental monitoring: water-level/soil-moisture/gas/weather channel;
- agriculture: soil probes + camera;
- cold-chain traceability: temperature/humidity/ethylene channel;
- conveyor: accelerometer + current transformer + microphone/thermal channel.

This is useful internally for rapid prototyping, but the submission should be framed around **one** problem statement and its measured outcomes—not as a generic IoT box.

## Final recommendation

Proceed with **SIH26025 / SubSense Mesh** unless the team already has unusually strong TinyML audio experience, in which case SIH26172 is the fastest low-budget alternative. Order only one-node parts first, validate signal quality and LoRa transport, and then duplicate the node. Freeze the data schema before model work so sensor logs, simulations, baselines and dashboard all use the same contract.
