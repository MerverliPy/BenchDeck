#!/usr/bin/env bash
set -euo pipefail

GIT_TAG="${GITHUB_REF:-}"
PKG_VERSION=""

if command -v python3 &>/dev/null; then
  PKG_VERSION="$(python3 -c "
import tomllib
with open('pyproject.toml', 'rb') as f:
    data = tomllib.load(f)
print(data['project']['version'])
")"
else
  echo "ERROR: python3 not available for version extraction" >&2
  exit 1
fi

if [ -z "${GIT_TAG}" ] || [ "${GIT_TAG}" = "refs/heads/main" ] || [ "${GIT_TAG}" = "refs/heads/master" ]; then
  echo "No release tag (GITHUB_REF=${GIT_TAG:-unset}). Skipping version match."
  echo "pyproject.toml version: ${PKG_VERSION}"
  exit 0
fi

TAG_VERSION="${GIT_TAG#refs/tags/}"
TAG_VERSION="${TAG_VERSION#v}"

if [ "${TAG_VERSION}" != "${PKG_VERSION}" ]; then
  echo "ERROR: Git tag version '${TAG_VERSION}' does not match pyproject.toml version '${PKG_VERSION}'" >&2
  echo "Update pyproject.toml version to match the tag before publishing." >&2
  exit 1
fi

echo "Version match: tag v${TAG_VERSION} == pyproject.toml ${PKG_VERSION}"
