#!/bin/bash
# BTS Reporting Carrier on-time performance bulk downloader.
#
# Runs as an EMR step on the cluster master node — downloads each
# monthly zip directly from BTS, uploads the inner CSV to S3 under
# year=YYYY/month=MM/, and cleans up local disk between months.
# Doing this from the cluster (rather than from a laptop) is dramatically
# faster because EC2-to-S3 throughput within the same region is multi-Gbps.
#
# Usage: download_bts.sh [START_YEAR] [END_YEAR]
#   defaults: 2021 2023
#
# Skips months that 404 or return an HTML error page; logs and continues.

set -u

START_YEAR=${1:-2021}
END_YEAR=${2:-2023}
S3_PREFIX=${S3_PREFIX:-s3://flightdelay-raw/bts}
TMP=/tmp/bts_download
mkdir -p "$TMP"

# Amazon Linux 2023 EMR AMIs ship without unzip; install if missing.
if ! command -v unzip >/dev/null 2>&1; then
  echo "[$(date -Is)] installing unzip"
  sudo dnf install -y unzip >/dev/null
fi

echo "[$(date -Is)] starting BTS bulk download: ${START_YEAR}..${END_YEAR}"

ok=0
fail=0

for year in $(seq "$START_YEAR" "$END_YEAR"); do
  for month in $(seq 1 12); do
    name="On_Time_Reporting_Carrier_On_Time_Performance_1987_present_${year}_${month}.zip"
    url="https://transtats.bts.gov/PREZIP/${name}"
    zip_path="${TMP}/${name}"

    echo "[$(date -Is)] [${year}-${month}] downloading"
    if ! curl -L -s -f -o "$zip_path" "$url"; then
      echo "[${year}-${month}] download failed (HTTP error)"
      rm -f "$zip_path"
      fail=$((fail + 1))
      continue
    fi

    size=$(stat -c%s "$zip_path" 2>/dev/null || echo 0)
    if [ "$size" -lt 1000000 ]; then
      echo "[${year}-${month}] file too small (${size} bytes) — likely an HTML error page"
      rm -f "$zip_path"
      fail=$((fail + 1))
      continue
    fi

    extract_dir="${TMP}/extracted_${year}_${month}"
    rm -rf "$extract_dir"
    mkdir -p "$extract_dir"
    if ! unzip -q "$zip_path" -d "$extract_dir"; then
      echo "[${year}-${month}] unzip failed"
      rm -rf "$zip_path" "$extract_dir"
      fail=$((fail + 1))
      continue
    fi

    csv=$(find "$extract_dir" -maxdepth 2 -name '*.csv' -print -quit)
    if [ -z "$csv" ]; then
      echo "[${year}-${month}] no CSV in extracted folder"
      rm -rf "$zip_path" "$extract_dir"
      fail=$((fail + 1))
      continue
    fi

    month_pad=$(printf '%02d' "$month")
    s3_path="${S3_PREFIX}/year=${year}/month=${month_pad}/${year}_${month}.csv"
    csv_size_mb=$(du -m "$csv" | cut -f1)

    echo "[$(date -Is)] [${year}-${month}] uploading ${csv_size_mb}MB to ${s3_path}"
    if ! aws s3 cp "$csv" "$s3_path" --quiet; then
      echo "[${year}-${month}] upload failed"
      rm -rf "$zip_path" "$extract_dir"
      fail=$((fail + 1))
      continue
    fi

    rm -rf "$zip_path" "$extract_dir"
    ok=$((ok + 1))
    echo "[$(date -Is)] [${year}-${month}] OK  (uploaded=${ok}, failed=${fail})"
  done
done

echo "[$(date -Is)] DONE: uploaded=${ok}, failed=${fail}"
# Exit non-zero if zero months succeeded so EMR marks the step failed
if [ "$ok" -eq 0 ]; then
  exit 1
fi
