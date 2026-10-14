# SIM 카드 — 현황과 결론

2026-10-05.

## 결론 먼저

**알리익스프레스에서 산 "LTE Blank USIM" 3장은 2G GSM 전용이다. 4G/5G 에 쓸 수 없다.**
ADM 을 알아내도 마찬가지다. USIM 애플리케이션이 물리적으로 없다.

## 근거 — 독립된 두 도구가 같은 판정

| 도구 | 결과 |
|---|---|
| 제조사 윈도우 툴 (GRSIMWrite) | `Type: GSM(GY04):GSM` |
| pySim | `EF.DIR` 없음, AID 없음, `ADF.USIM` 없음, `DF_GSM(7F20)` 만 존재 |

판매 페이지는 `Compatible: 4G FDD LTE, WCDMA and GSM` 라고 적혀 있었다.
**광고와 실물이 다르다 → 분쟁 사유.**

## 카드 식별 정보

```
ATR     3B9F94801FC38031A073B6A10067CF3251CC9E6EC015
ICCID   비어 있음 (전부 FF)
IMSI    없음
키 레퍼런스  1(PIN1), 129(PIN2), 10(ADM1), 11(ADM2)   ※ 0x0C 없음
```

### 파일 구조 (전부 읽기 성공)

| 파일 | 용도 | 쓰기 권한 |
|---|---|---|
| `2FE2` | ICCID | ADM2 |
| `7F20/6F07` | IMSI | ADM2 |
| `7F20/6F38` | SST | ADM2 |
| `3F00/0001` (19바이트) | 알고리즘 3 + Ki 16 | ADM2 |
| `7F20/6F20` Kc, `6F30` PLMNsel, `6F7E` LOCI | | PIN1 |
| `2F06` | EF.ARR (접근규칙) | ADM2 |

`0001` 이 19바이트인 것은 `SysmoSIMgr2`/`Gialer` 계열의 `알고리즘(3)+Ki(16)` 레이아웃과 일치.

## ADM 추적 기록 (실패)

시도한 값과 결과. **전부 틀렸다.**

| CHV | 값 | 출처 | 결과 |
|---|---|---|---|
| 0x0A (ADM1) | `88888888` | pySim 소스 | 틀림 |
| 0x0B (ADM2) | `88888888` | 툴 `data.grsp` | **틀림 (카드 2장에서 확인)** |
| 0x0C (ADM3) | `84796153` | GialerSim | 키 번호 자체가 카드에 없음 |

### 왜 `data.grsp` 의 ADM 이 안 맞았나

```
EditADM    3838383838383838
EditPIN1   1234        EditPUK1   88888888
EditICCID  FFFFFFFFFFFFFFFFFFFF     ← 공백
```

이 값들은 **카드에 써넣을 값**이지 인증에 쓰는 값이 아니다.
툴은 ADM 인증을 하지 않고 **제조사 전용 명령으로 공백 카드를 초기화하며 ADM 까지 심는다.**
pySim 은 표준 UICC 명령만 쓰므로 이 경로를 재현할 수 없다.

**실제로 툴은 이 카드에 쓰기를 성공했다** — 모뎀이 읽은 preferred networks 가
`data.grsp` 의 `EditGSM_PLMN`(46000;46002;52501;...) 과 정확히 일치.

## 카드 재고 상태

```
카드 1   ADM2 소진 (차단)   ← 잘못된 시도로 소모
카드 2   ADM2 1회 남음
카드 3   ADM2 2회 남음
```

**pySim 으로 더 시도하지 말 것.** 새 후보 값이 없다.

## 교훈

1. **카드가 USIM 인지부터 확인한다.** `EF.DIR` 과 AID 를 읽으면 1분이면 끝난다.
   ADM 을 쫓기 전에 했어야 했다.
2. **`apdu --raw` 는 이 카드에서 신뢰할 수 없다.** 모든 명령에 `6F00` 을 반환하면서도
   카운터는 깎았다. 인증은 반드시 pySim 정식 명령(`verify_chv`, `-A`)으로 한다.
   정식 경로는 `63Cx` / `N tries left` 를 정확히 보고한다.
3. **`6F00` 을 "처리 안 됨"으로 읽지 말 것.** 비표준 응답이어도 카운터는 돈다.

## 다음 카드 — sysmoISIM-SJA5-9FV

| 조건 | 충족 |
|---|---|
| 3GPP R17, 5G SA (`ADF.USIM/DF.5GS`) | O |
| **ADM1 키 주문 시 이메일 제공** | O |
| pySim 공식 지원 | O |
| 2G/3G/4G/VoLTE(ISIM) | O |

- 구매: https://shop.sysmocom.de/SIM/Cards/
- **`with ADM keys` 가 상품명에 있어야 한다**
- **MFF2(솔더 타입) 아닌 일반 카드**를 고를 것
- 9FV vs S17 차이는 SUCI 계산 주체뿐. Open5GS 는 기본이 null-scheme 이라
  **9FV 로 충분**하다. S17 은 재고가 자주 끊긴다.

