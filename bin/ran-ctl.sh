#!/usr/bin/env bash
# RAN(gNB/UE) 제어. 코어는 건드리지 않는다.
#   ./ran-ctl.sh START [프로파일] | STOP | STATUS
# 프로파일:
#   n78   OAI gNB + OAI nr-UE, n78 TDD 30kHz, rfsimulator   (기본)
#   n3    srsRAN gNB + srsUE,  n3  FDD 15kHz, ZMQ
# 두 프로파일은 UE1 IMSI 를 공유하므로 동시에 올리지 말 것.
set -euo pipefail
source "$(dirname "$0")/_common.sh"
resolve_upstream || exit 1

declare -A FILE=(
  [oaignb_rfsim]="$P5/compose/oai_n78_rfsim.yaml"
  [oainrue]="$P5/compose/oai_n78_rfsim.yaml"
  [srsgnb_zmq]="$UP/srsgnb_zmq.yaml"
  [srsue_5g_zmq]="$UP/srsue_5g_zmq.yaml"
)
N78=(oaignb_rfsim oainrue)          # 기동 순서: gNB 먼저
N3=(srsgnb_zmq srsue_5g_zmq)
ALL=("${N78[@]}" "${N3[@]}")

up_one() {
  local c="$1" f="${FILE[$1]}"
  if docker inspect "$c" >/dev/null 2>&1; then docker start "$c" >/dev/null
  else docker compose -p "${CORE_PROJECT}" -f "$f" --project-directory "$(dirname "$f")" up -d "$c"
  fi
  echo "  기동 $c"
}

case "${1:-STATUS}" in
  START)
    docker network inspect ${CORE_PROJECT}_default >/dev/null 2>&1 \
      || { echo "코어 네트워크가 없다. 먼저 core-ctl.sh START" >&2; exit 1; }
    wait_core_ready 120 || { echo "코어가 준비되지 않았다. RAN 기동 중단." >&2; exit 1; }
    case "${2:-n78}" in
      n78) SET=("${N78[@]}") ;;
      n3)  SET=("${N3[@]}")  ;;
      *) echo "프로파일은 n78 또는 n3" >&2; exit 2 ;;
    esac
    for c in "${SET[@]}"; do
      up_one "$c"
      # UE 붙기 전 gNB rfsim/zmq 서버 대기.
      # 주의: "[[ ]] && sleep" 형태로 쓰면 UE 차례에 조건이 거짓이라 1 을 반환하고
      #       루프의 마지막 명령이므로 set -e 가 걸려 성공인데도 exit 1 이 된다.
      if [[ "$c" == *gnb* ]]; then sleep 5; fi
    done
    ;;
  STOP)
    for ((i=${#ALL[@]}-1; i>=0; i--)); do docker stop "${ALL[$i]}" >/dev/null 2>&1 || true; done
    echo "  RAN 전부 정지"
    ;;
  STATUS)
    docker ps -a --filter "name=^($(IFS='|'; echo "${ALL[*]}"))$" \
      --format 'table {{.Names}}\t{{.Status}}'
    ;;
  *) echo "사용법: $0 START [n78|n3] | STOP | STATUS" >&2; exit 2 ;;
esac
