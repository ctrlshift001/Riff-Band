#!/usr/bin/env sh
set -eu

DEPLOYMENT_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ENV_FILE="$DEPLOYMENT_ROOT/.env.competition"
COMPOSE_FILE="$DEPLOYMENT_ROOT/docker-compose.yml"
IMAGE_ARCHIVE="$DEPLOYMENT_ROOT/ai4ms-workbench.tar"
CHECKSUM_FILE="$DEPLOYMENT_ROOT/SHA256SUMS.txt"
IMAGE_TAG="ai4ms-workbench:competition"
WORKBENCH_URL="http://127.0.0.1:8000"

fail() {
  printf '%s\n' "$1" >&2
  exit 1
}

[ -f "$ENV_FILE" ] || fail "Missing .env.competition beside START_AI4MS.sh."
[ -f "$COMPOSE_FILE" ] || fail "Missing docker-compose.yml beside START_AI4MS.sh."

API_KEY=$(sed -n 's/^AUTOENV_OPENAI_API_KEY=//p' "$ENV_FILE" | head -n 1)
case "$API_KEY" in
  ""|your_*|replace-*|changeme|sk-xxx)
    fail "No usable competition LLM API key is configured."
    ;;
esac
unset API_KEY

printf '%s\n' "AI4MS competition configuration is valid. Secrets were not printed."
[ "${1:-}" = "--validate-only" ] && exit 0

command -v docker >/dev/null 2>&1 || fail "Docker Engine is not installed."
docker info >/dev/null 2>&1 || fail "Docker is installed but the daemon is unavailable."

if ! docker image inspect "$IMAGE_TAG" >/dev/null 2>&1 && [ -f "$IMAGE_ARCHIVE" ]; then
  if [ -f "$CHECKSUM_FILE" ]; then
    expected_hash=$(awk 'NR == 1 { print $1 }' "$CHECKSUM_FILE")
    if command -v sha256sum >/dev/null 2>&1; then
      actual_hash=$(sha256sum "$IMAGE_ARCHIVE" | awk '{ print $1 }')
    elif command -v shasum >/dev/null 2>&1; then
      actual_hash=$(shasum -a 256 "$IMAGE_ARCHIVE" | awk '{ print $1 }')
    else
      fail "No SHA-256 utility is available to verify the competition image."
    fi
    [ "$actual_hash" = "$expected_hash" ] ||
      fail "The SHA-256 checksum for ai4ms-workbench.tar is invalid."
    printf '%s\n' "Competition image checksum is valid."
  fi
  printf '%s\n' "Loading the AI4MS competition image..."
  docker load --input "$IMAGE_ARCHIVE"
elif ! docker image inspect "$IMAGE_TAG" >/dev/null 2>&1; then
  fail "Neither ai4ms-workbench.tar nor the competition image is available."
fi

printf '%s\n' "Starting AI4MS..."
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up --detach --no-build

attempt=0
until curl --fail --silent "$WORKBENCH_URL/healthz" >/dev/null 2>&1; do
  attempt=$((attempt + 1))
  [ "$attempt" -lt 60 ] || fail "AI4MS did not become healthy within 120 seconds."
  sleep 2
done

printf '%s\n' "Checking live LLM connectivity..."
curl --fail --silent --show-error \
  --max-time 210 \
  --request POST \
  --header "Content-Type: application/json" \
  --data "{}" \
  "$WORKBENCH_URL/api/v1/meta/inference/probe" >/dev/null

printf '%s\n' "AI4MS is ready. Open $WORKBENCH_URL"
if [ "${1:-}" != "--no-browser" ]; then
  if command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$WORKBENCH_URL" >/dev/null 2>&1 &
  elif command -v open >/dev/null 2>&1; then
    open "$WORKBENCH_URL" >/dev/null 2>&1 &
  fi
fi
