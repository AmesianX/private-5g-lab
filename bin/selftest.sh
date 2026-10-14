#!/usr/bin/env bash
# 재부팅 후 또는 변경 후 종단간 자가진단.
#   ./selftest.sh [n78|n3] [--keep]
# --keep 을 주면 끝나고 안 내린다 (기본은 내림).
# 통과 = 코어 기동 -> RAN 기동 -> UE 접속 -> 터널 생성 -> 외부 통신.
set -uo pipefail
source "$(dirname "$0")/_common.sh"
resolve_upstream || exit 1

PROFILE="${1:-n78}"; KEEP=0; [ "${2:-}" = "--keep" ] && KEEP=1
case "$PROFILE" in
  n78) UEC=oainrue;       IFACE=oaitun_ue1; OK_PAT="PDU Session Establishment Accept" ;;
  n3)  UEC=srsue_5g_zmq;  IFACE=tun_srsue;  OK_PAT="PDU Session Establishment successful" ;;
  *) echo "프로파일은 n78 또는 n3" >&2; exit 2 ;;
esac

fail=0
step() { printf '%-42s' "$1"; }
ok()   { echo "OK   $*"; }
ng()   { echo "실패 $*"; fail=1; }

echo "=== selftest: $PROFILE ==="
step "1. 코어 기동 + 준비 대기"
if out=$("$P5/bin/core-ctl.sh" START 2>&1); then
  ok "$(printf '%s' "$out" | grep -o '코어 준비 완료.*' || echo '')"
else ng "$(printf '%s' "$out" | tail -2)"; echo "중단"; exit 1; fi

step "2. RAN 기동 ($PROFILE)"
if "$P5/bin/ran-ctl.sh" START "$PROFILE" >/dev/null 2>&1; then ok; else ng; fi

step "3. UE 접속 (최대 60초)"
# docker logs 는 재시작 전 로그까지 누적되므로 반드시 현재 기동분만 본다.
# 안 그러면 이전 실행의 성공 로그를 읽고 거짓 통과한다.
t0=$(date +%s); got=""
since=$(docker inspect "$UEC" --format '{{.State.StartedAt}}' 2>/dev/null)
while [ $(( $(date +%s) - t0 )) -lt 60 ]; do
  got=$(docker logs "$UEC" --since "$since" 2>&1 | grep -F "$OK_PAT" | tail -1)
  [ -n "$got" ] && break
  sleep 2
done
[ -n "$got" ] && ok "$(echo "$got" | grep -oE '(IP|IPv4): *[0-9.]+' | tail -1)" || ng "'$OK_PAT' 미검출"

step "4. 터널 인터페이스 $IFACE"
ip4=$(docker exec "$UEC" ip -4 -o addr show "$IFACE" 2>/dev/null | grep -oE 'inet [0-9.]+' | cut -d' ' -f2)
[ -n "$ip4" ] && ok "$ip4" || ng "없음"

# 이 UE 는 IMS 시험용이라 `ims` DNN 을 요청한다(configs/oai/nr-ue.n78.rfsim.conf).
# IMS 망은 외부 인터넷으로 라우팅되지 않으므로 8.8.8.8 로 재면 당연히 실패한다.
# 사용자 평면이 섰는지는 **자기 망의 UPF 게이트웨이**로 재는 것이 맞다.
step "5. 사용자 평면 (UPF 게이트웨이)"
if [ -n "$ip4" ]; then
  gw="${ip4%.*}.1"
  r=$(docker exec "$UEC" ping -c3 -W2 -I "$IFACE" "$gw" 2>&1 | grep -oE '[0-9]+% packet loss')
  [ "$r" = "0% packet loss" ] && ok "$gw $r" || ng "$gw $r"
else ng "터널 없어 건너뜀"; fi

step "5b. 외부 통신 (참고)"
if [ -n "$ip4" ] && [ "${ip4#10.45.}" != "$ip4" ]; then
  r=$(docker exec "$UEC" ping -c3 -W2 -I "$IFACE" 8.8.8.8 2>&1 | grep -oE '[0-9]+% packet loss')
  [ "$r" = "0% packet loss" ] && ok "$r" || ng "$r"
else
  ok "건너뜀 — 이 UE 는 ims DNN($ip4). 외부 통신은 모뎀·단말로 확인한다"
fi

step "6. 정본 vs 런타임 설정 일치"
d=$("$P5/bin/deploy-configs.sh" --check 2>&1 | tail -1)
[ "$d" = "차이 0 건" ] && ok "$d" || ng "$d"

echo
[ $KEEP -eq 1 ] && echo "(--keep: 기동 상태 유지)" || { "$P5/bin/ran-ctl.sh" STOP >/dev/null 2>&1; "$P5/bin/core-ctl.sh" STOP >/dev/null 2>&1; echo "(정지 완료)"; }
[ $fail -eq 0 ] && { echo "=== 전체 통과 ==="; exit 0; } || { echo "=== 실패 있음 ==="; exit 1; }
