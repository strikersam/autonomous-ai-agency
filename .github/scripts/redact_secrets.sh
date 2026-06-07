#!/usr/bin/env bash
# redact_secrets.sh — Strip credentials from test output files before
# they reach any GitHub issue. Defense-in-depth: even if a test misbehaves
# and dumps an env var, the escalation issue body won't contain the secret.
#
# Usage: .github/scripts/redact_secrets.sh /tmp/test_baseline.txt /tmp/test_failure_details.txt
#   Pass one or more file paths; each will be sanitised in-place.
#   Missing/non-existent files are silently skipped.
#
# Redaction rules (ordered from most to least specific):
#   GitHub classic tokens     ghp_<hex36+>
#   GitHub OAuth tokens       gho_<hex36+>
#   GitHub fine-grained PATs  github_pat_<alnum22+>
#   OpenAI / generic API keys sk-<alnum32+>
#   AWS access keys           AKIA<base16>
#   NVIDIA API keys           nvapi-<alnum40+>
#   JWT tokens                jwt-<base64url32+>
#
# Platform notes:
#   Uses `sed -i''` (no space) which works on both GNU sed (Linux/CI) and
#   BSD sed (macOS). The `|| true` on the final sed ensures that a dry-run
#   on a read-only file or a missing file (handled by [ -f ]) never fails
#   the calling step.

set -euo pipefail

if [ $# -eq 0 ]; then
  echo "Usage: $0 <file> [<file> ...]" >&2
  exit 1
fi

for f in "$@"; do
  [ -f "$f" ] || continue
  sed -i'' \
    -e 's/ghp_[A-Za-z0-9_]\{36,\}/[REDACTED: GitHub token]/g' \
    -e 's/gho_[A-Za-z0-9_]\{36,\}/[REDACTED: GitHub OAuth token]/g' \
    -e 's/github_pat_[A-Za-z0-9_]\{22,\}/[REDACTED: GitHub PAT]/g' \
    -e 's/sk-[A-Za-z0-9]\{32,\}/[REDACTED: API key]/g' \
    -e 's/AKIA[0-9A-Z]\{16\}/[REDACTED: AWS key]/g' \
    -e 's/nvapi-[A-Za-z0-9_]\{40,\}/[REDACTED: NVIDIA key]/g' \
    -e 's/jwt[-_=][A-Za-z0-9+/=]\{32,\}/[REDACTED: JWT]/g' \
    "$f" || true
done
