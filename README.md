# private5g — 사설 로컬 5G SA 망

리눅스 한 대와 SDR 한 대로 **동작하는 5G 단독(SA) 이동통신망**을 세운다. 상용 단말이
실제로 붙고, 전화가 울리고, 문자와 사진이 오간다. 목적은 상용망 두절 시 가동할 자체
통신망이다. 5G SA 로 검증한 뒤 **4G LTE 가 실제 배치 목표**다.

이 저장소 하나로 **맨바닥에서 같은 망이 선다.** 새로 산 컴퓨터에 리눅스를 깔고 장비도
새로 사서 붙이는 상황을 전제로 썼다.

## 끝나면 무엇이 되나

| | 실측 |
|---|---|
| 5G SA 등록 | 실물 갤럭시 S22+ 가 `HOME`, 기술 `NR`, PLMN `001/01` |
| 데이터 | UPF 까지 RTT 25~31 ms, 외부까지 54~58 ms, 손실 0 % |
| 음성 (VoNR) | 단말에 수신 전화 표시, 통화 성립, RTP 양방향 |
| 영상통화 | video RTP 송신 332 / 수신 2697 (20 초) |
| 문자 | 길이 제한 없음(UDH 연결 문자). 270 자가 한 통으로 병합 |
| 멀티미디어(MMS) | 양방향. 단말이 보낸 JPEG 이 원본과 SHA256 동일 |
| 전파 누설 | 차폐함 밖에서 검출 안 됨(측정 방법과 한계는 12 장) |

## ⚠ 송신 전에 반드시

전파는 벽을 넘는다. **공중으로 내보내는 순간 허가가 필요한 무선국**이다. 한국 전파법
기준으로 허가 없는 무선국 개설·운용은 3년 이하 징역 또는 3천만 원 이하 벌금이다.

- PLMN 은 시험용 **001/01** 고정. 상용 번호(450-05 SKT / 450-06 LGU+ / 450-08 KT) 절대 금지
- 주파수는 상용 할당과 교차 확인. n78 상용: LG U+ 3400~3500 / KT 3500~3600 / SKT 3600~3700 MHz
- **업스트림 예제의 주파수를 믿지 말 것.** 대부분 상용 대역 한복판이 기본값이다
- 송신은 **동축 직결 + 감쇠기**, 안 쓰는 단자는 **50 Ω 종단**, 가능하면 **차폐함** 안에서
- 송신 게인은 항상 최소에서 시작
- 안테나 달린 SDR 이 같은 호스트에 있다면 그 장치가 열리지 않는지 확인(`serial=` 핀)

자세한 것은 [docs/book/부록D-전파와법규고지.md](docs/book/부록D-전파와법규고지.md).

---

# 재구축 가이드

아래 순서대로 하면 된다. 각 단계 끝에 **확인 방법**을 같이 적었다. 확인이 통과하지
않으면 다음으로 넘어가지 말 것 — 뒤에서 엉뚱한 증상으로 되돌아온다.

> **검증 기록.** 이 절차는 2026-10-15 에 실제로 전부 내리고 다시 세워서 확인했다.
> `docker compose down -v` 로 컨테이너와 **데이터베이스 볼륨까지 삭제**한 뒤, 이 저장소를
> GitHub 에서 **새로 클론해** 그것만으로 재구축했다. 결과: 설정 렌더가 기존과 비트 단위로
> 동일, 코어 NF 5/5, 가입자 3명 생성, 실물 단말이 `00101` 에 재등록되어 인터넷(10.45.x)과
> IMS(10.46.x) 세션을 모두 받고 문자까지 통했다.
>
> 그 과정에서 **이 저장소의 결함 세 가지**가 드러나 고쳤다 — 업스트림 경로를 심볼릭
> 링크로 못 찾던 것, `cd && pwd` 가 논리 경로를 돌려줘 심볼릭이 자기 자신을 가리키던 것,
> 그리고 **빈 데이터베이스에서 PyHSS APN 행을 만들지 않아 가입자 등록이 외래키 제약에
> 걸리던 것**이다. 마지막 것은 이미 돌아가는 랩에서는 평생 드러나지 않는 종류다.

