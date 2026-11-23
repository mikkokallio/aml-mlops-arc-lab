#!/bin/bash
set -euo pipefail
: "${ACR_SERVER:?Set the lab registry hostname}"
: "${IMAGE:?Set the immutable serving image}"
: "${IDENTITY_CLIENT_ID:?Set the AcrPull managed identity client ID}"
[[ "$IMAGE" == "$ACR_SERVER/"*"@sha256:"* ]] || {
  echo "An immutable image from the specified registry is required." >&2
  exit 1
}
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq docker.io curl python3
systemctl enable --now docker
token="$(curl --silent --show-error --fail --noproxy '*' \
  -H Metadata:true \
  "http://169.254.169.254/metadata/identity/oauth2/token?api-version=2018-02-01&resource=https%3A%2F%2Fmanagement.azure.com%2F&client_id=$IDENTITY_CLIENT_ID" \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')"
refresh="$(printf '%s' "$token" | curl --silent --show-error --fail \
  --request POST "https://$ACR_SERVER/oauth2/exchange" \
  --data-urlencode 'grant_type=access_token' --data-urlencode "service=$ACR_SERVER" \
  --data-urlencode 'access_token@-' \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["refresh_token"])')"
unset token
trap 'docker logout "$ACR_SERVER" >/dev/null' EXIT
printf '%s' "$refresh" | docker login "$ACR_SERVER" \
  --username 00000000-0000-0000-0000-000000000000 --password-stdin
unset refresh
docker pull "$IMAGE"
docker logout "$ACR_SERVER" >/dev/null
trap - EXIT
docker run --detach --name aml-portable-smoke --restart unless-stopped \
  --publish 8080:8080 --env MODEL_VERSION=2 "$IMAGE"
for attempt in $(seq 1 60); do
  if curl --silent --show-error --fail http://127.0.0.1:8080/health; then
    exit 0
  fi
  sleep 5
done
docker logs --tail 50 aml-portable-smoke >&2
echo "Container failed to become ready." >&2
exit 1
