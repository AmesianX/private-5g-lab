#!/usr/bin/env bash
# private5g/configs (정본) -> upstream 클론(런타임 트리) 배포.
#
# 코어/IMS/srsRAN 컨테이너는 upstream 클론의 compose 파일을 쓰므로
# 설정도 그 트리 안에 있어야 한다. 정본은 항상 여기(configs/)이고,
# 클론 쪽은 배포 사본이다. 클론에서 직접 고치지 말 것.
#   ./deploy-configs.sh          배포
#   ./deploy-configs.sh --check  차이만 출력 (배포 안 함)
set -euo pipefail
source "$(dirname "$0")/_common.sh"
resolve_upstream || exit 1

# 비밀값·호스트 고유값은 저장소에 두지 않는다. configs/secrets/lab.env 에서 읽어
# `*.in` 템플릿의 @TOKEN@ 을 채워 실제 설정 파일을 만든다(렌더 결과는 .gitignore).
SECRETS="$P5/configs/secrets/lab.env"
TEMPLATES=(
  "configs/env/env.in:configs/env/env"
  "configs/oai/nr-ue.n78.rfsim.conf.in:configs/oai/nr-ue.n78.rfsim.conf"
  "configs/srsran/gnb.yml.in:configs/srsran/gnb.yml"
)

render_templates() {
  if [ ! -f "$SECRETS" ]; then
    echo "  비밀값 파일이 없다: $SECRETS" >&2
    echo "  configs/secrets/lab.env.example 을 복사해 채운 뒤 chmod 600 할 것." >&2
    return 1
  fi
  # key=value 만 읽는다(주석·빈 줄 무시).
  local -a sedargs=()
  while IFS='=' read -r k v; do
    case "$k" in ''|\#*) continue;; esac
    sedargs+=(-e "s|@${k}@|${v}|g")
  done < <(grep -E '^[A-Za-z_][A-Za-z0-9_]*=' "$SECRETS")
  local n=0
  for m in "${TEMPLATES[@]}"; do
    local src="$P5/${m%%:*}" dst="$P5/${m##*:}"
    [ -f "$src" ] || { echo "  결손 템플릿 $src" >&2; return 1; }
    sed "${sedargs[@]}" "$src" > "$dst.tmp"
    if grep -q '@[A-Z0-9_]\+@' "$dst.tmp"; then
      echo "  채우지 못한 토큰이 남았다: ${m##*:}" >&2
      grep -o '@[A-Z0-9_]\+@' "$dst.tmp" | sort -u | sed 's/^/         /' >&2
      rm -f "$dst.tmp"; return 1
    fi
    if [ -f "$dst" ] && cmp -s "$dst.tmp" "$dst"; then rm -f "$dst.tmp"
    else mv "$dst.tmp" "$dst"; chmod 600 "$dst"; n=$((n+1)); echo "  렌더   ${m##*:}"; fi
  done
  echo "렌더 $n 건"
}

# 정본경로:배포경로
MAP=(
  "env/env:.env"
  "compose/sa-vonr-deploy.yaml:sa-vonr-deploy.yaml"   # 관리 포트(8080/9999/3000/9090)를 127.0.0.1 에만 공개. 11e
  "dns/ims_zone:dns/ims_zone"   # IMS 도메인 @ A 레코드(SMSC 전달용) 포함. 13장 사례
  "oai/gnb.sa.band78.fr1.106PRB.usrpb210.conf:oai/gnb.sa.band78.fr1.106PRB.usrpb210.conf"
  "pcscf/route/mo.cfg:pcscf/route/mo.cfg"
  "pcscf/route/mt.cfg:pcscf/route/mt.cfg"
  "pcscf/route/register.cfg:pcscf/route/register.cfg"
  "srslte/ue_5g_zmq.conf:srslte/ue_5g_zmq.conf"
  "srslte/ue_5g_zmq_n78.conf:srslte/ue_5g_zmq_n78.conf"
  "srsran/gnb.yml:srsran/gnb.yml"
  "srsran/libresdr_alphafox02.bin:srsran/libresdr_alphafox02.bin"
  "srsran/gnb_zmq_n78.yml:srsran/gnb_zmq_n78.yml"
)

check_only=0; [ "${1:-}" = "--check" ] && check_only=1
[ $check_only -eq 1 ] || render_templates || exit 1
rc=0; n_diff=0
for m in "${MAP[@]}"; do
  src="$P5/configs/${m%%:*}"; dst="$UP/${m##*:}"
  if [ ! -f "$src" ]; then echo "  결손 정본 $src"; rc=1; continue; fi
  if [ -f "$dst" ] && cmp -s "$src" "$dst"; then
    [ $check_only -eq 1 ] && echo "  동일   ${m##*:}"
  else
    n_diff=$((n_diff+1))
    if [ $check_only -eq 1 ]; then
      echo "  차이   ${m##*:}"
      diff -u "$dst" "$src" 2>/dev/null | sed -n '3,12p' | sed 's/^/         /'
    else
      mkdir -p "$(dirname "$dst")"; cp -a "$src" "$dst"; echo "  배포   ${m##*:}"
    fi
  fi
done
[ $check_only -eq 1 ] && echo "차이 $n_diff 건" || echo "배포 $n_diff 건 (나머지는 이미 동일)"
exit $rc