## 0. 장비 — 특히 USIM 을 조심하라

| 품목 | 우리가 쓴 것 | 주의 |
|---|---|---|
| 리눅스 호스트 | Ubuntu 24.04, x86_64 | 도커가 돌면 된다 |
| SDR | Ettus **USRP B210** / LibreSDR B220mini | 송신용 **시리얼을 고정**한다 |
| USIM | **sysmoISIM-SJA5** | **아래 함정을 꼭 읽을 것** |
| 카드 리더 | PC/SC CCID (Identiv SCR35xx 등) | `pcscd` |
| UE ① 모뎀 | Quectel **RM520N-GL** + 캐리어 보드 | USB, `2c7c:0801` |
| UE ② 실물 단말 | 갤럭시 S22+ (SM-S9060), **루트 필요** | 차폐함 안에서 제어하려면 |
| 차폐함 | TOJOIN MS3020-A | SMA 관통 4, 필터패널 |
| 감쇠기 | 30 dB · 40 dB SMA | 송신 경로 |
| 종단기 | 50 Ω SMA | 안 쓰는 단자 전부 |
| USB-C 랜 어댑터 | RTL8153 계열 | 차폐함 안 단말의 유선 adb |
| 동축 케이블 | SMA | 길수록 손실. 길이를 기록해 둘 것 |

### 🔴 USIM 함정 — 여기서 가장 오래 막힌다

**알리익스프레스의 "LTE Blank USIM" 류는 쓸 수 없다.** 광고에는
`Compatible: 4G FDD LTE, WCDMA and GSM` 이라고 적혀 있지만, 실물은 **2G GSM 전용**이다.
`EF.DIR` 도 AID 도 `ADF.USIM` 도 없고 `DF_GSM(7F20)` 만 있다. ADM 키를 알아내도 소용없다 —
USIM 애플리케이션이 물리적으로 없기 때문이다. 우리는 이것을 모르고 ADM 추적에 카드 한
장을 소모한 뒤에야 알았다.

**카드가 USIM 인지는 1 분이면 가른다. ADM 을 쫓기 전에 이것부터 하라.**

```bash
sudo ~/.venv/bin/python3 pySim-read.py -p0 | head -20
# "Autodetected card type" 과 ADF.USIM 이 보여야 한다. 없으면 그 카드는 버린다.
```

**제대로 된 카드는 유럽에서 왔다.** 독일 sysmocom 에서 **sysmoISIM-SJA5** 를 주문했다.

- 구매: <https://shop.sysmocom.de/SIM/Cards/>
- **상품명에 `with ADM keys` 가 있어야 한다.** ADM 키 없이는 카드에 쓸 수 없고,
  sysmocom 은 주문 건별로 **ADM1 을 이메일로** 보내 준다
- **MFF2(솔더 타입) 말고 일반 카드**를 고를 것
- 9FV / S17 차이는 SUCI 계산 주체뿐이다. Open5GS 는 기본이 null-scheme 이라 **9FV 로 충분**하고
  S17 은 재고가 자주 끊긴다
- 배송에 시간이 걸린다. **망을 다 세워 놓고 카드를 기다리는 일이 없도록 먼저 주문하라.**
  우리는 그 상태로 작업이 멈춘 적이 있다

자세한 기록은 [docs/sim-cards.md](docs/sim-cards.md).

## 1. 호스트 선행 설치

```bash
sudo apt update
sudo apt install -y docker.io docker-compose-v2 git python3-pip \
                    pcscd pcsc-tools android-tools-adb nmap avahi-utils \
                    uhd-host python3-uhd zstd
sudo usermod -aG docker "$USER"          # 재로그인 필요
sudo uhd_images_downloader               # UHD 펌웨어/FPGA
sudo systemctl enable --now pcscd
python3 -m venv ~/.venv && ~/.venv/bin/pip install pyscard
```

**ModemManager 를 반드시 비켜 세운다.** 그대로 두면 모뎀의 AT 포트와 QMI 세션을 가로채
죽인다. 증상이 "되다가 끊긴다"라서 원인을 찾기 어렵다.

```bash
sudo systemctl mask ModemManager          # 또는 udev 로 해당 장치만 제외
```

