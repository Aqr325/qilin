#!/bin/bash
#
# Kylin Security Operations Agent — Installation script for KylinOS V10
#
# Usage:
#   sudo bash install.sh              # Install with defaults
#   sudo bash install.sh --dev        # Install in development mode (console logging)
#   sudo bash install.sh --uninstall  # Remove agent
#

set -euo pipefail

# ── Configuration ────────────────────────────────────────────────────────
AGENT_NAME="kylin-secops-agent"
AGENT_VERSION="3.2.1"

INSTALL_DIR="/opt/${AGENT_NAME}"
CONFIG_DIR="/etc/${AGENT_NAME}"
DATA_DIR="/var/lib/${AGENT_NAME}"
LOG_DIR="/var/log/${AGENT_NAME}"
RUN_DIR="/var/run/${AGENT_NAME}"
SYSTEMD_DIR="/usr/lib/systemd/system"
BIN_PATH="${INSTALL_DIR}/${AGENT_NAME}"
SERVICE_FILE="${SYSTEMD_DIR}/${AGENT_NAME}.service"
CONFIG_FILE="${CONFIG_DIR}/config.yaml"

# Source directory (where this script lives)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Check if running in a package (desktop delivery) or source tree
if [[ -f "${SCRIPT_DIR}/../electron-app/frontend/index.html" ]] || [[ -f "${SCRIPT_DIR}/../../electron-app/frontend/index.html" ]]; then
    IS_DESKTOP_MODE=true
else
    IS_DESKTOP_MODE=false
fi

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# ── Functions ────────────────────────────────────────────────────────────

log_info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }

check_root() {
    if [[ $EUID -ne 0 ]]; then
        log_error "This script must be run as root (sudo)"
        exit 1
    fi
}

check_os() {
    if [[ ! -f /etc/kylin-release ]]; then
        log_warn "Not running on KylinOS. Installation may still work but is untested."
    else
        log_info "Detected KylinOS: $(head -1 /etc/kylin-release 2>/dev/null)"
    fi
}

# ── Pre-flight checks ────────────────────────────────────────────────────
preflight() {
    # Check writable paths
    for dir in "$INSTALL_DIR" "$CONFIG_DIR" "$DATA_DIR" "$LOG_DIR"; do
        if [[ ! -w "$dir" ]]; then
            log_error "Cannot write to $dir. Ensure it exists and you have permissions."
            exit 1
        fi
    done

    # Check if already installed and running
    if systemctl is-active --quiet "${AGENT_NAME}.service" 2>/dev/null; then
        log_warn "${AGENT_NAME} is currently running. It will be stopped and restarted."
        stop_agent || true
    fi

    # Check disk space (require at least 200MB)
    local available_kb
    available_kb=$(df --output=avail "$INSTALL_DIR" 2>/dev/null | tail -1 || echo "0")
    if [[ "$available_kb" -lt 204800 ]]; then
        log_warn "Low disk space: ${available_kb}KB available (recommended >= 200MB)"
    fi

    log_info "Pre-flight checks passed"
}

install_deps() {
    log_info "Installing system dependencies..."

    # Python 3.11+
    if command -v python3 &>/dev/null; then
        PYTHON=$(command -v python3)
        log_info "Python: $($PYTHON --version 2>&1)"
    else
        log_error "Python 3 not found. Please install python3 first."
        exit 1
    fi

    # Check Python version (need >= 3.9)
    local py_version
    py_version=$($PYTHON -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null)
    local py_major py_minor
    py_major=$(echo "$py_version" | cut -d. -f1)
    py_minor=$(echo "$py_version" | cut -d. -f2)
    if [[ "$py_major" -lt 3 ]] || [[ "$py_major" -eq 3 && "$py_minor" -lt 9 ]]; then
        log_error "Python 3.9+ required (found ${py_version})"
        exit 1
    fi

    # Install pip if needed
    if ! $PYTHON -m pip --version &>/dev/null; then
        log_info "Installing pip..."
        $PYTHON -m ensurepip --upgrade
    fi

    # ── Create virtual environment (isolated from system Python) ──
    log_info "Creating Python virtual environment at ${VENV_DIR}..."
    VENV_DIR="${INSTALL_DIR}/venv"
    $PYTHON -m venv "$VENV_DIR"

    # Upgrade pip inside venv
    "$VENV_DIR/bin/python3" -m pip install --upgrade pip --quiet

    # Install Python dependencies (inside venv)
    log_info "Installing Python dependencies..."
    # Find requirements.txt: prioritize PROJECT_DIR/agent/ or SCRIPT_DIR/
    local req_file=""
    for candidate in "${PROJECT_DIR}/agent/requirements.txt" "${SCRIPT_DIR}/requirements.txt" "${SCRIPT_DIR}/../../agent/requirements.txt"; do
        if [[ -f "$candidate" ]]; then
            req_file="$candidate"
            break
        fi
    done

    if [[ -n "$req_file" ]]; then
        log_info "Found requirements.txt at ${req_file}"
        "$VENV_DIR/bin/python3" -m pip install --no-cache-dir -r "$req_file"
    else
        log_warn "requirements.txt not found, installing fallback packages..."
        $PYTHON -m pip install --no-cache-dir aiohttp psutil pyyaml pyinotify distro 2>/dev/null || true
    fi

    # Install kylin_monitor-specific dependencies (available on KylinOS)
    "$VENV_DIR/bin/python3" -m pip install --no-cache-dir distro 2>/dev/null || true

    log_info "Virtual environment ready at ${VENV_DIR}"
    log_info "Installed Python packages:"
    "$VENV_DIR/bin/python3" -m pip list --format=columns 2>/dev/null | head -15
}

