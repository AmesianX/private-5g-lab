# 여기서부터 이어서 한다

마지막 작업: **2026-10-15** (책 검수·정정은 2026-10-21, `docs/book/`)
중단 사유: **없음. 차폐함 안 실물 단말까지 끝났다.** 남은 건 그 구성의 처리량(iperf3) 한 줄.

---

## 한 줄 요약

**차폐함 안 실물 갤럭시 S22+ 로 등록·데이터·전화·문자·MMS·영상통화가 전부 통했다.**

구성이 둘이라는 점을 먼저 본다.

- **모뎀 + 동축 직결(40 dB)** — DL 55 / UL 11 Mbps, RTT 38 ms. 처리량 숫자는 전부 이 구성이다.
- **폰 + 차폐함(30 dB → SMA 관통 → 안쪽 안테나)** — RTT 25~31 ms, 외부 54~58 ms, 손실 0 %.
  통화·문자(UDH 270자 병합)·MMS 양방향·영상통화까지. **처리량(Mbps)만 안 쟀다.**

상자 자체의 누설은 켬/끔 차 0.3 dB 이내로 검출 한계 아래(`docs/shielding-measurement.md`).
상세: 메모리 `project_private5g_e2e_done`, `project_private5g_ims_call_recipe`.

---

## 1. 어디까지 됐나

| 단계 | 상태 | 증거 |
|---|---|---|
| 5GC + IMS(VoNR) 24 컨테이너 | **완료** | 전부 Up, NF 5/5 연결 |
| IMS 등록 | **완료** | 200 OK, `tel:9076543210` |
| MILENAGE 독립 구현 검증 | **완료** | PyHSS 로그와 바이트 일치 |
| n78 종단간 (소프트 UE, rfsim) | **완료** | 등록→PDU세션→ping 8.8.8.8 37ms |
| n3 종단간 (srsUE, ZMQ) | **완료** | PDU Session IP 192.168.101.2 |
| 작업물 `private5g/` 통합 | **완료** | 스크립트·설정·문서 한 곳 |
| **B210 실제 RF 송신** | **완료** | 3350.01 MHz n78, LibreSDR FPGA |
| **RF 경로 (동축+감쇠기+MHF4)** | **완료** | 모뎀이 `00101` 셀 탐지 |
| **모뎀 SIM 슬롯** | **완료** | `CPIN: READY` 확인 |
| **모뎀 접속 (RACH→인증→PDU)** | **완료** | AMF `Registration complete`, IP 10.45.0.x, ping 8.8.8.8 |
| **처리량 실측** | **완료** | DL 55 / UL 11 Mbps, RTT 38ms (20MHz 1T1R 상한 부합) |
| **UE IP 대역 변경** | **완료** | 10.45.0.0/16(internet) / 10.46.0.0/16(ims) |
| **IMS 등록 (양쪽)** | **완료** | `tel:821099994531` / `tel:821099994532` 200 OK |
| **IMS 통화 (INVITE~RTP)** | **완료** | 모뎀 ↔ nr-UE, `tools/ims_call.py` |
| **차폐함 누설 계측** | **완료** | 켬/끔 차 0.3 dB 이내, 양성 대조로 계통 확인 (`docs/shielding-measurement.md`) |
| **차폐함 안 실물 폰** | **완료** | `HOME`/NR/001-01, RTT 25~31 ms, 손실 0 % (`docs/shieldbox-phone.md`) |
| **실물 폰 통화·문자** | **완료** | AMR-WB+PRACK+전제조건, UDH 270자 한 통 병합 (`docs/sim-vs-real.md`) |
| **MMS·영상통화** | **완료** | 양방향, JPEG SHA256 동일 (`docs/mms-and-video.md`) |
| **차폐함 구성의 처리량** | **미완** | **← 여기서부터.** 폰에서 `iperf3` 로 DL/UL. 케이블 경로(55/11)와는 다른 구성의 첫 측정이다 |

---

## 2. 카드 쓰기 절차 (참고 — 카드는 이미 발급해 쓰고 있다)

### 2-1. 카드 쓰기

sysmocom 이 **카드별 ADM1 키를 이메일로** 보내준다. 그걸로:

```bash
cd /home/user/work/sdr-tools/sim/pysim
sudo systemctl start pcscd

# 읽기 확인
sudo /home/user/.venv/bin/python3 pySim-shell.py -p0 -A <ADM1>

# 쓰기
sudo /home/user/.venv/bin/python3 pySim-prog.py -p0 \
  -a <ADM1> -t sysmoISIM-SJA5 \
  -i 001011234567895 \
  -k <KI> \
  --opc <OPC> \
  -s <ICCID> --mcc 001 --mnc 01
```

**가입자는 Open5GS 에 이미 등록돼 있다** (mongo 볼륨, 재부팅해도 유지):

```
IMSI  001011234567895
K     <KI>  (configs/secrets/lab.env)
OPc   <OPC> (configs/secrets/lab.env)
AMF   8000
```

### 2-2. 망 기동

```bash
cd /home/user/work/private5g
bin/core-ctl.sh START              # 코어. NF 수렴까지 자동 대기(약 10초)
cd upstream && docker compose -p docker_open5gs -f srsgnb.yaml up -d
docker logs srsgnb | tail -20      # "gNB started" 확인
```

> `bin/ran-ctl.sh` 는 시뮬레이션용(rfsim/ZMQ)이다.
> **B210 실장비 gNB 는 아직 ran-ctl 에 프로파일이 없다** — 위처럼 직접 띄운다.
> (할 일: `ran-ctl.sh` 에 `b210` 프로파일 추가)

