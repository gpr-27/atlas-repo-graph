#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
export ATLAS_DB=./atlas.db
echo "## 1. scan";      atlas scan backend billing web analytics
echo "## 2. impact";    atlas impact customer_id
echo "## 3. change";    ./apply_rename.sh
echo "## 4. rescan";    atlas scan backend billing web analytics
echo "## 5. verify";    atlas verify customer_id --renamed-to account_id --run-tests || true
./reset.sh
