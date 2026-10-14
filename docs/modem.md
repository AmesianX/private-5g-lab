# 모뎀 — Quectel RM520N-GL

2026-10-05 입고·식별.

## 식별 정보

| 항목 | 값 |
|---|---|
| 모델 | **Quectel RM520N-GL** (M.2 Key-B) |
| USB ID | `2c7c:0801` |
| 펌웨어 | `RM520NGLAAR03A03M4G` |
| IMEI | 868371054749623 |
| 지원 모드 | gsm-umts, lte, **5gnr** (SA 가능) |
| SIM 슬롯 | 2개 (slot 1 active) |

## 연결 — 외부 전원이 필수였다

**USB만 꽂으면 커널 이벤트가 0건이다.** 열거조차 안 된다.
M.2 캐리어가 모듈 3.3V 레일을 외부 DC 에서만 만들기 때문. USB 는 데이터만 넘긴다.

```
모듈 장착 → 캐리어 DC 전원 → USB 연결
```

전원 넣으면 이렇게 뜬다:

```
usb 7-1: Product: RM520N-GL / Manufacturer: Quectel
ttyUSB0 (ignored)  ttyUSB1 (gps)  ttyUSB2 (at)  ttyUSB3 (at)
cdc-wdm0 (qmi)     wwan0 (net)
```

소비전류 참고: 대기 50~200mA @3.3V, **송신 피크 2~3A @3.3V (7~10W)**.
USB 3.0 은 4.5W 뿐이라 송신을 못 버틴다.

## AT 커맨드 쓰는 법

ModemManager 가 `ttyUSB2` 를 점유한다. **`ttyUSB3` 을 쓰면 충돌 없다.**
`minicom`/`picocom`/`socat` 이 이 머신에 없어서 아래 함수로 쓴다:

```bash
PORT=/dev/ttyUSB3
at() {
  sudo stty -F $PORT 115200 raw -echo 2>/dev/null
  { printf '%s\r' "$1" | sudo tee $PORT >/dev/null; sudo timeout 2 cat $PORT; } 2>/dev/null \
    | tr -d '\r' | grep -vE "^$|^$1$"
}
at "ATI"
```

## 밴드 — n78 지원 확인

```
+QNWPREFCFG: "nr5g_band",1:2:3:5:7:8:12:13:14:18:20:25:26:28:29:30:38:40:41:48:66:70:71:75:76:77:78:79
```

**n78 활성.** 우리 주파수 계획(SSB 623328 = 3349.92 MHz) 그대로 사용 가능.
`n3` 도 있어 srsRAN n3 ZMQ 구성과도 호환.

## 통신사 프로파일 — 바꿔야 한다

현재 **KDDI(일본) 전용 설정**으로 묶여 있다. 통신사 프로파일은 밴드·PLMN 동작을 제한할 수 있다.

```
+QMBNCFG: "List",0,1,1,"Commercial-KDDI"              ← 현재 활성
+QMBNCFG: "List",5,0,0,"ROW_Generic_3GPP_PTCRB_GCF"   ← 시험망용으로 이것
+QMBNCFG: "List",1,0,0,"ROW_Commercial"
```

변경 (모뎀 리셋 필요, **사용자 승인 후 실행**):

```bash
at 'AT+QMBNCFG="select","ROW_Generic_3GPP_PTCRB_GCF"'
at 'AT+CFUN=1,1'      # 모뎀만 리셋 (호스트 재부팅 아님)
```

## 시험 전 권장 설정 (상용망 접속 방지 겸용)

```bash
at 'AT+QNWPREFCFG="mode_pref",NR5G'   # SA 전용. LTE 탐색 안 함
at 'AT+QNWPREFCFG="nr5g_band",78'     # n78 만. 상용 밴드 스캔 자체를 막음
```

밴드를 n78 로 좁히는 건 **셀 탐색을 빠르게 하고, 모뎀이 한국 상용 대역을
뒤지는 것을 막는 효과**가 있다. 되돌릴 때는 위 전체 밴드 목록을 다시 넣는다.

## 2026-10-05 실측으로 확인된 것

### RF 경로 검증 완료 — 모뎀이 우리 셀을 봤다