### 2-3. 카드를 모뎀에 꽂고 접속

```bash
# SIM 삽입 후 반드시 재초기화 (hot-swap 안 됨)
PORT=/dev/ttyUSB3
printf 'AT+CFUN=0\r' | sudo tee $PORT ; sleep 3
printf 'AT+CFUN=1\r' | sudo tee $PORT ; sleep 10

# 확인
AT+CPIN?        → READY
AT+QCCID        → 쓴 ICCID
AT+CIMI         → 001011234567895
AT+C5GREG?      → 0,1 또는 0,5 면 등록 성공
AT+QENG="servingcell"   → 셀 정보·RSRP
```

### 2-4. 실패하면 볼 곳

```bash
docker exec amf tail -40 /open5gs/install/var/log/open5gs/amf.log
docker logs srsgnb | tail -40
```

| 증상 | 원인 |
|---|---|
| 셀은 찾는데 RACH 실패 | 모뎀 포트 잘못(ANT1 아님) 또는 상향 감쇠 과다 |
| `Authentication failure` | Ki/OPc 불일치. 카드와 mongo 값 대조 |
| `Registration reject` | 코어 준비 전 접속. `wait_core_ready` 확인 |
| 셀 자체를 못 찾음 | tx_gain, 주파수, 또는 모뎀 밴드 설정 |

---

## 3. 지금 설정 상태 (건드리지 말 것)

```
configs/srsran/gnb.yml
  dl_arfcn    623334   (3350.01 MHz, n78)
  대역폭      20 MHz,  SCS 30 kHz
  tx_gain     65       ← 40 은 너무 낮아 모뎀이 못 봤다. 65에서 탐지됨
  rx_gain     36
  device_args type=b200,fpga=/mnt/srsran/libresdr_alphafox02.bin,...
              ↑ LibreSDR 클론이라 stock 이미지 쓰면 fx3 state 5 에러
```

**모뎀 현재 설정** (`AT+QNWPREFCFG`):
```
mode_pref   NR5G      (SA 전용)
nr5g_band   78        (n78 만. 상용 밴드 스캔 방지 겸용)
```
되돌리려면 `docs/modem.md` 의 전체 밴드 목록 참조.

---

## 4. 하드웨어 배선 (그대로 유지)

```
B210 [TRXA] ──[감쇠기 40dB]──[MHF4 피그테일]── [ANT1] 모뎀
B210 RXA / TRXB / RXB  → 50Ω 종단
모뎀 ANT2 / ANT3 / ANT4 → 비움
```

- B210 은 **USB 3.0 포트**에 꽂을 것. 펌웨어 로드 전엔 USB2(`WestBridge`)로 뜨는 게 정상
- 모뎀 M.2 캐리어는 **외부 DC 전원 필수**. USB 만으로는 열거조차 안 된다

---

## 5. 카드 재고 (주의)

```
알리 공백카드 3장 = 2G GSM 전용.  4G/5G 불가.  분쟁/환불 대상
  카드 1  ADM2 소진(차단)
  카드 2  ADM2 1회 남음
  카드 3  ADM2 2회 남음
```

**pySim 으로 이 카드들에 ADM 시도 금지.** 새 후보 값이 없다. 자세한 내용 `docs/sim-cards.md`.

---

## 6. USIM 과 무관하게 남은 과제

카드 기다리는 동안 할 수 있는 것:

1. **`SMF_DNS1=8.8.8.8` → 내부 DNS 로 교체**
   통신 두절 대비 망인데 외부 DNS 를 본다. `dns` 컨테이너가 이미 떠 있다.
2. **대시보드 구성** — Grafana :3000, Open5GS WebUI :9999, Prometheus :9090 (기동만 돼 있음)
3. **`ran-ctl.sh` 에 b210 프로파일 추가** — 지금은 실장비 gNB 를 수동으로 띄워야 함
4. **IMS/VoNR 통화 경로 검증** — 소프트 UE 로 가능
5. **차폐함(TOJOIN MS3020-A) 입고 후** 실제 방사 시험

---

## 7. 안전 원칙 (변함없음)

- PLMN **001/01** 고정. 상용(450-05/06/08) 금지
- 우리 대역 3340.01~3360.01 MHz. **LG U+ 하단(3400)과 40 MHz 이격**
- TX 게인은 **최소에서 시작**해 올린다
- 업스트림 예제의 주파수는 믿지 않는다 (대부분 상용 대역 한복판)
- 송신 중 커넥터 체결/해제 금지

---

## 8. 문서 지도

| 파일 | 내용 |
|---|---|
| `README.md` | 프로젝트 전체 지도, 사용법, 이식성 |
| `NEXT.md` | **이 문서. 재개 지점** |
| `docs/sim-cards.md` | SIM 카드 현황·ADM 추적 기록·다음 카드 선정 |
| `docs/modem.md` | RM520N-GL 식별·AT 커맨드·실측 결과 |
| `docs/rf-cabling.md` | B210↔모뎀 배선·감쇠 계산 |
| `docs/frequency-plan.md` | 주파수 계획·상용 대역 이격·계산법 |
| `docs/status.md` | 과제별 진행 상황 |
| `bin/` | core-ctl / ran-ctl / deploy-configs / selftest |
| `configs/` | 설정 **정본**. 여기를 고친다 |
