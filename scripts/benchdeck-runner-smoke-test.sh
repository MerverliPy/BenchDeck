#!/usr/bin/env bash
# Smoke test for the benchdeck-product-test self-hosted runner.
# Verifies the boundary the workflow asserts:
#   1. docker daemon reachable
#   2. rootless mode reported in docker info
#   3. jq installed
#   4. a disposable container with hard boundaries (non-root, no docker.sock, no network)
#      can be created, runs the boundary assertions, and is cleaned up
#
# Exits 0 only if all four pass. Designed to be safe to run repeatedly; pulls
# alpine:3.19 only on first use and reuses the cached image afterwards.

set -euo pipefail

# Rootless Docker wiring. The actual socket is at /run/user/<uid>/docker.sock
# when the systemd user manager is running, but the dockerd-rootless-setuptool's
# 'rootless' context points at the fallback path (which is stale). Set explicitly.
export XDG_RUNTIME_DIR=/run/user/$(id -u)
export DOCKER_HOST=unix:///run/user/$(id -u)/docker.sock

pass=0
fail=0
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

step() { printf '\n=== %s ===\n' "$1"; }
ok()   { printf '  \033[32m✓\033[0m %s\n' "$1"; pass=$((pass+1)); }
ko()   { printf '  \033[31m✗\033[0m %s\n' "$1" >&2; fail=$((fail+1)); }

step "1. docker reachable"
if docker info >/dev/null 2>&1; then
  ok "docker info succeeded"
else
  ko "docker info failed (is the rootless daemon running? Try: systemctl --user start docker)"
fi

step "2. rootless mode reported"
if docker info --format '{{json .SecurityOptions}}' 2>/dev/null | grep -qi rootless; then
  ok "rootless in SecurityOptions (workflow gate will pass)"
else
  ko "rootless NOT in SecurityOptions (workflow 'Verify controlled runner boundary' will fail)"
fi

step "3. jq installed (required by workflow step 2)"
if command -v jq >/dev/null; then
  ok "jq at $(command -v jq) ($(jq --version))"
else
  ko "jq not found (install with: sudo apt-get install -y jq)"
fi

step "4. disposable container with hard boundaries"
test_img="docker.io/library/alpine:3.19"
test_name="benchdeck-runner-smoke-$$"

# Pull only if not cached (idempotent; cheap)
if ! docker image inspect "$test_img" >/dev/null 2>&1; then
  echo "  pulling $test_img (one-time)..."
  docker pull -q "$test_img" >/dev/null
fi

# Boundary assertions: non-root, no docker socket, no network egress.
# The wget probe is best-effort: a 1-second timeout means we only fail if
# the network is genuinely open. A clean network (block on egress) lets
# wget fail fast; the whole assertion still completes in ~1s.
inner='set -e
  uid="$(id -u)"
  if [ "$uid" = "0" ]; then echo "BOUNDARY FAIL: container is root (uid=$uid)"; exit 10; fi
  if [ -S /var/run/docker.sock ]; then echo "BOUNDARY FAIL: docker.sock present"; exit 11; fi
  if wget -qO- --timeout=1 https://1.1.1.1/ >/dev/null 2>&1; then
    echo "BOUNDARY FAIL: external network reachable (1.1.1.1:443)"
    exit 12
  fi
  echo "  inner uid=$uid, no docker.sock, no external network"
  exit 0'

set +e
docker run --rm --name "$test_name" \
  --cap-drop=ALL \
  --security-opt no-new-privileges:true \
  --read-only \
  --network=none \
  --user 1000:1000 \
  --tmpfs /tmp:rw,noexec,nosuid,size=32m \
  "$test_img" \
  sh -c "$inner" >/tmp/benchdeck-runner-smoke-inner.$$ 2>&1
rc=$?
set -e
inner_output="$(cat /tmp/benchdeck-runner-smoke-inner.$$ 2>/dev/null || true)"
rm -f /tmp/benchdeck-runner-smoke-inner.$$

if [ "$rc" -eq 0 ]; then
  ok "non-root, no docker socket, no network egress (3/3 boundary checks)"
elif [ "$rc" -eq 10 ]; then
  ko "container ran as root: $inner_output"
elif [ "$rc" -eq 11 ]; then
  ko "container had docker.sock mounted: $inner_output"
elif [ "$rc" -eq 12 ]; then
  ko "container reached external network (rootless network= isolation broken): $inner_output"
else
  ko "boundary check failed (exit $rc): $inner_output"
fi

# Defensive: if the container wasn't removed by --rm, clean it up.
docker rm -f "$test_name" >/dev/null 2>&1 || true

step "summary"
printf '  passed: %d\n  failed: %d\n' "$pass" "$fail"
if [ "$fail" -gt 0 ]; then
  printf '\n\033[31mbenchdeck-runner smoke test FAILED\033[0m\n' >&2
  exit 1
fi
printf '\n\033[32mbenchdeck-runner smoke test PASSED\033[0m\n'
exit 0
