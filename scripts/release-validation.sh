#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPORT_PATH="${CORPUS_REPORT_PATH:-${ROOT_DIR}/reports/release-corpus.json}"
BASELINE_PATH="${CORPUS_BASELINE_PATH:-${ROOT_DIR}/reports/corpus_baseline.json}"
SOURCE_REPORT_PATH="${CORPUS_BASELINE_SOURCE_REPORT:-}"
REVIEWED_REPORT_PATH="${SOURCE_REPORT_PATH:-${ROOT_DIR}/reports/corpus_differential_latest.json}"
PREVIEW_PATH="${CORPUS_BASELINE_PREVIEW_PATH:-${ROOT_DIR}/reports/corpus_baseline_preview.json}"

mkdir -p "$(dirname "${REPORT_PATH}")"
mkdir -p "$(dirname "${PREVIEW_PATH}")"
cd "${ROOT_DIR}"

set +e
python corpus_runner.py \
  --root "${ROOT_DIR}" \
  --preview-baseline "${BASELINE_PATH}" \
  --source-report "${REVIEWED_REPORT_PATH}" \
  --json > "${PREVIEW_PATH}"
preview_status=$?
set -e

if [[ ! -s "${PREVIEW_PATH}" ]]; then
  echo "Release validation blocked: baseline preview did not produce JSON at ${PREVIEW_PATH}." >&2
  exit 1
fi

if ! preview_matches="$(
  python - "${PREVIEW_PATH}" <<'PY'
import json
import sys

try:
    with open(sys.argv[1], encoding="utf-8") as preview_file:
        preview = json.load(preview_file)
except (OSError, json.JSONDecodeError) as error:
    print(f"could not parse baseline preview: {error}", file=sys.stderr)
    raise SystemExit(1)

matches = preview.get("reviewed_report_matches_current")
if not isinstance(matches, bool):
    print(
        "baseline preview is missing boolean reviewed_report_matches_current",
        file=sys.stderr,
    )
    raise SystemExit(1)
print(str(matches).lower())
PY
)"; then
  echo "Release validation blocked: baseline preview JSON could not be parsed." >&2
  exit 1
fi

if [[ "${preview_matches}" != "true" ]]; then
  echo "Release validation blocked: reviewed_report_matches_current is false; the reviewed baseline report does not match the current corpus. See ${PREVIEW_PATH}." >&2
  exit 1
fi

if (( preview_status != 0 )); then
  echo "Release validation blocked: baseline preview exited with status ${preview_status}. See ${PREVIEW_PATH}." >&2
  exit "${preview_status}"
fi

if [[ -n "${SOURCE_REPORT_PATH}" ]]; then
  python corpus_runner.py \
    --root "${ROOT_DIR}" \
    --update-baseline "${BASELINE_PATH}" \
    --source-report "${SOURCE_REPORT_PATH}"
fi

exec python corpus_runner.py \
  --root "${ROOT_DIR}" \
  --baseline "${BASELINE_PATH}" \
  --output "${REPORT_PATH}" \
  --fail-on-loss