**확인** — `docker ps` 가 권한 오류 없이 돌고, `uhd_find_devices` 가 SDR 을 본다.

> `python3-uhd` 는 시스템 파이썬 버전용으로 설치된다. `~/.venv` 안에서는 `import uhd`
> 가 안 된다. 계측 도구(`tools/leakscan.py`)는 `/usr/bin/python3.12` 처럼 **시스템
> 파이썬으로** 실행해야 한다.

## 2. 저장소와 업스트림 클론

코어·IMS 컨테이너는 업스트림 프로젝트의 compose 를 쓴다. 우리 설정이 **정본**이고
업스트림 클론은 **배포 대상**이다.

```bash
git clone <이 저장소> ~/work/private5g
git clone https://github.com/herlesupreeth/docker_open5gs.git /path/to/docker_open5gs
git -C /path/to/docker_open5gs checkout 1f3bcf7

ln -s /path/to/docker_open5gs ~/work/private5g/upstream
```

**심볼릭 링크만 걸면 된다.** 우리 디렉터리 배치를 따라할 필요 없다 — 스크립트가
`upstream` 링크를 먼저 본다. (환경변수 `UPSTREAM_DIR` 로도 지정할 수 있다.)

업스트림 클론은 **건드리지 않는다.** 거기서 직접 고치면 다음 배포에 덮인다.

**확인** — `./bin/deploy-configs.sh --check` 가 "upstream 클론을 찾을 수 없다" 를 내지 않는다.

## 3. 컨테이너 이미지

ghcr.io 에서 받는 것이 정석이지만, 업스트림이 태그를 옮기거나 지울 수 있다.
**인터넷에서 못 구하는 상황을 대비해 우리가 실제로 돌린 이미지를 이 저장소 릴리즈에
올려 두었다.** 이 저장소 하나만 있으면 복원된다.

```bash
./bin/load-images.sh            # 릴리즈 images-v1 에서 받아 체크섬 확인 후 docker load
```

이미지 11 개, 압축 합계 4.0 GB. compose 가 쓰는 **로컬 태그와 ghcr 태그를 둘 다** 담았다.

**확인** — `docker images | grep docker_open5gs` 에 `latest` 와 `master` 가 모두 보인다.

## 4. 비밀값 채우기

실키와 호스트 고유값은 **이 파일 하나**에서만 온다. 저장소에는 틀만 있다.

```bash
cp configs/secrets/lab.env.example configs/secrets/lab.env
chmod 600 configs/secrets/lab.env
$EDITOR configs/secrets/lab.env
```

| 값 | 어디서 얻나 |
|---|---|
| `DOCKER_HOST_IP` | 호스트의 LAN 주소 (`ip -br addr`) |
| `B210_SERIAL` | `uhd_find_devices` 의 `serial:`. **송신에 쓸 그 한 대** |
| `PHONE_IP` | 차폐함 안 단말에 줄 고정 주소 |
| `UE*_KI`, `UE*_OPC` | 카드 공급사가 준 값 (sysmocom 이메일/CSV) |
| `UE3_ADM1`, `UE3_ICCID` | 카드 발급에 쓴다 |

**확인** — `./bin/deploy-configs.sh` 가 "채우지 못한 토큰이 남았다"를 내지 않는다.
비어 있으면 **무엇이 비었는지 이름을 적고 멈춘다.**

## 5. 설정 배포 · 코어 기동 · 가입자 생성

```bash
cd ~/work/private5g
./bin/deploy-configs.sh        # 템플릿 렌더 + 업스트림 트리로 배포
./bin/core-ctl.sh START        # NF 5/5 까지 기다린다
./bin/provision-subscribers.sh # APN 2개 + 가입자 3명을 "만든다"
./bin/provision-subscribers.sh --check
```

`provision-subscribers.sh` 는 **덤프 복원이 아니라 생성**이다. 빈 데이터베이스에서
APN(`internet`, `ims`)과 가입자를 템플릿
[`configs/db/subscriber.template.json`](configs/db/subscriber.template.json) 으로 만든다.
값은 `lab.env` 에서 읽는다. 멱등이라 여러 번 돌려도 중복이 쌓이지 않는다.

