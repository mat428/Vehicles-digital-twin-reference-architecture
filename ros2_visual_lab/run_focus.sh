#!/usr/bin/env bash
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"
prepare_lab
label=${1:-focus_$(date -u +%Y%m%dT%H%M%SZ)}
if [[ $# -gt 0 ]]; then shift; fi
[[ "$label" =~ ^[a-zA-Z0-9_-]+$ ]] || { echo 'Invalid label' >&2; exit 2; }
[[ ! -e "$lab_dir/artifacts/$label" ]] || { echo 'Use a fresh output label' >&2; exit 2; }
ensure_lab_image
docker image inspect f1tenth-ros2-visual:humble --format '{{.Id}}' > "$lab_dir/artifacts/${label}_image.txt"
docker run --rm --init --shm-size=512m --user "$(id -u):$(id -g)" \
  -e ROS_LOG_DIR=/tmp/ros_logs -e XDG_CACHE_HOME=/tmp/cache \
  -e ROS_DOMAIN_ID=75 -e RMW_IMPLEMENTATION=rmw_fastrtps_cpp \
  -v "$evidence_dir:/evidence:ro" -v "$lab_dir:/lab:rw" \
  f1tenth-ros2-visual:humble python3 /lab/focus_suite.py --label "$label" "$@" \
  2>&1 | tee "$lab_dir/artifacts/${label}_console.log"
