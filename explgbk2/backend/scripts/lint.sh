#!/usr/bin/env bash

set -e
set -x

uv run pyrefly check app
uv run ruff check app
uv run ruff format app --check