**확인** — `--check` 가 mongo 가입자 3 행, PyHSS `auc`/`subscriber`/`ims_subscriber` 각 3 행을 보고한다.

## 6. USIM 발급

### 6.1 공급사가 보내 준 값 읽기

sysmocom 은 주문 건별로 카드 목록을 CSV 또는 이메일로 보낸다. 한 줄이 카드 한 장이고,
우리에게 필요한 것은 넷뿐이다.

| 항목 | 예 | 쓰임 |
|---|---|---|
| ICCID | `894944…` 19 자리 | 카드 식별. 바꿀 수 없다 |
| **ADM1** | 8 자리 숫자 | **쓰기 권한.** 이게 없으면 아무것도 못 쓴다 |
| **Ki** | 32 자리 헥스 | 인증키. 카드와 HSS 가 같아야 한다 |
| **OPc** | 32 자리 헥스 | 사업자 변형값 |

나머지(PIN1/PUK1/PIN2/PUK2, KIC/KID/KIK 9 개)는 OTA 용이라 우리 랩에서는 쓰지 않는다.
이 값들은 **저장소에 넣지 않는다.** `configs/secrets/lab.env` 에만 둔다.

> **ADM1 은 재시도 횟수가 정해져 있다.** 틀린 값을 반복해 넣으면 카드가 영구히 잠긴다.
> 우리는 다른 카드에서 이걸로 한 장을 날렸다. **추측해서 넣지 말 것.**

### 6.2 리더와 카드 확인

```bash
sudo systemctl start pcscd
sudo pcsc_scan -r                     # 리더가 보이는지
```

pySim 을 받는다.

```bash
git clone https://gitea.osmocom.org/sim-card/pysim.git ~/work/pysim
cd ~/work/pysim && ~/.venv/bin/pip install -r requirements.txt
```

**쓰기 전에 반드시 읽어 본다.** 이 한 번으로 "USIM 인가"와 "ADM1 이 맞는가"가 동시에 갈린다.

```bash
sudo ~/.venv/bin/python3 pySim-read.py -p0 | head -25
```

- `Autodetected card type: sysmoISIM-SJA5` → 우리가 아는 카드다
- 뒤쪽에 `ISIM Service Table` 과 `ADF.USIM` 이 보여야 한다. **없으면 그 카드는 쓸 수 없다**(0 절)
- `Service 122/123`(5GS) 이 있으면 5G SA 가능

ADM1 검증은 pySim-shell 에서 한다. **정식 명령으로만** 하라 —
`apdu --raw` 는 비표준 응답을 내면서도 재시도 카운터를 깎는다.

```bash
sudo ~/.venv/bin/python3 pySim-shell.py -p0
# (쉘 안에서)
verify_adm <ADM1>        # 오류가 없으면 통과. 틀리면 "N tries left" 를 알려 준다
exit
```

### 6.3 쓰기

가입자 3 번(차폐함 안 단말)을 예로 든다. 값은 `lab.env` 에서 꺼내 쓴다.

```bash
cd ~/work/pysim
set -a; source ~/work/private5g/configs/secrets/lab.env; set +a

sudo ~/.venv/bin/python3 pySim-prog.py -p0 -t sysmoISIM-SJA5 -a "$UE3_ADM1" \
  -x 001 -y 01 --mnclen 2 -n P5G \
  -i "$UE3_IMSI" -k "$UE3_KI" -o "$UE3_OPC" \
  -M e1ffffffffffffffffffffffff06815384090067ffffffffff000000 \
  --msisdn 821099994533 \
  --ims-hdomain ims.mnc001.mcc001.3gppnetwork.org \
  --impi "$UE3_IMSI@ims.mnc001.mcc001.3gppnetwork.org" \
  --impu "sip:$UE3_IMSI@ims.mnc001.mcc001.3gppnetwork.org"
```

각 인자의 뜻과 함정:

