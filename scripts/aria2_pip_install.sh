#!/bin/bash
# aria2c-assisted pip install for large packages on unreliable networks
# Usage: bash aria2_pip_install.sh <venv_path> <package> [mirror_url]
set -e

VENV="$1"
PKG="$2"
MIRROR="${3:-https://mirrors.aliyun.com/pypi/simple/}"
WDIR="/tmp/wheels_$(basename $VENV)"
PIP="$VENV/bin/pip"
PYTHON="$VENV/bin/python"

mkdir -p "$WDIR"

echo "=== [1] pip download: $PKG (with retry) ==="
rm -rf "$WDIR"/*

for i in 1 2 3 4 5; do
    echo "--- download attempt $i ---"
    if $PIP download "$PKG" -d "$WDIR" -i "$MIRROR" --trusted-host mirrors.aliyun.com --timeout 300 --retries 5 2>&1; then
        echo "--- download succeeded on attempt $i ---"
        break
    fi
    echo "--- attempt $i failed, cleaning partial files and retrying ---"
    # Remove files that might be incomplete (less than 1MB = likely truncated)
    find "$WDIR" -type f -size -1M -delete 2>/dev/null || true
    sleep 10
done

echo "=== [2] aria2c re-download for any failed/incomplete wheels ==="
# Collect URLs for packages that failed to download properly
# Re-run pip download in verbose mode to capture URLs of missing packages
FAILED_URLS=""
$PIP download "$PKG" -d "$WDIR" -i "$MIRROR" --trusted-host mirrors.aliyun.com --timeout 30 2>&1 | while IFS= read -r line; do
    if echo "$line" | grep -qi "error\|failed\|Connection broken\|IncompleteRead"; then
        # Try to extract URL from error line
        url=$(echo "$line" | grep -oP 'https?://[^\s]+' | head -1)
        if [ -n "$url" ]; then
            FAILED_URLS="$FAILED_URLS\n$url"
        fi
    fi
done || true

if [ -n "$FAILED_URLS" ]; then
    echo "--- aria2c downloading failed URLs ---"
    URL_FILE="/tmp/aria2_urls_$(basename $VENV).txt"
    echo -e "$FAILED_URLS" > "$URL_FILE"
    aria2c -x 16 -s 16 -k 1M -t 300 --max-tries=5 -d "$WDIR" -i "$URL_FILE" 2>&1 || true
fi

# Also aria2c re-download any suspiciously small wheel files
# by re-resolving the full dependency list
echo "=== [3] Final aria2c bulk download of all required wheels ==="
# Get the list of all required package URLs from pip
$PIP install "$PKG" --dry-run --ignore-installed --report /tmp/pip_report_$(basename $VENV).json -i "$MIRROR" --trusted-host mirrors.aliyun.com 2>/dev/null || true

# Parse the JSON report to get download URLs
if [ -f "/tmp/pip_report_$(basename $VENV).json" ]; then
    ALL_URLS="/tmp/aria2_all_urls_$(basename $VENV).txt"
    $PYTHON -c "
import json
with open('/tmp/pip_report_$(basename $VENV).json') as f:
    data = json.load(f)
urls = []
for item in data.get('install', []):
    md = item.get('metadata', {})
    dl = item.get('download_info', {})
    if dl and dl.get('url'):
        urls.append(dl['url'])
    elif md.get('name'):
        # Construct PyPI URL
        name = md['name'].replace('-', '_')
        version = md.get('version', '')
        urls.append(f'https://mirrors.aliyun.com/pypi/packages/{name}-{version}.tar.gz')
for u in urls:
    print(u)
" > "$ALL_URLS" 2>/dev/null || true

    # Filter out already downloaded files
    if [ -f "$ALL_URLS" ] && [ -s "$ALL_URLS" ]; then
        aria2c -x 16 -s 16 -k 1M -t 300 --max-tries=5 -d "$WDIR" -i "$ALL_URLS" --auto-file-renaming=false 2>&1 || true
    fi
fi

echo "=== [4] pip install from local wheels ==="
$PIP install --no-index --find-links "$WDIR" "$PKG" 2>&1 || {
    echo "=== Fallback: direct pip install with aria2c not possible, using pip directly ==="
    $PIP install "$PKG" -i "$MIRROR" --trusted-host mirrors.aliyun.com --timeout 300 --retries 5 2>&1
}

echo "=== Done: $PKG ==="
