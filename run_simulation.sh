#!/bin/bash

# Stadium RF Simulation Launcher
# Usage: ./run_simulation.sh <destination-address> [options]

set -euo pipefail

# Default values
DEST_ADDR=""
LOG_DIR="logs"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="simulation_${TIMESTAMP}.log"
PID_FILE="simulation.pid"
PYTHON_ENV="stadium-rf-sim"
E2SIM_POD_NAME="e2sim"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
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
    echo -e "${BLUE}[STADIUM-RF-SIM]${NC} $1"
}

# Function to get E2SIM pod IP automatically
get_e2sim_pod_ip() {
    print_status "Attempting to discover E2SIM pod IP automatically..." >&2
    
    # Check if kubectl is available
    if ! command -v kubectl &> /dev/null; then
        print_warning "kubectl not found, cannot auto-discover pod IP" >&2
        return 1
    fi
    
    # Try to get pod IP by exact name first in ricplt namespace
    local pod_ip=$(kubectl get pod "$E2SIM_POD_NAME" -n ricplt -o jsonpath='{.status.podIP}' 2>/dev/null)
    
    if [[ -n "$pod_ip" && "$pod_ip" != "null" ]]; then
        print_status "Found E2SIM pod '$E2SIM_POD_NAME' with IP: $pod_ip" >&2
        echo "$pod_ip"
        return 0
    fi
    
    # If exact name doesn't work, search for pods starting with e2sim- in ricplt namespace
    print_status "Exact pod name not found, searching for pods starting with 'e2sim-' in ricplt namespace..." >&2
    local pods=$(kubectl get pods -n ricplt -o jsonpath='{range .items[*]}{.metadata.name}{"|"}{.status.podIP}{"\n"}{end}' 2>/dev/null | grep "^e2sim-" | head -1)
    
    if [[ -n "$pods" ]]; then
        local pod_name=$(echo "$pods" | cut -d'|' -f1)
        local pod_ip=$(echo "$pods" | cut -d'|' -f2)
        
        if [[ -n "$pod_ip" && "$pod_ip" != "null" ]]; then
            print_status "Found E2SIM pod '$pod_name' with IP: $pod_ip" >&2
            echo "$pod_ip"
            return 0
        fi
    fi
    
    # Fallback: search in all namespaces for pods starting with e2sim-
    print_status "No pods found in ricplt namespace, searching all namespaces for pods starting with 'e2sim-'..." >&2
    local pods=$(kubectl get pods --all-namespaces -o jsonpath='{range .items[*]}{.metadata.name}{"|"}{.status.podIP}{"\n"}{end}' 2>/dev/null | grep "^e2sim-" | head -1)
    
    if [[ -n "$pods" ]]; then
        local pod_name=$(echo "$pods" | cut -d'|' -f1)
        local pod_ip=$(echo "$pods" | cut -d'|' -f2)
        
        if [[ -n "$pod_ip" && "$pod_ip" != "null" ]]; then
            print_status "Found E2SIM pod '$pod_name' with IP: $pod_ip" >&2
            echo "$pod_ip"
            return 0
        fi
    fi
    
    print_warning "Could not find any E2SIM pods starting with 'e2sim-' or get their IP" >&2
    return 1
}

# Function to show usage
show_usage() {
    echo "Usage: $0 [destination-address] [options]"
    echo ""
    echo "If no destination address is provided, the script will attempt to"
    echo "automatically discover the E2SIM pod IP using kubectl."
    echo ""
    echo "Options:"
    echo "  -d, --daemon     Run in background (default)"
    echo "  -f, --foreground Run in foreground"
    echo "  -l, --log-dir    Log directory (default: logs)"
    echo "  -p, --pod-name   E2SIM pod name (default: $E2SIM_POD_NAME)"
    echo "  -h, --help       Show this help"
    echo ""
    echo "Examples:"
    echo "  $0                              # Auto-discover E2SIM pod IP"
    echo "  $0 10.233.92.62                # Use specific IP"
    echo "  $0 --foreground                 # Auto-discover and run in foreground"
    echo "  $0 10.233.92.62 --foreground   # Use specific IP and run in foreground"
    echo "  $0 --pod-name my-e2sim-pod     # Use different pod name for discovery"
}