| 인자 | 뜻 | 주의 |
|---|---|---|
| `-t sysmoISIM-SJA5` | 카드 종류 | Ki 는 카드마다 다른 **전용 파일**에 들어가므로 종류가 맞아야 한다 |
| `-x 001 -y 01 --mnclen 2` | MCC/MNC 와 MNC 자릿수 | `EF.AD` 의 MNC 길이까지 맞춰 준다 |
| `-n P5G` | 사업자 이름(SPN) | 단말 상태바에 뜬다 |
| `-i / -k / -o` | IMSI / Ki / OPc | **HSS 에 넣은 값과 같아야 한다** |
| `-M …` | EF.SMSP 원본 보존 | 생략하면 pySim 기본 SMSC(+1555…)로 덮인다. 우리 SMSC 는 SIP 전용이라 E.164 번호가 없다 |
| `--ims-hdomain/--impi/--impu` | ISIM 신원 | VoNR·IMS 에 필요 |
| (ICCID) | — | **이 카드 타입에서는 쓸 수 없다.** 경고만 내고 넘어간다. 공장값을 그대로 쓴다 |

> **클론(같은 IMSI 두 장)은 만들지 않는다.** 코어가 한 가입자로 보기 때문에 나중에 붙은
> 쪽이 앞선 쪽을 밀어낸다. 단말이 둘이면 가입자도 둘이어야 한다.

### 6.4 쓴 값 확인

읽을 수 있는 것부터 본다.

```bash
sudo ~/.venv/bin/python3 pySim-read.py -p0 | grep -iE 'ICCID|^IMSI|SPN|PLMNwAcT|Home Network Domain|IMS private|IMS public'
```

기대값:

```
ICCID: 894944…                 (공장값 그대로)
IMSI:  001011234567897
SPN:   P5G
PLMNwAcT: 00f110ffff           ← MCC 001 / MNC 01
Home Network Domain Name: ims.mnc001.mcc001.3gppnetwork.org
IMS private user identity: 001011234567897@ims…
IMS public user identity:  sip:001011234567897@ims…
```

### 6.5 Ki 가 제대로 심겼는지 확인 — 유일한 방법

**Ki 는 카드에서 읽을 수 없다.** 그래서 카드에게 직접 인증을 시켜 보는 것이 유일한 검증이다.
단말에 꽂아 보고 "안 붙네" 하는 것보다 훨씬 빠르고 원인이 분명하다.

① 임의의 RAND 와 SQN 에 대해 기대값을 계산한다.

```bash
cd ~/work/private5g
set -a; source configs/secrets/lab.env; set +a
python3 - <<'PY'
import os, sys
sys.path.insert(0, 'tools')
from milenage import f1, f2345, xor
ki, opc = bytes.fromhex(os.environ['UE3_KI']), bytes.fromhex(os.environ['UE3_OPC'])
rand = bytes.fromhex('00112233445566778899aabbccddeeff')
sqn, amf = bytes.fromhex('000000000020'), bytes.fromhex('8000')   # SQN 32
maca, _ = f1(ki, opc, rand, sqn, amf)
res, ck, ik, ak, _ = f2345(ki, opc, rand)
print('RAND', rand.hex())
print('AUTN', (xor(sqn, ak) + amf + maca).hex())
print('기대 RES', res.hex(), '\n기대 CK ', ck.hex(), '\n기대 IK ', ik.hex())
PY
```

② 그 값을 카드에 넣는다.

```bash
cd ~/work/pysim
printf 'select ADF.USIM\nauthenticate <RAND> <AUTN>\n' > /tmp/auth.script
sudo ~/.venv/bin/python3 pySim-shell.py -p0 --script /tmp/auth.script
```

③ 카드가 돌려준 `res`/`ck`/`ik` 가 계산값과 **같으면 Ki·OPc 가 정확히 들어간 것이다.**

```json
{"successful_3g_authentication": {"res": "…", "ck": "…", "ik": "…", "kc": "…"}}
```

④ **이 시험으로 카드의 SQN 이 올라간다.** HSS 쪽 SQN 을 그보다 크게 맞춰 두면 첫 접속에서
재동기(AUTS) 왕복이 생기지 않는다.

```bash
docker exec mongo mongosh --quiet open5gs --eval \
 'db.subscribers.updateOne({imsi:"001011234567897"},{$set:{"security.sqn":NumberLong("64")}})'
curl -s -X PATCH http://127.0.0.1:8080/auc/3 -H 'Content-Type: application/json' -d '{"sqn":64}'
```

