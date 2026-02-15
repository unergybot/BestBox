#!/bin/bash
# GPU Backend Detection for BestBox
# Priority: env var > .bestbox/config > auto-detect

validate_backend() {
  case "$1" in
    cuda|rocm|cpu)
      return 0
      ;;
    *)
      echo "Error: Invalid GPU backend '$1'. Must be: cuda, rocm, or cpu" >&2
      return 1
      ;;
  esac
}

_read_config_backend() {
  local script_dir config_file value
  script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
  config_file="$script_dir/.bestbox/config"

  if [ -f "$config_file" ]; then
    value=$(sed -nE 's/^[[:space:]]*gpu_backend[[:space:]]*=[[:space:]]*([^#[:space:]]+).*/\1/p' "$config_file" | head -1)
    if [ -n "$value" ]; then
      echo "$value"
      return 0
    fi
  fi

  return 1
}

detect_gpu() {
  local configured

  if [ -n "${BESTBOX_GPU_BACKEND:-}" ]; then
    validate_backend "$BESTBOX_GPU_BACKEND" || return 1
    echo "$BESTBOX_GPU_BACKEND"
    return 0
  fi

  if configured=$(_read_config_backend); then
    validate_backend "$configured" || return 1
    echo "$configured"
    return 0
  fi

  if command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi >/dev/null 2>&1; then
    echo "cuda"
  elif command -v rocm-smi >/dev/null 2>&1 || command -v rocminfo >/dev/null 2>&1; then
    echo "rocm"
  else
    echo "cpu"
  fi
}

export -f validate_backend detect_gpu
