# Proposed ROS 2/DDS extension — awaiting a frozen study design

Prepared 29 October 2026. This document proposes additional work; it does not
claim that the full study has been performed. The paper remains unchanged.

## What the sample establishes

The shared controller can run as a separate ROS 2 process and exchange
estimated state and commands through actual DDS while controlling either
native plant. RViz subscribes to the same running experiment. Same-host
Fast DDS and Cyclone DDS integrations both complete the selected circle case.
This adds middleware integration evidence to the existing in-process study.

## What stronger evidence would require

1. Introduce typed observation, command and diagnostic messages. Preserve
   source time, receive time, sequence, frame, units and command expiration.
   Publish `/clock` and define how simulation-time pauses affect wall deadlines.
2. Separate plant/measurement generation, observer/controller, monitoring and
   visualization into explicit nodes. Ground truth must remain unavailable to
   the controller and diagnostic prediction after initialization.
3. Keep the existing lockstep mode as a reproducibility reference. Add an
   asynchronous, wall-paced mode where physics continues when packets are
   late. Prespecify hold-last-command/expiry behavior. Measure scheduling
   overruns, observation age, command age, drops and deadline misses.
4. Compare an in-process baseline, separate processes in one container,
   separate containers with controlled DDS transport, and optionally two
   physical machines. Record whether transport is UDP or shared memory.
   Host-network Docker alone would not establish remote-network behavior.
5. Freeze a finite matrix before running it: backend, geometry, speed, seed,
   middleware, QoS and load. Start from the existing matched conditions; avoid
   multiplying the entire matrix before checking representative cases.
6. Include reliable versus best-effort delivery and explicitly compatible
   endpoint QoS. Test nominal operation, added application delay, packet loss,
   subscriber restart and CPU/rendering load. Label injected delay separately
   from measured middleware/application delay.
7. Report median/p95/p99/max application RTT, observation/command age,
   effective rates, completion, tracking/state errors and diagnostic counts.
   Assess the 20 ms control period and 80 ms freshness criterion using actual
   clock semantics. A sub-20 ms RTT alone does not prove an on-time loop.
8. Use visualization-off versus common-RViz versus native-rendering conditions
   to quantify observer effects. Run repeated measurements with the same
   environment and load before comparing DDS implementations.
9. Preserve raw timing and payload/sequence records, ROS bags if useful,
   middleware configs, image digest, package versions, GPU/CPU configuration
   and the exact source snapshot. Recompute outcomes independently.

For same-host measurements, a common monotonic clock permits application
timestamp comparisons. Across machines, measure and report synchronization
error before publishing one-way latency; RTT can be measured at one endpoint.

## Claim boundaries

Successful transport testing would support a statement about implemented
ROS 2/DDS interfaces and their measured behavior in the tested deployment.
It would not establish physical-model fidelity, HIL performance, real-vehicle
synchronization, comprehensive interoperability or safety. ROS 2/DDS should
become an implemented component in the article only after the corresponding
source, methods and results are ready for review and online transfer.

## Reference documentation

- ROS middleware documentation source: https://github.com/ros2/ros2_documentation/blob/humble/source/How-To-Guides/Working-with-multiple-RMW-implementations.rst
- ROS QoS documentation source: https://github.com/ros2/ros2_documentation/blob/humble/source/Concepts/Intermediate/About-Quality-of-Service-Settings.rst
- Official Docker ROS 2 guide: https://docs.docker.com/guides/ros2/

The rendered docs.ros.org pages were access-blocked during this session. The
implementation was verified locally rather than relying on those pages.
