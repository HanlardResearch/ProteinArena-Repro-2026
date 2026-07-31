#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 4 ]]; then
  echo "usage: $0 CANDIDATES_FASTA HISTORICAL_FASTA OUTPUT_TSV TMP_DIR" >&2
  exit 2
fi

candidates=$1
historical=$2
output=$3
tmp_dir=$4

command -v mmseqs >/dev/null || { echo "mmseqs is required" >&2; exit 127; }
[[ -f "$candidates" ]] || { echo "missing candidates FASTA: $candidates" >&2; exit 2; }
[[ -f "$historical" ]] || { echo "missing historical FASTA: $historical" >&2; exit 2; }

mkdir -p "$tmp_dir"
mmseqs easy-search "$candidates" "$historical" "$output" "$tmp_dir" \
  --format-output query,target,fident \
  --max-seqs 1000000 \
  -s 7.5

if command -v shasum >/dev/null; then
  candidates_sha=$(shasum -a 256 "$candidates" | awk '{print $1}')
  historical_sha=$(shasum -a 256 "$historical" | awk '{print $1}')
else
  candidates_sha=$(sha256sum "$candidates" | awk '{print $1}')
  historical_sha=$(sha256sum "$historical" | awk '{print $1}')
fi
version=$(mmseqs version | head -1)
marker="${output}.complete.json"
printf '{\n  "status": "complete",\n  "candidates_sha256": "%s",\n  "historical_sha256": "%s",\n  "mmseqs_version": "%s",\n  "sensitivity": 7.5,\n  "coverage_policy": "not specified by paper; no explicit coverage threshold in this run"\n}\n' \
  "$candidates_sha" "$historical_sha" "$version" > "$marker"

echo "Wrote $output and verified completion marker $marker."
