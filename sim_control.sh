#!/bin/bash

# Stadium RF Simulation Management Script
# Usage: ./sim_control.sh [status|stop|logs|clean]

set -euo pipefail

PID_FILE="simulation.pid"
LOG_DIR="logs"
K8S_LOGS_PID="k8s-logs.pid"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header() {
    echo -e "${BLUE}[SIM-CONTROL]${NC} $1"
}

show_usage() {
    echo "Usage: $0 [command]"
    echo ""
    echo "Commands:"
    echo "  status   Show simulation status"
    echo "  stop     Stop running simulation and Kubernetes pod logs"
    echo "  logs     Show recent logs (tail -f)"
    echo "  k8s      Manage Kubernetes pod logs (status|start|stop)"
    echo "  clean    Clean up old logs and PID files"
    echo "  help     Show this help"
    echo ""
    echo "If no command is provided, 'status' is assumed."
}

get_simulation_status() {
    if [[ -f "$PID_FILE" ]]; then
        local pid=$(cat "$PID_FILE")
        if kill -0 "$pid" 2>/dev/null; then
            print_status "Simulation is RUNNING with PID: $pid"
            print_status "Started: $(ps -o lstart= -p $pid 2>/dev/null || echo 'Unknown')"
            print_status "Runtime: $(ps -o etime= -p $pid 2>/dev/null | tr -d ' ' || echo 'Unknown')"
            print_status "Memory: $(ps -o rss= -p $pid 2>/dev/null | awk '{printf "%.1f MB", $1/1024}' || echo 'Unknown')"
            
            local latest_log=$(ls -t $LOG_DIR/simulation_*.log 2>/dev/null | head -1 || echo "")
            if [[ -n "$latest_log" ]]; then
                print_status "Log file: $latest_log"
                print_status "Log size: $(du -h "$latest_log" 2>/dev/null | cut -f1 || echo 'Unknown')"
            fi
            return 0
        else
            print_warning "PID file exists but process not running (stale PID: $pid)"
            return 1
        fi
    else
        print_status "Simulation is NOT running"
        return 1
    fi
}

stop_simulation() {
    if [[ -f "$PID_FILE" ]]; then
        local pid=$(cat "$PID_FILE")
        if kill -0 "$pid" 2>/dev/null; then
            print_status "Stopping simulation (PID: $pid)..."
            
            # First try graceful shutdown
            kill -TERM "$pid"
            
            # Wait up to 10 seconds for graceful shutdown
            local count=0
            while kill -0 "$pid" 2>/dev/null && [[ $count -lt 10 ]]; do
                sleep 1
                ((count++))
                echo -n "."
            done
            echo ""
            
            # If still running, force kill
            if kill -0 "$pid" 2>/dev/null; then
                print_warning "Graceful shutdown failed, forcing termination..."
                kill -9 "$pid"
                sleep 1
            fi
            
            # Verify it's stopped
            if kill -0 "$pid" 2>/dev/null; then
                print_error "Failed to stop simulation"
                return 1
            else
                print_status "Simulation stopped successfully"
                rm -f "$PID_FILE"
                return 0
            fi
        else
            print_warning "PID file exists but process not running (stale PID). Cleaning up."
            rm -f "$PID_FILE"
            return 0
        fi
    else
        print_status "No simulation running (no PID file)"
        return 0
    fi
}

show_logs() {
    local latest_log=$(ls -t $LOG_DIR/simulation_*.log 2>/dev/null | head -1 || echo "")
    
    if [[ -n "$latest_log" ]]; then
        print_status "Showing logs from: $latest_log"
        print_status "Press Ctrl+C to exit log view"
        echo ""
        tail -f "$latest_log"
    else
        print_error "No log files found in $LOG_DIR"
        return 1
    fi
}

clean_logs() {
    print_status "Cleaning up old files..."
    
    # Remove stale PID file
    if [[ -f "$PID_FILE" ]]; then
        local pid=$(cat "$PID_FILE")
        if ! kill -0 "$pid" 2>/dev/null; then
            print_status "Removing stale PID file"
            rm -f "$PID_FILE"
        fi
    fi
    
    # Keep only last 5 log files
    if [[ -d "$LOG_DIR" ]]; then
        local log_count=$(ls $LOG_DIR/simulation_*.log 2>/dev/null | wc -l || echo 0)
        if [[ $log_count -gt 5 ]]; then
            local to_remove=$((log_count - 5))
            print_status "Removing $to_remove old log files (keeping latest 5)"
            ls -t $LOG_DIR/simulation_*.log | tail -n +6 | xargs rm -f
        fi
    fi
    
    # Clean stale k8s logs PID
    if [[ -f "$K8S_LOGS_PID" ]]; then
        local alive=false
        while IFS='|' read -r pid _; do
            if [[ -n "${pid}" ]] && kill -0 "${pid}" 2>/dev/null; then
                alive=true; break
            fi
        done < "$K8S_LOGS_PID"
        if [[ "$alive" == false ]]; then
            print_status "Removing stale $K8S_LOGS_PID"
            rm -f "$K8S_LOGS_PID"
        fi
    fi

    print_status "Cleanup completed"
}

k8s_logs_stop() {
    # Stop Kubernetes pod logs tailers if any
    if [[ -x ./k8s_logs.sh ]]; then
        print_status "Stopping Kubernetes pod logs"
        ./k8s_logs.sh stop || true
        return 0
    fi
    if [[ -f "$K8S_LOGS_PID" ]]; then
        print_status "Stopping Kubernetes pod logs (legacy PID file)"
        while IFS= read -r line; do
            [[ -z "${line:-}" ]] && continue
            local pid
            if [[ "$line" == *"|"* ]]; then
                pid="${line%%|*}"
            else
                pid="$line"
            fi
            if kill -0 "$pid" 2>/dev/null; then
                kill -TERM "$pid" 2>/dev/null || true
                sleep 1
                kill -9 "$pid" 2>/dev/null || true
            fi
        done < "$K8S_LOGS_PID"
        rm -f "$K8S_LOGS_PID"
        return 0
    fi
    print_status "No Kubernetes pod log tailers to stop"
    return 0
}

k8s_logs_cmd() {
    local sub=${1:-status}
    shift || true
    if [[ ! -x ./k8s_logs.sh ]]; then
        print_error "k8s_logs.sh not found or not executable"
        return 1
    fi
    case "$sub" in
        status)
            ./k8s_logs.sh status
            ;;
        start)
            ./k8s_logs.sh start "$@"
            ;;
        stop)
            ./k8s_logs.sh stop
            ;;
        *)
            print_error "Unknown k8s subcommand: $sub"
            echo "Usage: $0 k8s [status|start|stop] [ns:prefix ...]"
            return 1
            ;;
    esac
}

# Main execution
COMMAND=${1:-status}

case $COMMAND in
    status|st)
        print_header "Simulation Status"
        get_simulation_status
        ;;
    stop)
        print_header "Stopping Simulation"
    stop_simulation || true
    k8s_logs_stop || true
        ;;
    logs|log)
        show_logs
        ;;
    k8s)
        shift || true
        k8s_logs_cmd "$@"
        ;;
    clean)
        print_header "Cleaning Up"
        clean_logs
        ;;
    help|--help|-h)
        show_usage
        ;;
    *)
        print_error "Unknown command: $COMMAND"
        show_usage
        exit 1
        ;;
esac