```
AT+COPS=?
+COPS: (1,"KOR LG Uplus","45006",7),
       (1,"KT","45008",7),
       (1,"450 30","45030",7),
       (1,"Test PLMN 1-1","Test1-1","00101",12)   ← 우리 셀, AcT 12 = NR SA
```

이것으로 아래가 전부 증명됐다:

| 항목 | 결과 |
|---|---|
| B210 송신 (3350.01 MHz n78) | 정상 |
| 동축 + 감쇠기 + MHF4 피그테일 | 정상 (신호가 통과함) |
| 모뎀 ANT1 포트 선택 | 맞음 |
| 주파수 계획 | 맞음 (상용 3사와 분리되어 탐지) |
| gNB ↔ AMF (N2) | 정상 |

**SIM 없이도 셀 탐색은 된다.** 이 검증에 SIM 이 필요 없었다.

### 스캔이 처음에 실패했던 이유 (장비 탓 아님)

둘 다 설정 실수였다:

1. **`tx_gain: 40` 이 너무 낮았다** → 65 로 올리니 잡혔다
2. **`mode_pref=NR5G` 를 설정만 하고 모뎀 리셋을 안 했다** → NR 탐색이 안 돌고 LTE 만 긁었다.
   `AT+CFUN=1,1` 로 리셋해야 적용된다.

### QSCAN 은 NR 을 지원하지 않는다

```
AT+QSCAN=?  →  +QSCAN: (1-3)      GSM/WCDMA/LTE 만
AT+QSCAN=2  →  즉시 OK, 결과 없음
```

**NR 셀 탐색은 `AT+COPS=?` 를 써야 한다.**

### SIM 슬롯은 정상이다

알리 공백카드를 꽂았을 때:

```
AT+CPIN?   →  +CPIN: READY
AT+QCCID   →  FFFFFFFFFFFFFFFFFFFF   (공백 카드)
```

`CPIN: READY` 가 떴으므로 **슬롯 배선·접점·삽입 모두 정상**이다.
처음에 `sim-missing` 이 나온 것은 **삽입 후 `AT+CFUN=0` → `AT+CFUN=1` 재초기화가 필요**했기 때문.
SIM 은 hot-swap 이 안 되고 모뎀이 기동 시점에 읽는다.

### 유용한 진단 커맨드

```
AT+CPIN?       SIM 상태        ERROR 10 = 미삽입
AT+QCCID       ICCID           ERROR 13 = SIM 통신 실패
AT+CIMI        IMSI            ERROR 15 = SIM wrong(IMSI 없음)
AT+QINISTAT    초기화 진행도    0 = 시작 안 됨
AT+QUIMSLOT?   활성 슬롯        (1,2) 중 선택
AT+QSIMDET?    삽입감지 설정
AT+COPS=?      PLMN 탐색 (NR 포함, 60~100초 소요)
AT+CREG? / AT+C5GREG?   LTE / 5G 등록 상태
```

ModemManager 가 `ttyUSB2`(때로 `ttyUSB3` 까지) 를 점유한다.
점유 중이면 `mmcli` 로 조회하거나 ModemManager 를 잠시 멈춘다.

## 현재 블로커

| 항목 | 상태 |
|---|---|
| 모뎀 | **확보·동작 확인** |
| n78 지원 | **확인** |
| **프로그래머블 USIM** | **없음** — `+CPIN: NOT INSERTED`, 슬롯 2개 모두 비어 있음 |
| **PC/SC 카드 리더** | **없음** — `pcsc_scan: No reader found`, pcscd inactive |
| pySim | 리포는 있음 (`sdr-tools/sim/pysim`), 모듈 미설치 |
| MHF4 피그테일 | 미확인 |
| 차폐함 / 감쇠기 | 미입고 |

## USIM 에 넣을 값

Open5GS 에 등록된 가입자 (mongo 볼륨, 재부팅 후에도 유지):

```
IMSI  001011234567895     (MCC 001 / MNC 01 / MSIN 1234567895)
```

Ki / OPc 는 `configs/env/env` 와 mongo 가입자 레코드에 있다.
USIM 쪽을 Open5GS 에 맞추거나, 반대로 카드의 기존 Ki 를 Open5GS 에 등록해도 된다.
**sysmoUSIM 처럼 Ki 가 알려진 테스트 카드라면 후자가 간단하다.**

관련: [[rf-cabling.md]], [[frequency-plan.md]], [[status.md]]
