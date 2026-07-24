#!/usr/bin/env bash
set -euo pipefail

suffix="${GITHUB_RUN_ID:-$$}${RANDOM}"
worker="wp6w${suffix}"
test_root="$(mktemp -d)"
versions="${test_root}/versions"
stage="${versions}/.stage-$(printf '%032x' "$RANDOM")"

cleanup() {
  sudo userdel "${worker}" >/dev/null 2>&1 || true
  rm -rf -- "${test_root}"
}
trap cleanup EXIT

sudo useradd --system --no-create-home --shell /usr/sbin/nologin "${worker}"
mkdir -p "${stage}"
chmod 0755 "${versions}"
sudo chown "${worker}:${worker}" "${stage}"
sudo chmod 0700 "${stage}"

if sudo -u "${worker}" touch "${versions}/forbidden"; then
  echo "worker能够写入versions根" >&2
  exit 1
fi
sudo -u "${worker}" touch "${stage}/allowed"
test -f "${stage}/allowed"
echo "PASS Linux distinct-UID stage isolation"
