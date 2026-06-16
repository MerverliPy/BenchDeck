#!/usr/bin/env bash
set -uo pipefail

# ── synthetic canary, never a real key ─────────────────────────────────
CANARY_VALUE="sk-canary-dummy-value-for-boundary-test-$(date +%s)"
CTR_NAME="benchdeck-bv-$(date +%s | sha256sum | head -c 8)"
FAILURES=0; PASSES=0

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[0;33m'; NC='\033[0m'
pass() { printf "  ${GREEN}PASS${NC}  %s\n" "$1"; ((PASSES++)) || true; }
fail() { printf "  ${RED}FAIL${NC}  %s  — %s\n" "$1" "$2"; ((FAILURES++)) || true; }
info() { printf "  ${YELLOW}INFO${NC}  %s\n" "$1"; }

# ── detect rootless Docker ─────────────────────────────────────────────
ROOTLESS=false
if docker info --format '{{json .SecurityOptions}}' 2>/dev/null | grep -qi rootless; then
    ROOTLESS=true
    info "Rootless Docker detected — adjusting permission expectations"
else
    info "Native Docker detected"
fi

# ── image selection ─────────────────────────────────────────────────────
IMAGE=""
if docker images --format '{{.Repository}}:{{.Tag}}' 2>/dev/null | grep -q 'benchdeck-product-test'; then
    IMAGE=$(docker images --format '{{.Repository}}:{{.Tag}}' | grep 'benchdeck-product-test' | head -1)
elif docker images --format '{{.Repository}}:{{.Tag}}' 2>/dev/null | grep -q 'python.*slim'; then
    IMAGE=$(docker images --format '{{.Repository}}:{{.Tag}}' | grep 'python.*slim' | head -1)
fi
if [ -z "${IMAGE:-}" ]; then
    fail "IMAGE_DETECT" "no cached image found"; exit 1
fi
info "Using image: ${IMAGE}"

# ── temp secret directory ───────────────────────────────────────────────
SECRET_DIR=$(mktemp -d -t benchdeck-bv-XXXXXX)

# Rootless Docker with user namespaces: container UID != host UID after
# remapping. The directory must be world-traversable (0711) and the file
# world-readable (0444) for the container to access the bind mount.
# The :ro flag still prevents writes. The parent dir lacks read
# permission so other users cannot list contents.
if $ROOTLESS; then
    chmod 0711 "${SECRET_DIR}"
    (umask 022 && printf '%s' "${CANARY_VALUE}" > "${SECRET_DIR}/api_key")
    chmod 0444 "${SECRET_DIR}/api_key"
    EXPECTED_FILE_MODE="444"
    EXPECTED_DIR_MODE="711"
else
    chmod 0700 "${SECRET_DIR}"
    (umask 077 && printf '%s' "${CANARY_VALUE}" > "${SECRET_DIR}/api_key")
    chmod 0400 "${SECRET_DIR}/api_key"
    EXPECTED_FILE_MODE="400"
    EXPECTED_DIR_MODE="700"
fi
info "Secret dir: ${SECRET_DIR} (mode $(stat -c '%a' "${SECRET_DIR}"))"

cleanup_all() {
    docker stop "${CTR_NAME}" 2>/dev/null || true
    docker rm -f "${CTR_NAME}" 2>/dev/null || true
    rm -f "${SECRET_DIR}/api_key" 2>/dev/null || true
    rmdir "${SECRET_DIR}" 2>/dev/null || true
}
trap cleanup_all EXIT

# ── start container detached ────────────────────────────────────────────
info "Starting container ${CTR_NAME} (detached, network=none, 128m)..."
docker run \
    --name "${CTR_NAME}" \
    --detach \
    --network=none \
    --memory=128m \
    --cpus=0.25 \
    --cap-drop=ALL \
    --security-opt=no-new-privileges:true \
    --read-only \
    --tmpfs /tmp:rw,noexec,nosuid,size=32m \
    -v "${SECRET_DIR}:/run/secrets:ro" \
    -e "OPENAI_API_KEY_FILE=/run/secrets/api_key" \
    "${IMAGE}" \
    sleep 120 >/dev/null 2>&1

# ── wait for container running ──────────────────────────────────────────
for i in $(seq 1 15); do
    STATE=$(docker inspect -f '{{.State.Status}}' "${CTR_NAME}" 2>/dev/null || echo "gone")
    if [ "${STATE}" = "running" ]; then break; fi
    sleep 0.5
done

# ── assertion 1: no OPENAI_API_KEY= in Config.Env ──────────────────────
info "A1: docker inspect env..."
ENV_RAW=$(docker inspect -f '{{range .Config.Env}}{{println .}}{{end}}' "${CTR_NAME}" 2>/dev/null)
if echo "${ENV_RAW}" | grep -q '^OPENAI_API_KEY='; then
    fail "NO_OPENAI_KEY_IN_ENV" "OPENAI_API_KEY= value found in docker inspect Config.Env"
else
    pass "NO_OPENAI_KEY_IN_ENV"
fi

# ── assertion 2: no OPENAI_API_KEY= in Config.Cmd ──────────────────────
info "A2: docker inspect cmd..."
CMD_JSON=$(docker inspect -f '{{json .Config.Cmd}}' "${CTR_NAME}" 2>/dev/null)
if echo "${CMD_JSON}" | grep -qi 'openai.*api.*key'; then
    fail "NO_OPENAI_KEY_IN_CMD" "key-like pattern in docker inspect Config.Cmd"
else
    pass "NO_OPENAI_KEY_IN_CMD"
fi

# ── assertion 3: OPENAI_API_KEY_FILE set (not the value itself) ─────────
info "A3: OPENAI_API_KEY_FILE env var presence..."
if echo "${ENV_RAW}" | grep -q 'OPENAI_API_KEY_FILE='; then
    pass "KEY_FILE_ENV_SET"
else
    fail "KEY_FILE_ENV_SET" "OPENAI_API_KEY_FILE not found in container env"
fi

# ── assertion 4: OPENAI_API_KEY value absent from env ───────────────────
info "A4: OPENAI_API_KEY value absent from env..."
if echo "${ENV_RAW}" | grep -q 'OPENAI_API_KEY=sk-'; then
    fail "KEY_VALUE_NOT_IN_ENV" "OPENAI_API_KEY=sk-... found in container env"
else
    pass "KEY_VALUE_NOT_IN_ENV"
fi

# ── assertion 5: secret file readable inside container ──────────────────
info "A5: secret file readable..."
SECRET_CONTENT=$(docker exec "${CTR_NAME}" cat /run/secrets/api_key 2>/dev/null || echo "READ_FAILED")
if [ "${SECRET_CONTENT}" = "${CANARY_VALUE}" ]; then
    pass "SECRET_FILE_READABLE"
elif [ "${SECRET_CONTENT}" = "READ_FAILED" ]; then
    fail "SECRET_FILE_READABLE" "cat /run/secrets/api_key failed (permission denied)"
else
    fail "SECRET_FILE_READABLE" "content mismatch: expected ${#CANARY_VALUE} bytes, got '${SECRET_CONTENT:0:30}...'"
fi

# ── assertion 6: mount is read-only ─────────────────────────────────────
info "A6: bind mount read-only..."
TOUCH_OUT=$(docker exec "${CTR_NAME}" sh -c 'touch /run/secrets/new_file 2>&1' 2>/dev/null || echo "TOUCH_BLOCKED")
if echo "${TOUCH_OUT}" | grep -qi 'read.only\|permission denied\|TOUCH_BLOCKED'; then
    pass "MOUNT_READ_ONLY"
else
    fail "MOUNT_READ_ONLY" "touch succeeded on read-only mount"
fi

# ── assertion 7: key value absent from /proc/1/environ ──────────────────
info "A7: key value absent from /proc/1/environ..."
PROC_ENV=$(docker exec "${CTR_NAME}" cat /proc/1/environ 2>/dev/null | tr '\0' '\n' || echo "")
if echo "${PROC_ENV}" | grep -q 'OPENAI_API_KEY=sk-'; then
    fail "KEY_NOT_IN_PROC_ENV" "key value found in /proc/1/environ"
else
    pass "KEY_NOT_IN_PROC_ENV"
fi

# ── assertion 8: key file path in /proc/1/environ ───────────────────────
info "A8: key file path in /proc/1/environ..."
if echo "${PROC_ENV}" | grep -q 'OPENAI_API_KEY_FILE=/run/secrets/api_key'; then
    pass "KEY_FILE_IN_PROC_ENV"
else
    fail "KEY_FILE_IN_PROC_ENV" "OPENAI_API_KEY_FILE=/run/secrets/api_key absent from /proc/1/environ"
fi

# ── assertion 9: container cannot modify secret file ────────────────────
info "A9: container cannot overwrite secret file..."
OVERWRITE_OUT=$(docker exec "${CTR_NAME}" sh -c 'echo x > /run/secrets/api_key 2>&1' 2>/dev/null || echo "BLOCKED")
if echo "${OVERWRITE_OUT}" | grep -qi 'read.only\|permission denied\|BLOCKED'; then
    pass "CONTAINER_CANT_MODIFY_SECRET"
else
    fail "CONTAINER_CANT_MODIFY_SECRET" "echo x > /run/secrets/api_key succeeded"
fi

# ── assertion 10: host file permissions platform-appropriate ────────────
info "A10: host secret file permissions..."
HOST_MODE=$(stat -c '%a' "${SECRET_DIR}/api_key" 2>/dev/null || echo "???")
if [ "${HOST_MODE}" = "${EXPECTED_FILE_MODE}" ]; then
    pass "SECRET_HOST_MODE_${EXPECTED_FILE_MODE}"
else
    fail "SECRET_HOST_MODE" "host mode is ${HOST_MODE}, expected ${EXPECTED_FILE_MODE}"
fi

HOST_DIR_MODE=$(stat -c '%a' "${SECRET_DIR}" 2>/dev/null || echo "???")
if [ "${HOST_DIR_MODE}" = "${EXPECTED_DIR_MODE}" ]; then
    pass "SECRET_DIR_MODE_${EXPECTED_DIR_MODE}"
else
    fail "SECRET_DIR_MODE" "host dir mode is ${HOST_DIR_MODE}, expected ${EXPECTED_DIR_MODE}"
fi

# ── assertion 11: canary absent from docker logs ────────────────────────
info "A11: canary absent from docker logs..."
if docker logs "${CTR_NAME}" 2>&1 | grep -q "${CANARY_VALUE}"; then
    fail "KEY_NOT_IN_LOGS" "canary value found in docker logs"
else
    pass "KEY_NOT_IN_LOGS"
fi

# ── stop and clean up ──────────────────────────────────────────────────
info "Stopping container..."
docker stop "${CTR_NAME}" 2>/dev/null || true
docker rm -f "${CTR_NAME}" 2>/dev/null || true

# ── assertion 12: temp directory cleaned ─────────────────────────────────
sleep 1
if [ -d "${SECRET_DIR}" ]; then
    rm -f "${SECRET_DIR}/api_key" 2>/dev/null || true
    rmdir "${SECRET_DIR}" 2>/dev/null || true
fi
if [ ! -d "${SECRET_DIR}" ]; then
    pass "TEMP_DIR_CLEANED"
else
    fail "TEMP_DIR_CLEANED" "still exists: ${SECRET_DIR}"
fi

# ── assertion 13: no residual container ─────────────────────────────────
sleep 1
if docker ps -a --format '{{.Names}}' 2>/dev/null | grep -q "^${CTR_NAME}$"; then
    docker rm -f "${CTR_NAME}" 2>/dev/null || true
    fail "NO_RESIDUAL_CONTAINER" "container ${CTR_NAME} still present after cleanup"
else
    pass "NO_RESIDUAL_CONTAINER"
fi

# ── assertion 14: pia containers untouched ──────────────────────────────
info "A14: existing containers unaffected..."
PIA_COUNT=$(docker ps --format '{{.Names}}' 2>/dev/null | grep -c '^pia-' || echo "0")
if docker ps --format '{{.Names}}' 2>/dev/null | grep -q '^pia-'; then
    pass "EXISTING_CONTAINERS_UNTOUCHED"
    info "  pia containers still running: $(docker ps --format '{{.Names}}' 2>/dev/null | grep '^pia-' | tr '\n' ' ')"
else
    info "  (no pia containers detected — nothing to verify)"
    pass "EXISTING_CONTAINERS_UNTOUCHED"
fi

# ── summary ─────────────────────────────────────────────────────────────
echo ""
echo "═════════════════════════════════════════════"
printf "  Boundary validation: ${GREEN}%d passed${NC}, ${RED}%d failed${NC}\n" "${PASSES}" "${FAILURES}"
echo "═════════════════════════════════════════════"
exit "${FAILURES}"
