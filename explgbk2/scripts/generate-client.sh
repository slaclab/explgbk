#! /usr/bin/env bash

set -e
set -x

cd backend
uv run python -c "import app.main; import json; print(json.dumps(app.main.app.openapi()))" > ../openapi.json
cd ..
mv openapi.json frontend/
# Ensure hook environments have workspace binaries available from the pinned lockfile.
[ -d "frontend/node_modules" ] || bun install --frozen-lockfile
bun run --filter frontend generate-client
bun run lint
