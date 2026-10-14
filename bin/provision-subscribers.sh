#!/usr/bin/env bash
# 가입자 3명을 Open5GS(mongo)와 PyHSS(auc/subscriber/ims_subscriber)에 등록한다.
# 맨바닥에서 재구성할 때 쓴다. 이미 있으면 덮어쓴다(멱등).
#   ./provision-subscribers.sh [--check]
#
# 값은 configs/secrets/lab.env 에서 읽는다. 저장소에는 실키가 없다.
# 가입자 프로파일(슬라이스·세션·PCC 규칙)은 configs/db/subscriber.template.json.
#   세션 타입은 1(IPv4)이어야 한다 — srsRAN gNB 가 IPv4v6 를 거부한다.
set -euo pipefail
source "$(dirname "$0")/_common.sh"

SECRETS="$P5/configs/secrets/lab.env"
TPL="$P5/configs/db/subscriber.template.json"
PYHSS="http://127.0.0.1:8080"
REALM="ims.mnc001.mcc001.3gppnetwork.org"
[ -f "$SECRETS" ] || { echo "비밀값 없음: $SECRETS (lab.env.example 참고)" >&2; exit 1; }
# shellcheck disable=SC1090
set -a; source "$SECRETS"; set +a

check_only=0; [ "${1:-}" = "--check" ] && check_only=1

# IMSI  MSISDN  KI  OPC  IMEISV
UES=(
  "${UE1_IMSI:-}|821099994531|${UE1_KI:-}|${UE1_OPC:-}|${UE1_IMEISV:-${UE1_IMEISV:?lab.env 에 UE1_IMEISV 를 넣을 것}}"
  "${UE2_IMSI:-}|821099994532|${UE2_KI:-}|${UE2_OPC:-}|6754567890123413"
  "${UE3_IMSI:-}|821099994533|${UE3_KI:-}|${UE3_OPC:-}|6754567890123414"
)

if [ $check_only -eq 1 ]; then
  echo "== Open5GS(mongo)"
  docker exec mongo mongosh --quiet open5gs --eval \
    'db.subscribers.find({},{imsi:1,msisdn:1,"security.sqn":1,_id:0}).forEach(d=>print(JSON.stringify(d)))'
  echo "== PyHSS"
  for t in auc subscriber ims_subscriber; do
    printf '%-16s %s\n' "$t" "$(curl -s "$PYHSS/$t/list" | python3 -c 'import json,sys;print(len(json.load(sys.stdin)),"행")')"
  done
  exit 0
fi

for row in "${UES[@]}"; do
  IFS='|' read -r IMSI MSISDN KI OPC IMEISV <<< "$row"
  for v in "$IMSI" "$MSISDN" "$KI" "$OPC"; do
    [ -n "$v" ] && [[ "$v" != \<* ]] || { echo "  건너뜀(값 없음): $IMSI" >&2; continue 2; }
  done
  echo "— $IMSI / $MSISDN"

  # 1) Open5GS: 템플릿을 채워 통째로 교체
  python3 - "$TPL" "$IMSI" "$MSISDN" "$KI" "$OPC" "$IMEISV" > /tmp/.sub.$$.json <<'PY'
import json, sys
tpl, imsi, msisdn, ki, opc, imeisv = sys.argv[1:7]
s = json.load(open(tpl, encoding='utf-8'))
s['imsi'] = imsi; s['msisdn'] = [msisdn]; s['imeisv'] = imeisv
s['security']['k'] = ki; s['security']['opc'] = opc
print(json.dumps(s, ensure_ascii=False))
PY
  # mongosh 에는 cat() 이 없다. 문서를 --eval 안에 직접 넣는다.
  docker exec -i mongo mongosh --quiet open5gs --eval \
    "const s=$(cat /tmp/.sub.$$.json); db.subscribers.deleteOne({imsi:s.imsi}); db.subscribers.insertOne(s);" >/dev/null
  rm -f /tmp/.sub.$$.json
  echo "    open5gs 등록"

  # 2) PyHSS: auc -> subscriber -> ims_subscriber
  #    subscriber 가 auc_id 를 참조하므로 순서가 고정이다. PUT 은 행을 새로 만들기
  #    때문에, 같은 IMSI 가 이미 있으면 그 id 로 PATCH 해야 중복이 안 쌓인다.
  find_id() {  # $1=표 이름  $2=id 필드  $3=IMSI
    curl -s "$PYHSS/$1/list" | python3 -c "
import json,sys
rows=[r for r in json.load(sys.stdin) if r.get('imsi')=='$3']
print(rows[0]['$2'] if rows else '')"
  }
  upsert() {   # $1=표  $2=id필드  $3=본문  → 최종 id 를 출력
    local id; id=$(find_id "$1" "$2" "$IMSI")
    if [ -n "$id" ]; then
      curl -s -X PATCH "$PYHSS/$1/$id" -H 'Content-Type: application/json' -d "$3" >/dev/null
      echo "$id"
    else
      curl -s -X PUT "$PYHSS/$1/" -H 'Content-Type: application/json' -d "$3" \
        | python3 -c "import json,sys;print(json.load(sys.stdin)['$2'])"
    fi
  }
  AUC=$(upsert auc auc_id \
    "{\"ki\":\"$KI\",\"opc\":\"$OPC\",\"amf\":\"8000\",\"imsi\":\"$IMSI\",\"sqn\":0}")
  upsert subscriber subscriber_id \
    "{\"imsi\":\"$IMSI\",\"enabled\":true,\"auc_id\":$AUC,\"default_apn\":1,\"apn_list\":\"1,2\",\"msisdn\":\"$MSISDN\",\"ue_ambr_dl\":0,\"ue_ambr_ul\":0,\"nam\":0,\"roaming_enabled\":true,\"subscribed_rau_tau_timer\":300}" >/dev/null
  upsert ims_subscriber ims_subscriber_id \
    "{\"imsi\":\"$IMSI\",\"msisdn\":\"$MSISDN\",\"msisdn_list\":\"[$MSISDN]\",\"sh_profile\":\"string\",\"ifc_path\":\"default_ifc.xml\"}" >/dev/null
  echo "    pyhss 등록 (auc_id=$AUC)"
done
echo "완료. 확인은 $0 --check"
