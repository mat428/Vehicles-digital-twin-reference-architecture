#!/usr/bin/env bash
# Shared setup for the Git checkout. Historical campaign sources are unchanged.
prepare_lab() {
  lab_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
  project_dir=$(dirname -- "$lab_dir")
  evidence_dir=${EVIDENCE_DIR:-"$project_dir/Vehicle_Control_SIL_Data_Code"}
  if [[ ! -d "$evidence_dir" ]]; then
    echo "Set EVIDENCE_DIR to the extracted primary reviewer package (see docs/ros2_dds/README.md)." >&2
    return 2
  fi
  evidence_dir=$(cd -- "$evidence_dir" && pwd)
  local required
  for required in src/run.py src/plants.py configs/protocol.json \
    vendor/f1tenth_gym/gym/f110_gym/envs/base_classes.py \
    vendor/metadrive/metadrive/__init__.py \
    results/f1tenth/monitor_model.json results/metadrive/monitor_model.json; do
    if [[ ! -f "$evidence_dir/$required" ]]; then
      echo "Incomplete EVIDENCE_DIR: missing $required in $evidence_dir" >&2
      return 2
    fi
  done
  mkdir -p "$lab_dir/artifacts"
}

ensure_lab_image() {
  if ! docker image inspect f1tenth-ros2-visual:humble >/dev/null 2>&1; then
    docker build -t f1tenth-ros2-visual:humble "$lab_dir"
  fi
}
