#!/bin/bash

# Kubernetes pod logs tailer for Stadium RF Simulation
# Usage:
#   ./k8s_logs.sh start            # start tailing default pods
#   ./k8s_logs.sh stop             # stop all tailers started by this script
#   ./k8s_logs.sh status           # show status of tailers
#   ./k8s_logs.sh start ns:prefix  # optionally add more targets (repeatable)

set -euo pipefail

LOG_ROOT_DIR="logs"
LOG_DIR="${LOG_ROOT_DIR}/k8s"
PID_FILE="k8s-logs.pid"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info() { echo -e "${GREEN}[INFO]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
err()  { echo -e "${RED}[ERROR]${NC} $1"; }

need_kubectl() {
  if ! command -v kubectl >/dev/null 2>&1; then
    err "kubectl not found in PATH"
    return 1
  fi
}

# Default targets (namespace:pod-name-prefix)
DEFAULT_TARGETS=(
  "ricrapp:energy-saver-rapp"
  "ricxapp:ricxapp-bouncer-xapp"
  "ricxapp:ricxapp-debugger-xapp"
  "ricplt:e2sim-e2sim-helm"
)

resolve_pod() {
  local ns="$1"; shift
  local prefix="$1"; shift
  kubectl get pods -n "$ns" -o jsonpath='{range .items[*]}{.metadata.name}{"\n"}{end}' 2>/dev/null | grep -E "^${prefix}(-|$)" | head -1 || true
}

start_tail() {
  local ns="$1"; shift
  local pod="$1"; shift
  local since_time
  # RFC3339 UTC timestamp to start from now
  since_time=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

  mkdir -p "$LOG_DIR"
  local logfile="${LOG_DIR}/${ns}_${pod}_${TIMESTAMP}.log"
  info "Tailing logs: ns=${ns} pod=${pod} -> ${logfile}"
  # shellcheck disable=SC2086
  nohup bash -c "kubectl logs -n ${ns} ${pod} -f --timestamps --since-time='${since_time}' >> '${logfile}' 2>&1" >/dev/null 2>&1 &
  local pid=$!
  echo "${pid}|${ns}|${pod}|${logfile}" >> "$PID_FILE"
}

start_all() {
  need_kubectl || return 1

  if [[ -f "$PID_FILE" ]]; then
    # Check if any PIDs are alive
    local alive=false
    while IFS='|' read -r pid _; do
      if [[ -n "${pid}" ]] && kill -0 "${pid}" 2>/dev/null; then
        alive=true; break
      fi
    done < <(cat "$PID_FILE" 2>/dev/null || true)
    if [[ "$alive" == true ]]; then
      warn "k8s logs already being tailed (see ${PID_FILE}); skipping start"
      return 0
    else
      warn "Found stale ${PID_FILE}; removing"
      rm -f "$PID_FILE"
    fi
  fi

  mkdir -p "$LOG_DIR"

  local targets=("${DEFAULT_TARGETS[@]}")
  # Append extra ns:prefix arguments
  if [[ $# -gt 0 ]]; then
    targets+=("$@")
  fi

  local started=0
  for t in "${targets[@]}"; do
    local ns="${t%%:*}"
    local prefix="${t#*:}"
    local pod
    pod=$(resolve_pod "$ns" "$prefix") || true
    if [[ -z "$pod" ]]; then
      warn "No pod matching prefix '${prefix}' in namespace '${ns}'"
      continue
    fi
    start_tail "$ns" "$pod" || warn "Failed to start tail for ${ns}/${pod}"
    started=$((started+1))
  done

  if [[ $started -eq 0 ]]; then
    err "No matching pods found to tail"
    return 1
  fi

  info "Started tailers for ${started} pod(s). PID map written to ${PID_FILE}"
  info "Logs directory: ${LOG_DIR}"
}

stop_all() {
  if [[ ! -f "$PID_FILE" ]]; then
    warn "No PID file found (${PID_FILE}); nothing to stop"
    return 0
  fi

  local stopped=0
  local remain=()
  while IFS= read -r line; do
    [[ -z "${line:-}" ]] && continue
    local pid ns pod file
    if [[ "$line" == *"|"* ]]; then
      IFS='|' read -r pid ns pod file <<< "$line"
    else
      pid="$line"; ns=""; pod=""; file=""
    fi
    if kill -0 "$pid" 2>/dev/null; then
  local id_display
  if [[ -n "$ns$pod" ]]; then id_display="${ns}/${pod}"; else id_display="unknown"; fi
      info "Stopping tailer PID=${pid} (${id_display})"
      kill -TERM "$pid" 2>/dev/null || true
      sleep 1
      if kill -0 "$pid" 2>/dev/null; then
        warn "Force killing PID=${pid}"
        kill -9 "$pid" 2>/dev/null || true
      fi
      if kill -0 "$pid" 2>/dev/null; then
        err "Failed to stop PID=${pid}"
        if [[ -n "$ns$pod$file" ]]; then
          remain+=("${pid}|${ns}|${pod}|${file}")
        else
          remain+=("${pid}")
        fi
      else
        stopped=$((stopped+1))
      fi
    fi
  done < "$PID_FILE"

  # Rewrite PID file with any remaining entries (should be none)
  : > "$PID_FILE"
  for line in "${remain[@]}"; do echo "$line" >> "$PID_FILE"; done
  if [[ ${#remain[@]} -eq 0 ]]; then rm -f "$PID_FILE"; fi

  info "Stopped ${stopped} tailer(s)."
}

status_all() {
  if [[ ! -f "$PID_FILE" ]]; then
    info "No active k8s log tailers. (${PID_FILE} not found)"
    return 0
  fi
  printf "%-8s %-22s %-52s %s\n" STATUS NAMESPACE/POD LOGFILE PID
  while IFS= read -r line; do
    [[ -z "${line:-}" ]] && continue
    local pid ns pod file
    if [[ "$line" == *"|"* ]]; then
      IFS='|' read -r pid ns pod file <<< "$line"
    else
      pid="$line"; ns=""; pod=""; file=""
    fi
    local id_display
    if [[ -n "$ns$pod" ]]; then id_display="${ns}/${pod}"; else id_display="unknown"; fi
    if kill -0 "$pid" 2>/dev/null; then
      printf "%-8s %-22s %-52s %s\n" RUNNING "${id_display}" "${file}" "${pid}"
    else
      printf "%-8s %-22s %-52s %s\n" DEAD "${id_display}" "${file}" "${pid}"
    fi
  done < "$PID_FILE"
}

usage() {
  cat <<EOF
Usage: $0 <start|stop|status> [ns:prefix ...]

Commands:
  start          Start tailers for default pods (and optional extra ns:prefix)
  stop           Stop all tailers started by this script (per ${PID_FILE})
  status         Show status of tailers recorded in ${PID_FILE}

Examples:
  $0 start
  $0 start ricplt:e2sim ricxapp:ricxapp-debugger-xapp
  $0 stop
  $0 status
EOF
}

cmd=${1:-status}
shift || true

case "$cmd" in
  start)
    start_all "$@"
    ;;
  stop)
    stop_all
    ;;
  status)
    status_all
    ;;
  -h|--help|help)
    usage
    ;;
  *)
    err "Unknown command: $cmd"
    usage
    exit 1
    ;;
esac
