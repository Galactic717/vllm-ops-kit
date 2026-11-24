#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
out=loadtest/results/latest/security
mkdir -p "$out"

# Retain the full policy report and enforce security-critical invariants here.
# The advisory findings remain visible even when they do not block the pipeline.
status=0
checkov -d terraform --framework terraform --external-checks-dir policy/checkov \
  --skip-download --output cli --output json --output-file-path "console,$out/checkov-report.json" \
  --hard-fail-on CKV2_AWS_9001,CKV2_GCP_9001,CKV_AWS_79,CKV_AWS_8,CKV_GCP_114,CKV_GCP_13,CKV_GCP_125 \
  || status=1

for image in vllm-ops-fixture:local verstak-agent:local verifine-slm:local \
  vllm-ops-postgres:local redis:7.4.12-alpine; do
  if ! docker image inspect "$image" >/dev/null 2>&1; then
    docker pull "$image"
  fi
  name=$(printf '%s' "$image" | tr '/:' '__')
  report="$out/$name.json"
  if ! trivy image --scanners vuln --severity HIGH,CRITICAL \
    --format json --output "$report" "$image"; then
    status=1
    continue
  fi
  python - "$report" <<'PY' || status=1
import json
from pathlib import Path
import sys

report = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
findings = [item for result in report.get("Results", [])
            for item in result.get("Vulnerabilities", [])]
fixable = [item for item in findings if item.get("FixedVersion")]
print(f'{report["ArtifactName"]}: {len(fixable)} with a published fix, '
      f'{len(findings) - len(fixable)} without a published fix')
sys.exit(bool(fixable))
PY
done
exit "$status"
