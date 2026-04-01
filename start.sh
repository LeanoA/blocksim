#!/usr/bin/env bash
# =============================================================================
# BlockSim — Script de inicio rápido
# =============================================================================
#
# Inicia el sistema completo (backend + frontend) con un solo comando.
#
# Uso:
#   ./start.sh          # Inicia backend y frontend
#   ./start.sh --help   # Muestra esta ayuda
#
# Requisitos:
#   - uv  (gestor de paquetes Python)  — https://docs.astral.sh/uv/
#   - node / npm                       — https://nodejs.org/
#
# El script:
#   1. Verifica que las dependencias del sistema estén instaladas
#   2. Instala/sincroniza dependencias del backend (uv sync)
#   3. Instala dependencias del frontend (npm install)
#   4. Inicia el servidor API (uvicorn) en segundo plano
#   5. Inicia el servidor de desarrollo frontend (Vite)
#   6. Limpia procesos al salir (Ctrl+C)
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Colores para mensajes en consola
# ---------------------------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # Sin color

# ---------------------------------------------------------------------------
# Directorio raíz del proyecto (donde está este script)
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="${SCRIPT_DIR}/backend"
FRONTEND_DIR="${SCRIPT_DIR}/frontend"

# ---------------------------------------------------------------------------
# PIDs de procesos en segundo plano (para limpiar al salir)
# ---------------------------------------------------------------------------
BACKEND_PID=""

# ---------------------------------------------------------------------------
# Funciones auxiliares
# ---------------------------------------------------------------------------

log_info()    { echo -e "${BLUE}[INFO]${NC}  $*"; }
log_ok()      { echo -e "${GREEN}[OK]${NC}    $*"; }
log_warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
log_error()   { echo -e "${RED}[ERROR]${NC} $*"; }

mostrar_ayuda() {
    echo ""
    echo -e "${CYAN}BlockSim — Script de inicio rápido${NC}"
    echo ""
    echo "Uso:"
    echo "  ./start.sh          Inicia backend y frontend"
    echo "  ./start.sh --help   Muestra esta ayuda"
    echo ""
    echo "URLs:"
    echo "  Backend API:    http://localhost:8000"
    echo "  API Docs:       http://localhost:8000/docs"
    echo "  Frontend:       http://localhost:5173"
    echo ""
    exit 0
}

# ---------------------------------------------------------------------------
# Limpieza al salir — mata procesos en segundo plano
# ---------------------------------------------------------------------------
cleanup() {
    echo ""
    log_info "Deteniendo servicios..."

    if [[ -n "${BACKEND_PID}" ]] && kill -0 "${BACKEND_PID}" 2>/dev/null; then
        kill "${BACKEND_PID}" 2>/dev/null
        wait "${BACKEND_PID}" 2>/dev/null || true
        log_ok "Backend detenido (PID ${BACKEND_PID})"
    fi

    log_ok "Todos los servicios detenidos. ¡Hasta luego!"
    exit 0
}

# Capturar señales de salida para limpiar procesos
trap cleanup SIGINT SIGTERM EXIT

# ---------------------------------------------------------------------------
# Verificación de dependencias del sistema
# ---------------------------------------------------------------------------
verificar_dependencias() {
    log_info "Verificando dependencias del sistema..."

    local faltan=0

    # Verificar uv
    if command -v uv &>/dev/null; then
        log_ok "uv encontrado: $(uv --version)"
    else
        log_error "uv no está instalado."
        log_info "  Instálalo con: curl -LsSf https://astral.sh/uv/install.sh | sh"
        faltan=1
    fi

    # Verificar Node.js
    if command -v node &>/dev/null; then
        log_ok "Node.js encontrado: $(node --version)"
    else
        log_error "Node.js no está instalado."
        log_info "  Instálalo desde: https://nodejs.org/"
        faltan=1
    fi

    # Verificar npm
    if command -v npm &>/dev/null; then
        log_ok "npm encontrado: $(npm --version)"
    else
        log_error "npm no está instalado."
        log_info "  Normalmente se instala junto con Node.js."
        faltan=1
    fi

    if [[ "${faltan}" -ne 0 ]]; then
        log_error "Faltan dependencias. Instálalas e intenta de nuevo."
        exit 1
    fi

    echo ""
}

# ---------------------------------------------------------------------------
# Instalar dependencias del backend
# ---------------------------------------------------------------------------
instalar_backend() {
    log_info "Sincronizando dependencias del backend (uv sync)..."
    (cd "${BACKEND_DIR}" && uv sync --dev)
    log_ok "Dependencias del backend listas."
    echo ""
}

# ---------------------------------------------------------------------------
# Instalar dependencias del frontend
# ---------------------------------------------------------------------------
instalar_frontend() {
    log_info "Instalando dependencias del frontend (npm install)..."
    (cd "${FRONTEND_DIR}" && npm install --silent)
    log_ok "Dependencias del frontend listas."
    echo ""
}

# ---------------------------------------------------------------------------
# Iniciar el servidor backend (uvicorn + FastAPI)
# ---------------------------------------------------------------------------
iniciar_backend() {
    log_info "Iniciando servidor backend (uvicorn)..."
    (
        cd "${BACKEND_DIR}" && \
        uv run uvicorn blocksim.api.app:create_app \
            --factory \
            --reload \
            --host 0.0.0.0 \
            --port 8000
    ) &
    BACKEND_PID=$!
    log_ok "Backend iniciado en segundo plano (PID ${BACKEND_PID})"
    echo ""
}

# ---------------------------------------------------------------------------
# Iniciar el servidor frontend (Vite dev server)
# ---------------------------------------------------------------------------
iniciar_frontend() {
    log_info "Iniciando servidor frontend (Vite)..."
    echo ""
    echo -e "${CYAN}=============================================${NC}"
    echo -e "${CYAN}  BlockSim está corriendo:${NC}"
    echo -e ""
    echo -e "  ${GREEN}Frontend:${NC}   http://localhost:5173"
    echo -e "  ${GREEN}Backend API:${NC} http://localhost:8000"
    echo -e "  ${GREEN}API Docs:${NC}   http://localhost:8000/docs"
    echo -e "  ${GREEN}Health:${NC}     http://localhost:8000/health"
    echo -e ""
    echo -e "  Presiona ${YELLOW}Ctrl+C${NC} para detener todo."
    echo -e "${CYAN}=============================================${NC}"
    echo ""

    # El frontend corre en primer plano para que Ctrl+C lo detenga
    (cd "${FRONTEND_DIR}" && npm run dev)
}

# ---------------------------------------------------------------------------
# Programa principal
# ---------------------------------------------------------------------------

# Mostrar ayuda si se solicita
if [[ "${1:-}" == "--help" ]] || [[ "${1:-}" == "-h" ]]; then
    mostrar_ayuda
fi

echo ""
echo -e "${CYAN}╔══════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║        BlockSim — Inicio Rápido          ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════╝${NC}"
echo ""

verificar_dependencias
instalar_backend
instalar_frontend
iniciar_backend

# Esperar un momento para que el backend arranque antes del frontend
sleep 2

iniciar_frontend
