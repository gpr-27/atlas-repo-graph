#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
sed -i.bak 's/customer_id/account_id/g' backend/app.py backend/openapi.yaml backend/tests/test_app.py web/profile.py
rm -f backend/*.bak backend/tests/*.bak web/*.bak
echo "renamed customer_id -> account_id in backend and web (billing and analytics untouched)"
