#!/usr/bin/env bash
# Open5GS 5GC + IMS(VoNR) 코어 제어.  RAN 은 ran-ctl.sh 담당.
#   ./core-ctl.sh START | STOP | STATUS
# compose 프로젝트명은 docker_open5gs 로 고정한다.
# 네트워크 docker_open5gs_default 를 RAN 컴포즈가 external 로 참조하므로
# 이름이 바뀌면 RAN 이 붙지 못한다.
set -euo pipefail
source "$(dirname "$0")/_common.sh"
resolve_upstream || exit 1
FILE="sa-vonr-deploy.yaml"     # VoNR 구성. 평문 SA 만 쓰려면 sa-deploy.yaml

case "${1:-STATUS}" in
  START)
    "$P5/bin/deploy-configs.sh"          # 정본 -> 런타임 트리 동기화 후 기동
    cd "$UP" && docker compose -p "${CORE_PROJECT}" -f "$FILE" up -d
    wait_core_ready 120
    ;;
  STOP)
    cd "$UP" && docker compose -p "${CORE_PROJECT}" -f "$FILE" stop
    ;;
  STATUS)
    docker ps -a --filter "label=com.docker.compose.project=${CORE_PROJECT}" \
      --format 'table {{.Names}}\t{{.Status}}' \
      | grep -vE "oaignb_rfsim|oainrue|srsgnb_zmq|srsue_5g_zmq" || true
    ;;
  *) echo "사용법: $0 START|STOP|STATUS" >&2; exit 2 ;;
esac