> 실패 시 읽는 법 — `authenticate` 가 `synchronisation_failure` 를 내면 **SQN 이 낮은 것**이지
> Ki 가 틀린 게 아니다. SQN 을 올려 다시 해 본다. `res` 가 **다르게** 나오면 그때가 Ki·OPc 불일치다.

## 7. RF 배선

- B210 **TX/RX(1번)** → 30 dB 감쇠 → 차폐함 SMA 관통 → 안쪽 안테나
- B210 **RX2(2번)** → 감쇠기 → 차폐함 SMA 관통 → 안쪽 안테나
- 안 쓰는 단자는 **전부 50 Ω 종단**. 커넥터는 손으로 끝까지 조인다
- 케이블 길이와 감쇠값을 **적어 둔다.** 나중에 링크 예산이 안 맞을 때 이 기록이 유일한 단서다

자세한 것은 [docs/rf-cabling.md](docs/rf-cabling.md).

## 8. 기지국

```bash
cd upstream && docker compose -p docker_open5gs -f srsgnb.yaml up -d
docker logs srsgnb | tail -5
```

`==== gNB started ===` 와 `N2: Connection to AMF … completed` 가 보여야 한다.

**로그 레벨을 `info` 로 둔다.** `warning` 이면 RACH·RRC 가 안 찍혀서 단말이 붙는지
판단조차 못 한다. `configs/srsran/gnb.yml.in` 의 `all_level`.

**확인** — `docker logs srsgnb | grep -c LIBUSB` 가 0 이고 `Operating over USB 3.` 이 있다.

## 9. 단말 붙이기

모뎀은 [docs/modem.md](docs/modem.md), 차폐함 안 단말은
[docs/shieldbox-phone.md](docs/shieldbox-phone.md).

차폐함 안 단말은 **USB 관통으로 제어할 수 없다** — 필터패널이 LC 저역통과라 USB 2.0
하이스피드 열거가 실패한다(충전만 된다). **RJ45 관통 + USB-C 랜 어댑터로 유선 adb** 를 쓴다.

단말 쪽에서 반드시 해야 하는 셋:

```bash
adb shell settings put global captive_portal_mode 0             # "인터넷 사용 불가" 제거
adb shell settings put global captive_portal_detection_enabled 0
adb shell settings put global mobile_data_always_on 1            # 유선 adb 가 셀룰러를 막는다
```

APN 도 넣어야 한다(`numeric=00101`, `apn=internet`, `type=default,supl,mms`).
MMS 까지 쓰려면 `mmsc` 칸이 **비어 있으면 안 된다**(아래 트러블슈팅 참조).

## 10. 동작 확인

```bash
./bin/selftest.sh
PID=$(docker inspect -f '{{.State.Pid}}' oainrue)
sudo nsenter -t $PID -n ~/.venv/bin/python3 tools/ims_call.py 172.22.0.21 <UE IP> both 10
python3 tools/ims_sms_mt.py 172.22.0.20 821099994533 821099994531 "재구축 확인"
```

`selftest.sh` 의 기대 출력:

```
1. 코어 기동 + 준비 대기          OK   코어 준비 완료 (NF 5/5, 10초)
2. RAN 기동 (n78)                 OK
3. UE 접속 (최대 60초)            OK   IPv4: 10.46.0.2
4. 터널 인터페이스 oaitun_ue1      OK   10.46.0.2
5. 사용자 평면 (UPF 게이트웨이)    OK   10.46.0.1 0% packet loss
5b. 외부 통신 (참고)              OK   건너뜀 — 이 UE 는 ims DNN
6. 정본 vs 런타임 설정 일치        OK   차이 0 건
=== 전체 통과 ===
```

> `selftest.sh` 는 **끝나면서 코어와 RAN 을 내린다.** 실물 단말로 작업 중이라면
> 끝난 뒤 `./bin/core-ctl.sh START` 와 기지국을 다시 올려야 한다.
>
> 5b 가 "건너뜀"인 것은 정상이다. 이 모의 UE 는 IMS 시험용이라 `ims` DNN 을 쓰고,
> IMS 망은 외부 인터넷으로 라우팅되지 않는다. 외부 통신은 모뎀이나 실물 단말로 확인한다.

