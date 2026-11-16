#!/usr/bin/env bash

# Append a timestamped line count of a CSV file to a log file.
# Also includes the CSV file's last modified time (mtime) in ISO-8601 UTC.
#
# Usage:
#   ./append_csv_linecount.sh [CSV_FILE] [LOG_FILE]
#
# Defaults:
#   - CSV_FILE: latest file matching logs/cell_power_changes_*.csv (by mtime)
#   - LOG_FILE: count_csv.log

set -euo pipefail

csv_file="${1:-}"
log_file="${2:-count_csv.log}"

if [[ -z "${csv_file}" ]]; then
  # Find the most recent matching CSV in logs/
  # Use nullglob to avoid literal pattern if no match
  shopt -s nullglob
  files=(logs/cell_power_changes_*.csv)
  shopt -u nullglob

  if (( ${#files[@]} == 0 )); then
    echo "Error: no CSV provided and no files match logs/cell_power_changes_*.csv" >&2
    exit 1
  fi

  # Sort by modification time descending and pick the first
  # shellcheck disable=SC2207
  files_sorted=($(ls -1t -- "${files[@]}"))
  csv_file="${files_sorted[0]}"
fi

if [[ ! -f "${csv_file}" ]]; then
  echo "Error: CSV file not found: ${csv_file}" >&2
  exit 1
fi

# Ensure log directory/file exists (create file if missing)
touch -- "${log_file}"

# Compute the file's last modification time (mtime) in ISO-8601 UTC
file_epoch=$(stat -c %Y -- "${csv_file}")
file_mtime=$(date -u -Is -d "@${file_epoch}")

# Build the line to append: current timestamp (ISO-8601), line count, file path, and file mtime
appended_line=$(printf '%s | lines=%s | file=%s | updated=%s' \
  "$(date -Is)" \
  "$(wc -l < "${csv_file}")" \
  "${csv_file}" \
  "${file_mtime}")

# Append to log and also print the exact line to stdout
echo "${appended_line}" >> "${log_file}"
echo "${appended_line}"

# Also print the last line of the CSV file for quick inspection
last_csv_line=$(tail -n 1 -- "${csv_file}")
echo "${last_csv_line}"
