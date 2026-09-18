#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
ASSETS_DIR="$SCRIPT_DIR/app/src/main/assets"

mkdir -p "$ASSETS_DIR"

if [ -f "$REPO_DIR/geodata/opentopomap_ale_lilla_edet.mbtiles" ]; then
    cp "$REPO_DIR/geodata/opentopomap_ale_lilla_edet.mbtiles" "$ASSETS_DIR/"
    echo "Kopierade opentopomap_ale_lilla_edet.mbtiles till assets."
fi

if [ -f "$REPO_DIR/geodata/forest_inspection.bin" ]; then
    cp "$REPO_DIR/geodata/forest_inspection.bin" "$ASSETS_DIR/"
    echo "Kopierade forest_inspection.bin till assets."
fi