**로그에 "통화 성립 ✅" 이 찍혀도 RTP 가 0 이면 성립한 게 아니다.** 반드시 패킷 수를 본다.

---

# 트러블슈팅 — 가장 오래 걸렸던 곳들

구축하면서 실제로 시간을 가장 많이 먹은 순서다. 전체 사례와 추적 과정은
[docs/book/13-트러블슈팅사례집.md](docs/book/13-트러블슈팅사례집.md) 에 스물두 건으로 있다.

### ① 카드가 USIM 이 아니었다 (며칠)
증상이 "ADM 이 안 맞는다"로 보여서 ADM 키를 쫓았다. 실제로는 USIM 애플리케이션 자체가
없는 2G 카드였다. **`pySim-read.py` 로 `ADF.USIM` 유무부터 본다.** 1 분이면 끝난다.

### ② 엉뚱한 SDR 로 송신했다 (9 분 송신 + 반나절)
안테나가 달린 다른 SDR 이 같은 호스트에 꽂혀 있었고, 설정에 시리얼이 없어서 그쪽이
열렸다. **`gnb.yml` 의 `device_args` 에 `serial=` 이 없으면 띄우지 말 것.**
그리고 B210 이 USB 2.0 으로 뜬다면 포트가 아니라 **케이블**을 먼저 의심하라 —
USB 2.0 Micro-B 케이블이 범인이었고 반나절을 먹었다.

### ③ `500 Server error on LIR select next S-CSCF` (두 시간, 그리고 재발)
문구는 LIR 실패처럼 읽히지만 **LIR 은 성공이었다.** 그 문구는 Kamailio 설정에서
`t_check_status("(408)")` 블록 안에 있다 — 다음 홉이 타임아웃했다는 뜻이다. 진짜 원인은
**P-CSCF 가 단말에 TCP 로 보내는데 우리 UA 가 UDP 만 듣고 있던 것**이었다. IMS 는 홉마다
헤더가 붙어 INVITE 가 1300 바이트를 넘고, 그러면 RFC 3261 §18.1.1 에 따라 TCP 로 간다.
**IMS 단말은 TCP 를 반드시 들어야 한다.**
> 넉 달 뒤 같은 증상이 재발했다. 도구 안에 **UDP 만 듣는 두 번째 코드 경로**가 남아
> 있었고, SDP 가 커지자 드러났다. 경로가 둘이면 한쪽만 고쳐진다.

### ④ 세션이 올라오자마자 끊기고 100 초마다 반복 (srsRAN + 실물 단말)
`docker logs srsgnb | grep "Unsupported PDU Session"` → **srsRAN gNB 는 IPv4v6 PDU 세션을
지원하지 않는다.** 가입자 세션 타입을 **1(IPv4)** 로 바꾼다. 단말은 "끊긴다"고만 하고
코어는 "만들었다 지웠다"만 찍는다. **거부한 계층(기지국)의 로그를 봐야 한다.**

### ⑤ 빈 데이터베이스에서 가입자 등록이 깨진다
```
IntegrityError (1452) … FOREIGN KEY (`default_apn`) REFERENCES `apn` (`apn_id`)
```
PyHSS 의 가입자는 APN 행을 참조한다. **APN 부터 만들어야 한다.**
`bin/provision-subscribers.sh` 가 그 순서를 지킨다. 이 함정은 **처음 구축할 때만**
나타나기 때문에, 이미 돌아가는 랩에서는 평생 안 보인다.

### ⑥ 실물 단말이 통화를 거절한다 (`488 Not Acceptable Here`)
모의 UE 끼리는 몇 달째 잘 되던 통화다. 실물은 넷을 요구한다.
**AMR-WB/AMR 코덱**(G.711 거절), **PRACK**(183 이 `Require: 100rel`),
**QoS 전제조건 선언**, 그리고 **SDP 응답이 `200 OK` 가 아니라 `183` 에 온다**는 것.
`488` 을 받으면 P-CSCF 로그의 `Source IP` 로 **누가 거절했는지**부터 가른다.