레퍼런스: https://github.com/SystronLab/srsRAN-USRPs-COTS (srsRAN+USRP+Open5GS+sysmoISIM)

## 카드 도착 후 절차

```bash
# 1. 리더 연결 후 카드 읽기
sudo systemctl start pcscd
cd /home/user/work/sdr-tools/sim/pysim
sudo /home/user/.venv/bin/python3 pySim-shell.py -p0 -A <이메일로받은ADM1>

# 2. 쓰기 (pySim-prog)
sudo /home/user/.venv/bin/python3 pySim-prog.py -p0 \
  -a <ADM1> -t sysmoISIM-SJA5 \
  -i 001011234567895 \
  -k <KI> \
  --opc <OPC> \
  -s <ICCID> --mcc 001 --mnc 01
```

가입자는 Open5GS 에 이미 등록돼 있다 (mongo 볼륨, 재부팅해도 유지).

관련: [[modem.md]], [[rf-cabling.md]], [[status.md]]

## 발급 카드 대장 (2026-10-14)

sysmoISIM-SJA5 카드에 pySim-prog 로 발급. **키·ADM1 은 이 저장소에 적지 않는다**(공급사 CSV 참조).

| # | ICCID | IMSI | MSISDN | 용도 | SPN |
|---|---|---|---|---|---|
| 1 | 8988211…(sysmo 1호) | 001011234567895 | 821099994531 | RM520N-GL 모뎀 | — |
| 2 | — (소프트 UE, 카드 없음) | 001011234567896 | 821099994532 | oainrue 컨테이너 | — |
| 3 | <ICCID3> | 001011234567897 | 821099994533 | **차폐함 안드로이드 폰** | P5G |

3번 발급 명령 형태(키는 자리표시자):

```bash
cd /home/user/work/sdr-tools/sim/pysim
sudo /home/user/.venv/bin/python3 pySim-prog.py -p0 -t sysmoISIM-SJA5 -a <ADM1> \
  -x 001 -y 01 --mnclen 2 -n P5G \
  -i 001011234567897 -k <KI> -o <OPC> \
  -M e1ffffffffffffffffffffffff06815384090067ffffffffff000000 \
  --msisdn 821099994533 \
  --ims-hdomain ims.mnc001.mcc001.3gppnetwork.org \
  --impi 001011234567897@ims.mnc001.mcc001.3gppnetwork.org \
  --impu sip:001011234567897@ims.mnc001.mcc001.3gppnetwork.org
```

주의할 점 세 가지.

- **ICCID 는 이 카드 타입에서 쓸 수 없다.** pySim 이 `Programming of the ICCID is not
  implemented for this type of card` 경고만 내고 넘어간다. 공장 ICCID 를 그대로 쓰면 된다.
- **EF.SMSP 는 공장값을 `-M` 으로 보존했다.** 우리 SMSC(kamailio)는 E.164 번호가 없는
  SIP 전용이라, pySim 기본값(+1555…)으로 덮으면 단말 기본 문자앱이 없는 번호로 보낸다.
- **클론(같은 IMSI 두 장)은 쓰지 않는다.** 코어가 한 가입자로 보기 때문에 나중에 붙은
  쪽이 앞선 쪽을 밀어낸다. 단말이 둘이면 가입자도 둘이어야 한다.

### 심은 키가 맞는지 확인하는 법

Ki 는 카드에서 읽을 수 없다. 유일한 검증은 **카드에게 직접 인증을 시켜 보는 것**이다.
`tools/milenage.py` 로 임의의 RAND 와 SQN 에 대한 AUTN·RES·CK·IK 를 계산하고,
pySim-shell 에서 같은 값을 카드에 넣는다.

```
select ADF.USIM
authenticate <RAND> <AUTN>
```

카드가 돌려준 `res`/`ck`/`ik` 가 계산값과 같으면 Ki·OPc 가 정확히 들어간 것이다.
3번 카드는 이 검증을 통과했다. 이때 카드의 SQN 이 시험에 쓴 값까지 올라가므로,
**HSS 쪽 SQN 을 그보다 크게 맞춰 두면**(여기서는 64) 첫 접속에서 재동기 왕복이 생기지 않는다.

### 코어 등록 (카드 1장 = 두 곳 등록)

```bash
# 1) open5gs: 기존 가입자 문서를 복제해 IMSI/MSISDN/키만 바꾼다
docker exec mongo mongosh --quiet open5gs --eval '...'
# 2) PyHSS: auc -> subscriber -> ims_subscriber 순서 (auc_id 를 subscriber 가 참조)
curl -X PUT http://127.0.0.1:8080/auc/          -d '{"imsi":...,"ki":...,"opc":...,"amf":"8000"}'
curl -X PUT http://127.0.0.1:8080/subscriber/   -d '{"imsi":...,"auc_id":3,"apn_list":"1,2",...}'
curl -X PUT http://127.0.0.1:8080/ims_subscriber/ -d '{"imsi":...,"msisdn_list":"[...]"}'
```

PyHSS REST 는 루프백에만 열려 있다(인증 없음). `scscf*` 칸은 등록 시 채워지므로 비워 둔다.
