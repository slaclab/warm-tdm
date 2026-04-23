#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${ROOT_DIR}/.venv"
RUCKUS_REQS="${ROOT_DIR}/firmware/submodules/ruckus/scripts/pip_requirements.txt"
IMPORT_TARGET="${WARM_TDM_IMPORT_TARGET:-RowFpgaBoard0}"
IMPORT_DIR="${ROOT_DIR}/firmware/targets/${IMPORT_TARGET}"

echo "[warm-tdm-regress] root: ${ROOT_DIR}"

if ! command -v python3 >/dev/null 2>&1; then
  echo "[warm-tdm-regress] error: python3 is required" >&2
  exit 1
fi

if ! command -v make >/dev/null 2>&1; then
  echo "[warm-tdm-regress] error: make is required" >&2
  exit 1
fi

if ! command -v ghdl >/dev/null 2>&1; then
  cat >&2 <<'EOF'
[warm-tdm-regress] error: ghdl is not installed.

Install it first, then rerun this script.

Examples:
  macOS (Homebrew): brew install ghdl
  Ubuntu/Debian:    sudo apt-get install -y ghdl
EOF
  exit 1
fi

if [ ! -d "${VENV_DIR}" ]; then
  echo "[warm-tdm-regress] creating virtualenv at ${VENV_DIR}"
  python3 -m venv "${VENV_DIR}"
fi

# shellcheck disable=SC1091
source "${VENV_DIR}/bin/activate"

echo "[warm-tdm-regress] upgrading pip"
python -m pip install --upgrade pip

echo "[warm-tdm-regress] installing repo python requirements"
python -m pip install -r "${ROOT_DIR}/pip_requirements.txt"

echo "[warm-tdm-regress] installing regression python requirements"
python -m pip install -r "${ROOT_DIR}/pip_requirements_regression.txt"

if [ -f "${RUCKUS_REQS}" ]; then
  echo "[warm-tdm-regress] installing ruckus python requirements"
  python -m pip install -r "${RUCKUS_REQS}"
fi

if [ ! -d "${IMPORT_DIR}" ]; then
  echo "[warm-tdm-regress] warning: import target directory not found: ${IMPORT_DIR}" >&2
fi

cat <<EOF
[warm-tdm-regress] setup complete

Activate the environment with:
  source "${VENV_DIR}/bin/activate"

Then import HDL sources with:
  make -C "${IMPORT_DIR}" import

Then run the first regression with:
  ./.venv/bin/python -m pytest -n 0 -q tests/warm_tdm/adc_dsp/test_AdcDsp.py
EOF