### ⑦ 유선 adb 를 깔았더니 셀룰러 데이터가 안 선다
라디오 로그에 `Re-evaluating 0 unsatisfied network requests`. 제어용으로 꽂은
**이더넷이 기본 인터넷 요청을 이미 만족시켜서** 안드로이드가 셀룰러를 요청조차 안 한다.
`mobile_data_always_on=1`. **관측 장치가 관측 대상을 바꾼 경우다.**

### ⑧ MMS 가 "유효한 APN 이 없다"고 한다
APN 의 **`mmsc` 칸이 비면 그 행이 통째로 무시된다**(`ApnSettings.load`). 그런데
`content insert --bind mmsc:s:http://...` 는 **값의 콜론에서 파서가 깨진다.**
결국 APN 편집 화면을 adb 로 조작해 넣었고, 대화상자 "확인"만으로는 DB 에 안 들어가고
**메뉴의 저장**을 눌러야 한다. 그리고 같은 Transaction-Id 나 같은 Content-Location URL 로
다시 보내면 단말이 **중복으로 보고 버린다.**

### ⑨ ModemManager 가 세션을 죽인다
`mmcli -L` 로 확인. 마스크하거나 udev 로 제외한다. 증상이 간헐적이라 RF 나 코어를
의심하게 만든다.

### ⑩ "됐다"가 틀린 기록이었다
빈 출력을 성공으로 읽은 적이 여러 번 있다. 비밀값 검사가 조용히 통과한 적도 있다
(`git grep` 의 `--cached` 를 `--` 뒤에 둬서 경로 지정으로 먹혔다).
**없는 것을 확인하는 검사는 검사 자체가 작동했는지를 따로 증명해야 한다.** 성질이 다른
검사를 하나 더 붙이거나, 반드시 걸려야 하는 것을 일부러 넣어 걸리는지 본다.

---

## 디렉터리

```
private5g/
├── bin/            제어 스크립트 (실행은 여기서만)
├── compose/        우리 docker compose
├── configs/        설정 정본 — 고칠 때는 반드시 여기
│   ├── secrets/    실키·호스트 고유값 (추적 안 함)
│   ├── db/         가입자 프로파일 템플릿
│   └── _backup/    로컬 변경 백업 (추적 안 함)
├── docs/           구축·측정·사례 문서, 화면 증거, 그리고 책
└── upstream ->     docker_open5gs 클론 (심볼릭, 추적 안 함)
```

## 문서

| 문서 | 내용 |
|---|---|
| [docs/REBUILD.md](docs/REBUILD.md) | 재구축 절차 (이 README 의 상세판) |
| [docs/sim-cards.md](docs/sim-cards.md) | USIM 구매·발급·검증, 쓸 수 없던 카드 기록 |
| [docs/shieldbox-phone.md](docs/shieldbox-phone.md) | 차폐함 안 단말 제어와 유선 adb |
| [docs/sim-vs-real.md](docs/sim-vs-real.md) | 시뮬레이션과 실물의 간극 일곱 가지 |
| [docs/mms-and-video.md](docs/mms-and-video.md) | 영상통화와 MMS |
| [docs/shielding-measurement.md](docs/shielding-measurement.md) | 차폐함 누설 계측 |
| [docs/rf-cabling.md](docs/rf-cabling.md) | RF 배선 |
| [docs/frequency-plan.md](docs/frequency-plan.md) | 주파수 계획 |
| [docs/book/](docs/book/) | 책 《로컬 5G 망 구축》 (별도 저장소) |

## 추적하지 않는 것

| 경로 | 이유 |
|---|---|
| `configs/secrets/lab.env` | 실키·호스트 고유값 |
| `configs/env/env`, `configs/oai/nr-ue.n78.rfsim.conf`, `configs/srsran/gnb.yml` | `*.in` 에서 렌더되는 결과물 |
| `configs/_backup/` | 로컬 안전 사본. 과거 실키가 들어 있다 |
| `docs/book/` | 별도 저장소 (`AmesianX/local-5g-handbook`) |
| `upstream` | 업스트림 클론으로 가는 심볼릭 링크 |
