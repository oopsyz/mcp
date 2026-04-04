#!/bin/bash
set -e

echo "Starting CLI Service Registry..."
uv run registry-server
