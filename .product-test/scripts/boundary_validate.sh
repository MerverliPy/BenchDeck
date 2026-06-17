#!/usr/bin/env bash
set -uo pipefail

# Synthetic canary only. This script never reads a real provider credential.
CANARY_VALUE="BENCHDECK_CANARY_NOT_A_REAL_SECRET_7f3a-$(date +%s)"
CTR_NAME="benchdeck-bv-$(printf '%s' "$$-$(date +%s%N)" | sha256sum | head -c 8)"
FAILURES=0
PASSES=0
UID_VALUE="$(id -u)"
GID_VALUE="$(id -g)"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[0;33m'; NC='\033[0m'
pass() { printf "  ${GREEN}PASS${NC}  %s\n" "$1"; ((PASSES++)) || true; }
fail() { printf "  ${RED}FAIL${NC}  %s  — %s\n" "$1" "$2"; ((FAILURES++)) || true; }
info() { printf "  ${YELLOW}INFO${NC}  %s\n" "$1"; }

IMAGE=""
if docker images --format '{{.Repository}}:{{.Tag}}' 2>/dev/null | grep -q 'benchdeck-product-test'; then
    IMAGE=$(docker images --format '{{.Repository}}:{{.Tag}}' | grep 'benchdeck-product-test' | head -1)
elif docker images --format '{{.Repository}}:{{.Tag}}' 2>/dev/null | grep -q 'python.*slim'; then
    IMAGE=$(docker images --format '{{.Repository}}:{{.Tag}}' | grep 'python.*slim' | head -1)
fi
if [ -z "${IMAGE:-}" ]; then
    fail "IMAGE_DETECT" "no cached image found"
    exit 1
fi
info "Using image: ${IMAGE}"

SECRET_DIR=$(mktemp -d -t benchdeck-bv-XXXXXX)
chmod 0700 "${SECRET_DIR}"
(umask 077 && printf '%s' "${CANARY_VALUE}" > "${SECRET_DIR}/api_key")
chmod 0400 "${SECRET_DIR}/api_key"

cleanup_all() {
    docker rm -f "${CTR_NAME}" >/dev/null 2>&1 || true
    rm -f "${SECRET_DIR}/api_key" >/dev/null 2>&1 || true
    rmdir "${SECRET_DIR}" >/dev/null 2>&1 || true
}
trap cleanup_all EXIT

info "Creating container ${CTR_NAME} with an in-container tmpfs secret store..."
if ! docker create \
    --name "${CTR_NAME}" \
    --network=none \
    --user "${UID_VALUE}:${GID_VALUE}" \
    --memory=128m \
    --cpus=0.25 \
    --cap-drop=ALL \
    --security-opt=no-new-privileges:true \
    --read-only \
    --tmpfs /tmp:rw,noexec,nosuid,nodev,size=32m,mode=0700 \
    --tmpfs "/run/secrets:rw,noexec,nosuid,nodev,size=64k,mode=0700,uid=${UID_VALUE},gid=${GID_VALUE}" \
    -e "OPENAI_API_KEY_FILE=/run/secrets/api_key" \
    "${IMAGE}" \
    sleep 120 >/dev/null 2>&1; then
    fail "CONTAINER_CREATE" "docker create failed"
    exit 1
fi

if ! docker start "${CTR_NAME}" >/dev/null 2>&1; then
    fail "CONTAINER_START" "docker start failed"
    exit 1
fi

if ! docker exec -i --user "${UID_VALUE}:${GID_VALUE}" "${CTR_NAME}" \
    sh -c 'umask 077; cat > /run/secrets/api_key; chmod 0400 /run/secrets/api_key' \
    < "${SECRET_DIR}/api_key" >/dev/null 2>&1; then
    fail "SECRET_STREAM" "docker exec stdin transport into tmpfs failed"
    exit 1
fi
pass "SECRET_STREAM"

ENV_RAW=$(docker inspect -f '{{range .Config.Env}}{{println .}}{{end}}' "${CTR_NAME}" 2>/dev/null)
CMD_JSON=$(docker inspect -f '{{json .Config.Cmd}}' "${CTR_NAME}" 2>/dev/null)

if echo "${ENV_RAW}" | grep -q '^OPENAI_API_KEY='; then
    fail "NO_OPENAI_KEY_IN_ENV" "credential value variable found in Config.Env"
else
    pass "NO_OPENAI_KEY_IN_ENV"
fi

if echo "${CMD_JSON}" | grep -Fq "${CANARY_VALUE}"; then
    fail "NO_KEY_IN_CMD" "canary found in Config.Cmd"
else
    pass "NO_KEY_IN_CMD"
fi

if echo "${ENV_RAW}" | grep -q '^OPENAI_API_KEY_FILE=/run/secrets/api_key$'; then
    pass "KEY_FILE_ENV_SET"
else
    fail "KEY_FILE_ENV_SET" "OPENAI_API_KEY_FILE path absent"
fi

SECRET_CONTENT=$(docker exec --user "${UID_VALUE}:${GID_VALUE}" "${CTR_NAME}" \
    cat /run/secrets/api_key 2>/dev/null || echo "READ_FAILED")
if [ "${SECRET_CONTENT}" = "${CANARY_VALUE}" ]; then
    pass "SECRET_FILE_READABLE"
else
    fail "SECRET_FILE_READABLE" "runtime user could not read the streamed canary"
fi

CONTAINER_MODE=$(docker exec --user "${UID_VALUE}:${GID_VALUE}" "${CTR_NAME}" \
    stat -c '%a' /run/secrets/api_key 2>/dev/null || echo "???")
if [ "${CONTAINER_MODE}" = "400" ]; then
    pass "SECRET_CONTAINER_MODE_400"
else
    fail "SECRET_CONTAINER_MODE" "container mode is ${CONTAINER_MODE}, expected 400"
fi

OVERWRITE_OUT=$(docker exec --user "${UID_VALUE}:${GID_VALUE}" "${CTR_NAME}" \
    sh -c 'printf x > /run/secrets/api_key 2>&1' 2>&1 || echo "BLOCKED")
if echo "${OVERWRITE_OUT}" | grep -qi 'permission denied\|read.only\|BLOCKED'; then
    pass "RUNTIME_USER_CANT_MODIFY_SECRET"
else
    fail "RUNTIME_USER_CANT_MODIFY_SECRET" "runtime user overwrote the secret file"
fi

PROC_ENV=$(docker exec --user "${UID_VALUE}:${GID_VALUE}" "${CTR_NAME}" \
    cat /proc/1/environ 2>/dev/null | tr '\0' '\n' || echo "")
if echo "${PROC_ENV}" | grep -Fq "${CANARY_VALUE}"; then
    fail "KEY_NOT_IN_PROC_ENV" "canary found in /proc/1/environ"
else
    pass "KEY_NOT_IN_PROC_ENV"
fi

HOST_MODE=$(stat -c '%a' "${SECRET_DIR}/api_key" 2>/dev/null || echo "???")
HOST_DIR_MODE=$(stat -c '%a' "${SECRET_DIR}" 2>/dev/null || echo "???")
if [ "${HOST_MODE}" = "400" ]; then pass "SECRET_HOST_MODE_400"; else fail "SECRET_HOST_MODE" "${HOST_MODE}"; fi
if [ "${HOST_DIR_MODE}" = "700" ]; then pass "SECRET_DIR_MODE_700"; else fail "SECRET_DIR_MODE" "${HOST_DIR_MODE}"; fi

if docker inspect -f '{{json .Mounts}}' "${CTR_NAME}" 2>/dev/null | grep -Fq "${SECRET_DIR}"; then
    fail "NO_HOST_SECRET_BIND" "host secret directory appears in container mounts"
else
    pass "NO_HOST_SECRET_BIND"
fi

if docker logs "${CTR_NAME}" 2>&1 | grep -Fq "${CANARY_VALUE}"; then
    fail "KEY_NOT_IN_LOGS" "canary found in container logs"
else
    pass "KEY_NOT_IN_LOGS"
fi

docker rm -f "${CTR_NAME}" >/dev/null 2>&1 || true
rm -f "${SECRET_DIR}/api_key" >/dev/null 2>&1 || true
rmdir "${SECRET_DIR}" >/dev/null 2>&1 || true

if [ ! -d "${SECRET_DIR}" ]; then pass "TEMP_DIR_CLEANED"; else fail "TEMP_DIR_CLEANED" "still exists"; fi
if docker ps -a --format '{{.Names}}' 2>/dev/null | grep -q "^${CTR_NAME}$"; then
    fail "NO_RESIDUAL_CONTAINER" "container remains"
else
    pass "NO_RESIDUAL_CONTAINER"
fi

echo
echo "═════════════════════════════════════════════"
printf "  Boundary validation: ${GREEN}%d passed${NC}, ${RED}%d failed${NC}\n" "${PASSES}" "${FAILURES}"
echo "═════════════════════════════════════════════"
exit "${FAILURES}"
