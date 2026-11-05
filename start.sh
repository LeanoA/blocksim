#!/usr/bin/env bash
# =============================================================================
# BlockSim — Quick Start Script
# =============================================================================
#
# Starts the full system (backend + frontend) with a single command.
#
# Usage:
#   ./start.sh          # Start backend and frontend
#   ./start.sh --help   # Show this help message
#
# Requirements:
#   - uv  (Python package manager) — https://docs.astral.sh/uv/
#   - node / npm                   — https://nodejs.org/
#
# Steps performed:
#   1. Verify required system dependencies are installed
#   2. Sync backend dependencies (uv sync)
#   3. Install frontend dependencies (npm install)
#   4. Start the API server (uvicorn) in the background
#   5. Start the frontend dev server (Vite)
#   6. Clean up background processes on exit (Ctrl+C)
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Console colors
# ---------------------------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# ---------------------------------------------------------------------------
# Project root directory
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="${SCRIPT_DIR}/backend"
FRONTEND_DIR="${SCRIPT_DIR}/frontend"

# ---------------------------------------------------------------------------
# Background process PIDs (for cleanup on exit)
# ---------------------------------------------------------------------------
BACKEND_PID=""

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

log_info()    { echo -e "${BLUE}[INFO]${NC}  $*"; }
log_ok()      { echo -e "${GREEN}[OK]${NC}    $*"; }
log_warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
log_error()   { echo -e "${RED}[ERROR]${NC} $*"; }

show_help() {
    echo ""
    echo -e "${CYAN}BlockSim — Quick Start Script${NC}"
    echo ""
    echo "Usage:"
    echo "  ./start.sh          Start backend and frontend"
    echo "  ./start.sh --help   Show this help message"
    echo ""
    echo "URLs:"
    echo "  Backend API:    http://localhost:8000"
    echo "  API Docs:       http://localhost:8000/docs"
    echo "  Frontend:       http://localhost:5173"
    echo ""
    exit 0
}

# ---------------------------------------------------------------------------
# Exit cleanup — terminates background processes
# ---------------------------------------------------------------------------
cleanup() {
    echo ""
    log_info "Stopping services..."

    if [[ -n "${BACKEND_PID}" ]] && kill -0 "${BACKEND_PID}" 2>/dev/null; then
        kill "${BACKEND_PID}" 2>/dev/null
        wait "${BACKEND_PID}" 2>/dev/null || true
        log_ok "Backend stopped (PID ${BACKEND_PID})"
    fi

    log_ok "All services stopped."
    exit 0
}

trap cleanup SIGINT SIGTERM EXIT

# ---------------------------------------------------------------------------
# System dependency checks
# ---------------------------------------------------------------------------
check_dependencies() {
    log_info "Checking system dependencies..."

    local missing=0

    if command -v uv &>/dev/null; then
        log_ok "uv found: $(uv --version)"
    else
        log_error "uv is not installed."
        log_info "  Install with: curl -LsSf https://astral.sh/uv/install.sh | sh"
        missing=1
    fi

    if command -v node &>/dev/null; then
        log_ok "Node.js found: $(node --version)"
    else
        log_error "Node.js is not installed."
        log_info "  Install from: https://nodejs.org/"
        missing=1
    fi

    if command -v npm &>/dev/null; then
        log_ok "npm found: $(npm --version)"
    else
        log_error "npm is not installed."
        log_info "  Typically installed alongside Node.js."
        missing=1
    fi

    if [[ "${missing}" -ne 0 ]]; then
        log_error "Missing required dependencies. Please install them and retry."
        exit 1
    fi

    echo ""
}

# ---------------------------------------------------------------------------
# Install backend dependencies
# ---------------------------------------------------------------------------
install_backend() {
    log_info "Syncing backend dependencies (uv sync)..."
    (cd "${BACKEND_DIR}" && uv sync --dev)
    log_ok "Backend dependencies ready."
    echo ""
}

# ---------------------------------------------------------------------------
# Install frontend dependencies
# ---------------------------------------------------------------------------
install_frontend() {
    log_info "Installing frontend dependencies (npm install)..."
    (cd "${FRONTEND_DIR}" && npm install --silent)
    log_ok "Frontend dependencies ready."
    echo ""
}

# ---------------------------------------------------------------------------
# Start backend server (uvicorn + FastAPI)
# ---------------------------------------------------------------------------
start_backend() {
    log_info "Starting backend server (uvicorn)..."
    (
        cd "${BACKEND_DIR}" && \
        uv run uvicorn blocksim.api.app:create_app \
            --factory \
            --reload \
            --host 0.0.0.0 \
            --port 8000
    ) &
    BACKEND_PID=$!
    log_ok "Backend running in background (PID ${BACKEND_PID})"
    echo ""
}

# ---------------------------------------------------------------------------
# Start frontend server (Vite dev server)
# ---------------------------------------------------------------------------
start_frontend() {
    log_info "Starting frontend server (Vite)..."
    echo ""
    echo -e "${CYAN}=============================================${NC}"
    echo -e "${CYAN}  BlockSim is running:${NC}"
    echo -e ""
    echo -e "  ${GREEN}Frontend:${NC}    http://localhost:5173"
    echo -e "  ${GREEN}Backend API:${NC} http://localhost:8000"
    echo -e "  ${GREEN}API Docs:${NC}    http://localhost:8000/docs"
    echo -e "  ${GREEN}Health:${NC}      http://localhost:8000/health"
    echo -e ""
    echo -e "  Press ${YELLOW}Ctrl+C${NC} to stop all services."
    echo -e "${CYAN}=============================================${NC}"
    echo ""

    (cd "${FRONTEND_DIR}" && npm run dev)
}

# ---------------------------------------------------------------------------
# Main entrypoint
# ---------------------------------------------------------------------------

if [[ "${1:-}" == "--help" ]] || [[ "${1:-}" == "-h" ]]; then
    show_help
fi

echo ""
echo -e "${CYAN}╔══════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║          BlockSim — Quick Start          ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════╝${NC}"
echo ""

check_dependencies
install_backend
install_frontend
start_backend

sleep 2

start_frontend
