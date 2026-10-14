# 맨바닥에서 재구성하기

새로 산 컴퓨터에 리눅스를 깔고, 장비도 새로 사서 붙인다는 전제다. 이 문서만 따라가면
같은 망이 선다. 값이 비는 곳은 전부 `configs/secrets/lab.env` 한 파일에서 온다.

> 송신 전에 [부록 D 전파와 법규 고지](book/부록D-전파와법규고지.md)를 먼저 읽을 것.
> 공중으로 전파를 내는 순간 허가가 필요한 무선국이다.

## 0. 장비 목록

| 품목 | 우리가 쓴 것 | 비고 |
|---|---|---|
| SDR | Ettus USRP **B210** (또는 LibreSDR) | 송신에 쓸 한 대의 **시리얼을 반드시 고정**한다 |
| FPGA 이미지 | `configs/srsran/libresdr_alphafox02.bin` | 저장소에 포함. LibreSDR 용 |
| UE(모뎀) | Quectel **RM520N-GL** + 캐리어 보드 | USB. `2c7c:0801` |
| UE(실물 단말) | 갤럭시 S22+ (SM-S9060), Magisk 루트 | 차폐함 제어용으로 루트 필요 |
| USIM | **sysmoISIM-SJA5**, `with ADM keys` 로 주문 | ADM1 을 이메일로 받는다 |
| 카드 리더 | PC/SC CCID (Identiv SCR35xx 등) | `pcscd` |
| 차폐함 | TOJOIN MS3020-A | SMA 관통 4, 필터패널(RJ45/USB/DB9/DC) |
| 감쇠기 | 30 dB · 40 dB SMA | 송신 경로용 |
| 종단기 | 50 Ω SMA | 안 쓰는 단자 전부 |
| USB-C 랜 어댑터 | RTL8153 계열 | 차폐함 안 폰의 유선 adb 용 |

**USB 관통으로는 폰을 제어할 수 없다.** 필터패널이 LC 저역통과라 USB 2.0 하이스피드
열거가 실패한다(충전만 된다). 반드시 RJ45 관통 + USB-C 랜 어댑터로 간다.

## 1. 호스트 선행 설치

```bash
sudo apt update
sudo apt install -y docker.io docker-compose-v2 git python3-pip pcscd pcsc-tools \
                    android-tools-adb nmap avahi-utils uhd-host
sudo usermod -aG docker "$USER"      # 재로그인 필요
sudo uhd_images_downloader           # UHD FPGA/펌웨어
sudo systemctl enable --now pcscd
```

**ModemManager 를 반드시 비켜 세운다.** 그대로 두면 모뎀의 QMI 세션을 가로채 죽인다.

```bash
sudo systemctl mask ModemManager        # 또는 udev 규칙으로 해당 장치만 제외
```

파이썬 도구는 전용 가상환경에 둔다(전역 설치 금지).

```bash
python3 -m venv ~/.venv && ~/.venv/bin/pip install pyscard
```

## 2. 저장소와 업스트림

```bash
git clone <이 저장소> ~/work/private5g
mkdir -p ~/work/sdr-tools/docker
git clone https://github.com/herlesupreeth/docker_open5gs.git \
          ~/work/sdr-tools/docker/docker_open5gs
git -C ~/work/sdr-tools/docker/docker_open5gs checkout 1f3bcf7
ln -s ../sdr-tools/docker/docker_open5gs ~/work/private5g/upstream
```

업스트림은 **클론 그대로 두고 건드리지 않는다.** 우리 변경은 전부 `configs/` 가 정본이고
`bin/deploy-configs.sh` 가 그 트리로 배포한다. 클론에서 직접 고치면 다음 배포에 덮인다.

## 3. 컨테이너 이미지

ghcr.io 에서 받는다(직접 빌드하지 않았다).

```
ghcr.io/herlesupreeth/docker_open5gs:master
ghcr.io/herlesupreeth/docker_kamailio:master
ghcr.io/herlesupreeth/docker_pyhss:master
ghcr.io/herlesupreeth/docker_rtpengine:master
ghcr.io/herlesupreeth/docker_mysql:master
ghcr.io/herlesupreeth/docker_dns:master
ghcr.io/herlesupreeth/docker_metrics:master
ghcr.io/herlesupreeth/docker_srsran:master
oaisoftwarealliance/oai-gnb:2026.w38
oaisoftwarealliance/oai-nr-ue:2026.w38
mongo:6.0
```

업스트림이 태그를 옮기거나 지울 수 있으므로, **우리가 돌렸던 이미지 자체를 이 저장소의
릴리즈에 올려 두었다.** 그쪽이 더 확실하다.

```bash
# 릴리즈에서 받은 뒤
zstd -d -c open5gs-images.tar.zst | docker load
```

## 4. 비밀값 채우기

```bash
cp configs/secrets/lab.env.example configs/secrets/lab.env
chmod 600 configs/secrets/lab.env
$EDITOR configs/secrets/lab.env
```

- `DOCKER_HOST_IP` — 호스트의 LAN 주소
- `B210_SERIAL` — `uhd_find_devices` 로 확인. **송신에 쓸 그 한 대**의 시리얼
- `PHONE_IP` — 차폐함 안 폰에 줄 고정 주소
- `UE*_KI` / `UE*_OPC` — 카드 공급사가 준 값
- `UE3_ADM1` / `UE3_ICCID` — 카드 발급에 쓴다