install_agent() {
    log_info "Installing ${AGENT_NAME} v${AGENT_VERSION}..."

    # Create directories
    mkdir -p "$INSTALL_DIR"
    mkdir -p "$CONFIG_DIR"
    mkdir -p "$DATA_DIR"
    mkdir -p "$LOG_DIR"
    mkdir -p "$RUN_DIR"

    # Clean old installation if present
    if [[ -d "${INSTALL_DIR}/src" ]]; then
        log_warn "Removing old installation..."
        rm -rf "${INSTALL_DIR:?}/src"
    fi

    # Install the Python package
    log_info "Copying agent files to ${INSTALL_DIR}..."
    # Copy only src/ (not src/__pycache__ or .pyc files)
    rsync -avq --exclude='__pycache__' --exclude='*.pyc' "${PROJECT_DIR}/src/" "${INSTALL_DIR}/src/" 2>/dev/null || \
        cp -r "${PROJECT_DIR}/src" "${INSTALL_DIR}/"

    # Create a wrapper script that calls the Python main from the virtual env
    log_info "Creating wrapper script..."
    local wrapper_dir
    wrapper_dir=$(mktemp -d)
    cat > "${wrapper_dir}/kylin_wrapper.py" << 'WRAPPER'
#!/usr/bin/env python3
"""Kylin SecOps Agent wrapper — runs from virtual environment."""
import sys
import os

# Use the virtual environment python
VENV_PYTHON = "/opt/kylin-secops-agent/venv/bin/python3"
AGENT_MAIN = "/opt/kylin-secops-agent/src/main.py"

if os.path.exists(VENV_PYTHON):
    os.execve(VENV_PYTHON, [VENV_PYTHON, AGENT_MAIN], os.environ)
else:
    # Fallback: use system python with path setup
    sys.path.insert(0, "/opt/kylin-secops-agent")
    try:
        from src.main import main
        main()
    except ImportError as e:
        sys.stderr.write(f"[Wrapper] ImportError: {e}\n")
        sys.stderr.write("Hint: Ensure src/ is installed in /opt/kylin-secops-agent/\n")
        sys.exit(1)
WRAPPER
    cp "${wrapper_dir}/kylin_wrapper.py" "$BIN_PATH"
    chmod 755 "$BIN_PATH"
    rm -rf "${wrapper_dir}"

    # Verify wrapper was created
    if [[ ! -f "$BIN_PATH" ]]; then
        log_error "Failed to create wrapper script at ${BIN_PATH}"
        exit 1
    fi

    # Install config file if not present
    if [[ ! -f "$CONFIG_FILE" ]]; then
        log_info "Creating default config at ${CONFIG_FILE}..."
        cat > "$CONFIG_FILE" << 'YAMLCONFIG'
# Kylin Security Operations Agent Configuration
platform:
  host: "secops.company.com"
  port: 443
  use_ssl: true
  ws_path: "/api/v1/ws/agent"
  token: ""

heartbeat:
  interval_min: 5
  interval_max: 12
  cpu_threshold: 90.0
  disk_threshold: 5.0

websocket:
  ping_interval: 15
  reconnect_min_delay: 1
  reconnect_max_delay: 60
  offline_timeout: 30

collector:
  enabled: true
  process_monitor: true
  network_monitor: true
  file_monitor: true
  log_monitor: true
  file_watch_paths:
    - /etc/passwd
    - /etc/shadow
    - /etc/ssh/sshd_config
    - /etc/cron.allow
    - /etc/cron.deny
    - /etc/sudoers
    - /etc/hosts.allow
    - /etc/hosts.deny
  log_files:
    - /var/log/secure
    - /var/log/messages
    - /var/log/audit/audit.log

engine:
  enabled: true
  audit_log_max: 10000
  offline_buffer_max: 1000

logging:
  level: "INFO"
  debug_console: false
  max_bytes: 10485760
  backup_count: 30
YAMLCONFIG
        chmod 640 "$CONFIG_FILE"
    fi

    log_info "Agent files installed"
}

