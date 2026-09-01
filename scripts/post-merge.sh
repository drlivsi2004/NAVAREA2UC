#!/usr/bin/env bash
set -euo pipefail

python -m py_compile main.py tests/*.py
python -m unittest discover -s tests -p 'test_*.py'

ARTIFACT_DIR="artifacts/navarea2uc-imported-design"
if [[ -f "${ARTIFACT_DIR}/package-lock.json" && ! -d "${ARTIFACT_DIR}/node_modules" ]]; then
  npm --prefix "${ARTIFACT_DIR}" ci --ignore-scripts --no-audit --no-fund
fi

if [[ -f "${ARTIFACT_DIR}/package.json" ]]; then
  npm --prefix "${ARTIFACT_DIR}" run typecheck
fi