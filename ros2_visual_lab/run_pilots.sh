#!/usr/bin/env bash
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"
prepare_lab
label=${1:-pilot20_$(date -u +%Y%m%dT%H%M%SZ)}
if [[ $# -gt 0 ]]; then shift; fi
if [[ ! "$label" =~ ^[a-zA-Z0-9_-]+$ ]]; then
  echo 'Label must contain only letters, digits, underscores or hyphens.' >&2
  exit 2
fi
ensure_lab_image
if [[ -e "$lab_dir/artifacts/$label" ]]; then
  echo "Output already exists: $label. Use a fresh label." >&2
  exit 2
fi
mkdir -p "$lab_dir/artifacts"
docker image inspect f1tenth-ros2-visual:humble --format '{{.Id}}' > "$lab_dir/artifacts/${label}_image.txt"
docker run --rm --init --shm-size=512m \
  --user "$(id -u):$(id -g)" \
  -e ROS_LOG_DIR=/tmp/ros_logs -e XDG_CACHE_HOME=/tmp/cache \
  -e ROS_DOMAIN_ID=74 -e RMW_IMPLEMENTATION=rmw_fastrtps_cpp \
  -v "$evidence_dir:/evidence:ro" \
  -v "$lab_dir:/lab:rw" \
  f1tenth-ros2-visual:humble python3 /lab/pilot_suite.py --label "$label" "$@" \
  2>&1 | tee "$lab_dir/artifacts/${label}_console.log"
