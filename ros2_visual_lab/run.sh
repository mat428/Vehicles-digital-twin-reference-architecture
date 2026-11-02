#!/usr/bin/env bash
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"
prepare_lab
ensure_lab_image
options=(--rm --init --shm-size=512m
  --user "$(id -u):$(id -g)"
  -e NVIDIA_DRIVER_CAPABILITIES=graphics,utility,compute
  -e ROS_LOG_DIR=/tmp/ros_logs -e XDG_CACHE_HOME=/tmp/cache
  -e ROS_DOMAIN_ID=73 -e RMW_IMPLEMENTATION="${RMW_IMPLEMENTATION:-rmw_fastrtps_cpp}"
  -v "$evidence_dir:/evidence:ro"
  -v "$lab_dir:/lab:rw")
if [[ " $* " == *" --visual "* || " $* " == *" --rviz "* || " $* " == *" --native-render "* ]]; then
  options+=(--gpus all -e DISPLAY="${DISPLAY:-:1}" -e XAUTHORITY=/tmp/lab.xauth
    -v /tmp/.X11-unix:/tmp/.X11-unix:ro
    -v "${XAUTHORITY:-/run/user/$(id -u)/gdm/Xauthority}:/tmp/lab.xauth:ro")
fi
exec docker run "${options[@]}" f1tenth-ros2-visual:humble python3 /lab/launch.py "$@"
