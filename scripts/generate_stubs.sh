#!/bin/sh
# Regenerate rtree/_core.pyi from the compiled extension.
#
# Run after changing src/_core.cpp, against an installed build:
#   pip install . && sh scripts/generate_stubs.sh
set -e
OUT=$(mktemp -d)
cd "$OUT"
python -m pybind11_stubgen rtree._core -o "$OUT" --numpy-array-use-type-var
cd - > /dev/null
STUB="$(dirname "$0")/../rtree/_core.pyi"
cp "$OUT/rtree/_core.pyi" "$STUB"
# Build-dependent constants: declare the type, not the value of this build.
sed -i.bak \
  -e 's/^SIDX_VERSION_COMPILED: tuple = .*/SIDX_VERSION_COMPILED: tuple[int, int, int]/' \
  -e 's/^HAS_ARRAY_API: bool = .*/HAS_ARRAY_API: bool/' \
  -e 's/^HAS_CONTAINS: bool = .*/HAS_CONTAINS: bool/' "$STUB"
rm -f "$STUB.bak"
ruff format -q "$STUB" 2>/dev/null || true
ruff check --fix -q "$STUB" > /dev/null 2>&1 || true
echo "wrote rtree/_core.pyi"