# Function to check if simulation is already running
check_running() {
    if [[ -f "$PID_FILE" ]]; then
        local pid=$(cat "$PID_FILE")
        if kill -0 "$pid" 2>/dev/null; then
            print_warning "Simulation already running with PID: $pid"
            print_status "Log file: $LOG_DIR/$(ls -t $LOG_DIR/simulation_*.log 2>/dev/null | head -1 | xargs basename 2>/dev/null || echo 'No log found')"
            print_status "To monitor: tail -f $LOG_DIR/simulation_*.log"
            print_status "To stop: kill $pid"
            exit 1
        else
            print_warning "Stale PID file found, removing..."
            rm -f "$PID_FILE"
        fi
    fi
}

# Function to setup logging
setup_logging() {
    mkdir -p "$LOG_DIR"
    LOG_FILE="$LOG_DIR/simulation_${TIMESTAMP}.log"
    
    # Keep only last 10 log files
    find "$LOG_DIR" -name "simulation_*.log" -type f | sort -r | tail -n +11 | xargs rm -f 2>/dev/null || true
}

# Function to activate conda environment
activate_env() {
    if command -v conda &> /dev/null; then
        print_status "Activating conda environment: $PYTHON_ENV"
        eval "$(conda shell.bash hook)"
        conda activate "$PYTHON_ENV" 2>/dev/null || {
            print_warning "Could not activate conda environment '$PYTHON_ENV', using current environment"
        }
    else
        print_warning "Conda not found, using current Python environment"
    fi
}

# Function to validate input file
validate_input() {
    if [[ ! -f "input.csv" ]]; then
        print_error "input.csv file not found in current directory"
        exit 1
    fi
    
    print_status "Input file: input.csv ($(wc -l < input.csv) lines)"
}

# Function to run simulation in background
run_background() {
    print_header "Starting Stadium RF Simulation (Background Mode)"
    print_status "Destination: $DEST_ADDR"
    print_status "Log file: $LOG_FILE"
    print_status "PID file: $PID_FILE"
    
    # Start simulation with nohup
    nohup python main.py "$DEST_ADDR" > "$LOG_FILE" 2>&1 &
    local pid=$!
    echo $pid > "$PID_FILE"
    
    # Wait a moment to check if process started successfully
    sleep 2
    if kill -0 $pid 2>/dev/null; then
        print_status "Simulation started successfully with PID: $pid"
        print_status ""
        print_status "Monitoring commands:"
        print_status "  Watch logs: tail -f $LOG_FILE"
        print_status "  Check status: ps -p $pid"
        print_status "  Stop simulation: kill $pid"
        print_status "  Force stop: kill -9 $pid"
    else
        print_error "Simulation failed to start"
        rm -f "$PID_FILE"
        exit 1
    fi
}

# Function to run simulation in foreground
run_foreground() {
    print_header "Starting Stadium RF Simulation (Foreground Mode)"
    print_status "Destination: $DEST_ADDR"
    print_status "Log file: $LOG_FILE"
    print_status "Press Ctrl+C to stop"
    print_status ""
    
    # Use tee to both display and log
    python main.py "$DEST_ADDR" 2>&1 | tee "$LOG_FILE"
}

# Parse command line arguments
FOREGROUND=false
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_usage
            exit 0
            ;;
        -f|--foreground)
            FOREGROUND=true
            shift
            ;;
        -d|--daemon)
            FOREGROUND=false
            shift
            ;;
        -l|--log-dir)
            LOG_DIR="$2"
            shift 2
            ;;
        -p|--pod-name)
            E2SIM_POD_NAME="$2"
            shift 2
            ;;
        -*)
            print_error "Unknown option: $1"
            show_usage
            exit 1
            ;;
        *)
            if [[ -z "$DEST_ADDR" ]]; then
                DEST_ADDR="$1"
            else
                print_error "Multiple destination addresses provided"
                show_usage
                exit 1
            fi
            shift
            ;;
    esac
done

# Auto-discover destination address if not provided
if [[ -z "$DEST_ADDR" ]]; then
    print_status "No destination address provided, attempting auto-discovery..."
    DEST_ADDR=$(get_e2sim_pod_ip)
    if [[ $? -ne 0 || -z "$DEST_ADDR" ]]; then
        print_error "Failed to auto-discover E2SIM pod IP"
        print_error "Please provide destination address manually or ensure:"
        print_error "  1. kubectl is installed and configured"
        print_error "  2. E2SIM pod is running and has an IP"
        print_error "  3. You have permissions to access the pod"
        echo ""
        show_usage
        exit 1
    fi
fi

# Validate destination address format
if [[ ! "$DEST_ADDR" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    print_error "Invalid IP address format: $DEST_ADDR"
    exit 1
fi

# Main execution
check_running
setup_logging
activate_env
validate_input

if [[ "$FOREGROUND" == "true" ]]; then
    run_foreground
else
    run_background
fi
