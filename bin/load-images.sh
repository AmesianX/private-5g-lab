#!/usr/bin/env bash
# 릴리즈에 올려 둔 컨테이너 이미지를 내려받아 docker 에 적재한다.
# 업스트림(ghcr.io)에서 더 못 받는 상황을 전제로 한 복원 경로다.
#   ./load-images.sh [릴리즈태그]   기본 images-v1
set -euo pipefail
TAG="${1:-images-v1}"
REPO="${REPO:-AmesianX/private-5g-lab}"
DIR="${DIR:-$HOME/work/_images}"
mkdir -p "$DIR"; cd "$DIR"

command -v gh >/dev/null || { echo "gh(GitHub CLI)가 필요하다" >&2; exit 1; }
command -v zstd >/dev/null || { echo "zstd 가 필요하다: apt install zstd" >&2; exit 1; }

echo "== 내려받기 ($REPO $TAG → $DIR)"
gh release download "$TAG" -R "$REPO" -p '*.tar.zst' -p 'SHA256SUMS' --clobber

echo "== 체크섬"
sha256sum -c SHA256SUMS

echo "== 적재"
for f in *.tar.zst; do
  printf '  %-34s' "$f"
  zstd -d -c "$f" | docker load | tail -1
done

echo "== 확인"
docker images --format '{{.Repository}}:{{.Tag}}' \
  | grep -E 'docker_(dns|kamailio|metrics|mysql|open5gs|pyhss|rtpengine|srsran)|grafana/grafana|^mongo:6.0|oai-(gnb|nr-ue)' | sort