install_systemd() {
    log_info "Installing systemd service..."

    # Copy service file
    SRC_SERVICE="${PROJECT_DIR}/systemd/${AGENT_NAME}.service"
    if [[ -f "$SRC_SERVICE" ]]; then
        cp "$SRC_SERVICE" "$SERVICE_FILE"
    else
        log_warn "Service file not found at ${SRC_SERVICE}, generating..."
        # Generate minimal service file
        cat > "$SERVICE_FILE" << SERVICEUNIT
[Unit]
Description=Kylin Security Operations Agent
After=network.target network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=${BIN_PATH}
CPUQuota=20%
MemoryMax=256M
Restart=always
RestartSec=10s
NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=strict
ProtectHome=yes
ReadWritePaths=${DATA_DIR} ${LOG_DIR} ${CONFIG_DIR}
Nice=10
LimitNOFILE=65536
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
SERVICEUNIT
    fi

    chmod 644 "$SERVICE_FILE"

    # Reload systemd and enable
    systemctl daemon-reload
    systemctl enable "${AGENT_NAME}.service"

    log_info "systemd service installed and enabled"
}

start_agent() {
    log_info "Starting ${AGENT_NAME}..."
    systemctl start "${AGENT_NAME}.service" || {
        log_warn "Failed to start service. Check logs: journalctl -u ${AGENT_NAME}"
        return 1
    }

    # Wait and check status
    sleep 2
    if systemctl is-active --quiet "${AGENT_NAME}.service"; then
        log_info "${AGENT_NAME} is running"
        systemctl status "${AGENT_NAME}.service" --no-pager | head -10
    else
        log_error "${AGENT_NAME} failed to start"
        journalctl -u "${AGENT_NAME}.service" --no-pager -n 20
        return 1
    fi
}

stop_agent() {
    log_info "Stopping ${AGENT_NAME}..."
    if systemctl is-active --quiet "${AGENT_NAME}.service" 2>/dev/null; then
        systemctl stop "${AGENT_NAME}.service"
        log_info "Service stopped"
    fi
}

uninstall() {
    log_warn "Uninstalling ${AGENT_NAME}..."

    stop_agent || true
    systemctl disable "${AGENT_NAME}.service" 2>/dev/null || true

    rm -f "$SERVICE_FILE"
    systemctl daemon-reload

    # Ask before removing data
    echo ""
    read -rp "Remove data directory ${DATA_DIR}? (y/N): " confirm
    if [[ "$confirm" == [yY] ]]; then
        rm -rf "$DATA_DIR"
        log_info "Data directory removed"
    fi

    echo ""
    read -rp "Remove log directory ${LOG_DIR}? (y/N): " confirm
    if [[ "$confirm" == [yY] ]]; then
        rm -rf "$LOG_DIR"
        log_info "Log directory removed"
    fi

    echo ""
    read -rp "Remove config directory ${CONFIG_DIR}? (y/N): " confirm
    if [[ "$confirm" == [yY] ]]; then
        rm -rf "$CONFIG_DIR"
        log_info "Config directory removed"
    fi

    echo ""
    read -rp "Remove installation directory ${INSTALL_DIR}? (y/N): " confirm
    if [[ "$confirm" == [yY] ]]; then
        rm -rf "$INSTALL_DIR"
        log_info "Installation directory removed"
    fi

    log_info "Uninstall complete"
}

main() {
    echo ""
    echo "========================================"
    echo " Kylin SecOps Agent v${AGENT_VERSION} Installer"
    echo "========================================"
    echo ""

    check_root
    check_os
    preflight

    # Validate source tree completeness
    if [[ ! -d "${SCRIPT_DIR}/src" ]]; then
        log_error "Source directory src/ not found at ${SCRIPT_DIR}/src"
        log_error "Ensure you are running this from the agent/ subdirectory of the project root."
        exit 1
    fi

    local mode="${1:-install}"

    case "$mode" in
        install)
            install_deps
            install_agent
            install_systemd
            start_agent
            ;;
        --dev)
            log_info "Development mode (console logging enabled)"
            echo ""
            read -rp "Install dependencies and files? (y/N): " confirm
            if [[ "$confirm" == [yY] ]]; then
                install_deps
                install_agent
                install_systemd
                # Enable debug console
                sed -i 's/debug_console: false/debug_console: true/' "$CONFIG_FILE" 2>/dev/null || true
                start_agent
            fi
            ;;
        --uninstall)
            uninstall
            ;;
        *)
            echo "Usage: $0 [--dev|--uninstall]"
            echo ""
            echo "  (no flag)   Install agent"
            echo "  --dev       Install with debug console logging"
            echo "  --uninstall Remove agent"
            exit 1
            ;;
    esac

    echo ""
    log_info "Operation completed"
    if [[ "$mode" != "--uninstall" ]]; then
        echo ""
        echo "Agent is running. Monitor with:"
        echo "  sudo journalctl -fu ${AGENT_NAME}"
        echo "  sudo systemctl status ${AGENT_NAME}"
        echo ""
        echo "Configuration: ${CONFIG_FILE}"
        echo "    Data:      ${DATA_DIR}"
        echo "    Logs:      ${LOG_DIR}"
    fi
    echo ""
}

main "$@"