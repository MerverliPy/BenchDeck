#!/usr/bin/env bash
set -euo pipefail

EXPECTED_VERSION="$1"
ERRORS=0

verify_wheel() {
  local wheel
  wheel="$(ls dist/*.whl 2>/dev/null | head -1)"
  if [ -z "${wheel}" ]; then
    echo "ERROR: No .whl found in dist/" >&2
    return 1
  fi
  local actual
  actual="$(unzip -p "${wheel}" '*.dist-info/METADATA' | grep '^Version:' | awk '{print $2}' | tr -d '[:space:]')"
  if [ "${actual}" != "${EXPECTED_VERSION}" ]; then
    echo "ERROR: Wheel METADATA Version '${actual}' != expected '${EXPECTED_VERSION}'" >&2
    return 1
  fi
  echo "Wheel ${wheel}: Version ${actual} OK"
}

verify_sdist() {
  local sdist
  sdist="$(ls dist/*.tar.gz 2>/dev/null | head -1)"
  if [ -z "${sdist}" ]; then
    echo "ERROR: No .tar.gz found in dist/" >&2
    return 1
  fi
  local actual
  actual="$(tar -xOzPf "${sdist}" --wildcards '*/PKG-INFO' 2>/dev/null | grep '^Version:' | awk '{print $2}' | tr -d '[:space:]')"
  if [ "${actual}" != "${EXPECTED_VERSION}" ]; then
    echo "ERROR: Sdist PKG-INFO Version '${actual}' != expected '${EXPECTED_VERSION}'" >&2
    return 1
  fi
  echo "Sdist ${sdist}: Version ${actual} OK"
}

verify_wheel || ERRORS=$((ERRORS + 1))
verify_sdist || ERRORS=$((ERRORS + 1))

if [ "${ERRORS}" -gt 0 ]; then
  echo "ERROR: ${ERRORS} build metadata verification failure(s)" >&2
  exit 1
fi

echo "Build metadata verification: PASS (version ${EXPECTED_VERSION})"