이 파일이 없으면 `deploy-configs.sh` 가 **무엇이 비었는지 적고 멈춘다.** 저장소에는
`*.in` 템플릿만 있고 실제 설정 파일은 렌더 결과라 추적하지 않는다.

## 5. 설정 배포와 코어 기동

```bash
cd ~/work/private5g
./bin/deploy-configs.sh --check    # 차이만 확인
./bin/deploy-configs.sh            # 렌더 + 배포
./bin/core-ctl.sh START            # NF 5/5 까지 대기
./bin/provision-subscribers.sh     # 가입자 3명 (mongo + PyHSS)
./bin/provision-subscribers.sh --check
```

`provision-subscribers.sh` 는 멱등이다. PyHSS 는 PUT 할 때마다 행이 새로 생기므로
같은 IMSI 가 있으면 그 id 로 PATCH 한다. 가입자 프로파일은
`configs/db/subscriber.template.json` 이고 **세션 타입은 반드시 1(IPv4)** 이다 —
srsRAN gNB 가 IPv4v6 PDU 세션을 거부한다.

## 6. USIM 발급

리더에 카드를 꽂고(ADM1 은 `lab.env` 의 `UE3_ADM1`):

```bash
cd /path/to/pysim
sudo ~/.venv/bin/python3 pySim-prog.py -p0 -t sysmoISIM-SJA5 -a <ADM1> \
  -x 001 -y 01 --mnclen 2 -n P5G \
  -i 001011234567897 -k <KI> -o <OPC> \
  --msisdn 821099994533 \
  --ims-hdomain ims.mnc001.mcc001.3gppnetwork.org \
  --impi 001011234567897@ims.mnc001.mcc001.3gppnetwork.org \
  --impu sip:001011234567897@ims.mnc001.mcc001.3gppnetwork.org
```

- ICCID 는 이 카드 타입에서 쓸 수 없다. 공장값을 그대로 쓴다.
- EF.SMSP 는 공장값을 `-M` 으로 보존한다. 우리 SMSC 는 SIP 전용이라 E.164 번호가 없다.
- **클론(같은 IMSI 두 장)은 쓰지 않는다.** 코어가 한 가입자로 보기 때문에 나중에 붙은
  쪽이 앞선 쪽을 밀어낸다. 단말이 둘이면 가입자도 둘이어야 한다.

심은 키가 맞는지는 **카드에 직접 인증을 시켜** 확인한다. 자세한 것은
[sim-cards.md](sim-cards.md).

## 7. RF 배선

[rf-cabling.md](rf-cabling.md) 와 [shieldbox-phone.md](shieldbox-phone.md) 참고. 요점만:

- B210 **TX/RX(1번)** → 30 dB 감쇠 → 차폐함 SMA 관통 → 안쪽 안테나
- B210 **RX2(2번)** → 감쇠기 체인 → 차폐함 SMA 관통 → 안쪽 안테나
- 안 쓰는 단자는 **전부 50 Ω 종단**
- 안테나가 달린 다른 SDR 이 같은 호스트에 꽂혀 있다면, 그 장치는 이번 실행에서
  절대 열리지 않아야 한다. `gnb.yml` 의 `serial=` 이 그 안전장치다.

## 8. 기지국

```bash
cd upstream && docker compose -p docker_open5gs -f srsgnb.yaml up -d
docker logs srsgnb | tail -5      # "==== gNB started ===" 확인
```

로그 레벨은 `info` 로 두었다. `warning` 이면 RACH·RRC 가 안 찍혀서 단말이 붙는지
판단조차 못 한다.

## 9. 단말 붙이기

모뎀은 [modem.md](modem.md), 차폐함 안 폰은
[shieldbox-phone.md](shieldbox-phone.md) 를 따른다. 폰 쪽에서 반드시 해야 하는 셋:

```bash
adb shell settings put global captive_portal_mode 0            # "인터넷 사용 불가" 제거
adb shell settings put global captive_portal_detection_enabled 0
adb shell settings put global mobile_data_always_on 1          # 유선 adb 가 셀룰러를 막는다
```

APN(numeric 00101, apn=internet)도 넣어야 한다. 셋 다 이유가 있고 그 이유는
[shieldbox-phone.md](shieldbox-phone.md) 에 적혀 있다.

## 10. 동작 확인

```bash
./bin/selftest.sh
PID=$(docker inspect -f '{{.State.Pid}}' oainrue)
sudo nsenter -t $PID -n ~/.venv/bin/python3 tools/ims_call.py 172.22.0.21 <UE IP> both 10
python3 tools/ims_sms_mt.py 172.22.0.20 821099994533 821099994531 "재구성 확인"
```

기대값과 함정은 [sim-vs-real.md](sim-vs-real.md) 에 있다. 특히 **로그에 "통화 성립 ✅"
이 찍혀도 RTP 가 0이면 성립한 게 아니다.**

## 추적하지 않는 것

| 경로 | 이유 |
|---|---|
| `configs/secrets/lab.env` | 실키·호스트 고유값 |
| `configs/env/env`, `configs/oai/nr-ue.n78.rfsim.conf`, `configs/srsran/gnb.yml` | `*.in` 에서 렌더되는 결과물 |
| `configs/_backup/` | 로컬 안전 사본. 과거 실키가 들어 있다 |
| `docs/book/` | 별도 저장소(`AmesianX/local-5g-handbook`) |
| `upstream` | 업스트림 클론으로 가는 심볼릭 링크 |
