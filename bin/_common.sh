# 공통 설정. 모든 스크립트가 이 파일 하나만 본다.
# 값을 바꿀 일이 있으면 여기만 고친다.

# 이 파일 기준으로 프로젝트 루트를 잡는다. private5g 를 통째로 어디로 옮겨도 동작한다.
P5="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# docker compose 프로젝트명. 디렉토리명과 무관하게 이 값으로 고정한다.
# 네트워크는 "<PROJ>_default" 가 되며 RAN 컴포즈가 external 로 참조한다.
: "${CORE_PROJECT:=docker_open5gs}"
export CORE_PROJECT

# upstream 클론(런타임 트리) 위치. 찾는 순서는 셋이다.
#   1) 환경변수 UPSTREAM_DIR  2) $P5/upstream 심볼릭  3) 우리 장비의 기본 배치
# 새 컴퓨터에서는 2번만 걸어 주면 된다 — 디렉터리 배치를 따라할 필요가 없다.
if [ -z "${UPSTREAM_DIR:-}" ]; then
  if [ -d "$P5/upstream" ]; then
    UPSTREAM_DIR="$P5/upstream"
  else
    UPSTREAM_DIR="$P5/../sdr-tools/docker/docker_open5gs"
  fi
fi

resolve_upstream() {
  local d
  d="$(cd "$UPSTREAM_DIR" 2>/dev/null && pwd -P)" || {
    echo "upstream 클론을 찾을 수 없다: $UPSTREAM_DIR" >&2
    echo "  해결: ln -s <docker_open5gs 클론 경로> $P5/upstream" >&2
    echo "  또는: UPSTREAM_DIR=<경로> $0 ..." >&2
    return 1
  }
  [ -f "$d/sa-vonr-deploy.yaml" ] || {
    echo "$d 는 docker_open5gs 클론이 아니다 (sa-vonr-deploy.yaml 없음)" >&2; return 1
  }
  UP="$d"
  # 편의용 심볼릭을 실제 위치로 갱신 (없거나 깨졌으면 새로 건다)
  [ "$(readlink -f "$P5/upstream" 2>/dev/null)" = "$d" ] || ln -sfn "$d" "$P5/upstream"
  return 0
}

# 코어 SBI 메시가 수렴할 때까지 대기.
#   "docker compose up -d" 반환 = 컨테이너 기동, != 코어 준비 완료.
#   준비 전에 UE 를 붙이면 AUSF 호출이 HTTP 504 로 죽고
#   AMF 가 Registration reject [90] 을 내린다. (실측 확인)
wait_core_ready() {
  local need="AUSF UDM PCF SMF NSSF" timeout="${1:-120}" t0 since log have n
  n=$(echo $need | wc -w); t0=$(date +%s)
  since=$(docker inspect amf --format '{{.State.StartedAt}}' 2>/dev/null) || {
    echo "amf 컨테이너가 없다" >&2; return 1; }
  while :; do
    log=$(docker logs amf --since "$since" 2>&1 || true)
    have=$(printf '%s\n' "$log" \
      | grep -oE "\[(${need// /|})\] NFInstance associated" | sort -u | wc -l)
    if [ "$have" -ge "$n" ]; then
      echo "  코어 준비 완료 (NF $have/$n, $(( $(date +%s) - t0 ))초)"; return 0
    fi
    if [ $(( $(date +%s) - t0 )) -ge "$timeout" ]; then
      echo "  코어 준비 시간초과 ${timeout}초 (NF $have/$n)" >&2
      printf '%s\n' "$log" | grep -oE "\[[A-Z]+\] NFInstance associated" | sort -u | sed 's/^/    연결됨 /' >&2
      return 1
    fi
    sleep 2
  done
}
