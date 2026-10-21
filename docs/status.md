# 진행 상황

## 완료

- **5GC + IMS(VoNR)** 23 컨테이너 기동(+ RAN 3), 종단간 접속/PDU 세션/인터넷 확인
- **IMS 등록 200 OK** — `tel:9076543210` 할당,
  `Service-Route: <sip:orig@scscf.ims.mnc001.mcc001.3gppnetwork.org:6060;lr>`
- **MILENAGE 독립 구현 검증** — 계산한 CK/IK 가 PyHSS 로그값과 바이트 단위 일치
  (`tools/milenage.py`, `tools/ims_full_reg.py`)
- **n78 TDD 30 kHz 종단간 검증** (OAI gNB + OAI nr-UE, rfsim)
  동기 → SIB1 → 4-Step RA → NAS 등록 → PDU 세션 → 데이터(8.8.8.8 37 ms)
- 작업물을 `private5g/` 한 곳으로 통합, 남의 클론과 분리

## 핵심 제약 — srsUE 는 n78 불가

`sdr-tools/5g-ran/srsRAN_4G/srsue/src/stack/rrc_nr/rrc_nr_procedures.cc:439` 에서
SCS 가 15 kHz 가 아니면 소스 레벨에서 거부한다. 차단문만 지워도 안 되는 이유는
슬롯 타이밍이 15 kHz 상수로 하드코딩돼 있기 때문:

```
srsue/src/phy/sync_sa.cc:279          SRSRAN_NSLOTS_PER_FRAME_NR(15kHz)
srsue/src/phy/nr/slot_sync.cc:133,151 동일
srsue/src/phy/nr/worker_pool.cc:122   scs = 15kHz 고정
```

15 kHz 는 프레임당 10슬롯, 30 kHz 는 20슬롯이라 UE 가 슬롯 번호를 2배 틀리게 계산한다.
메인테이너도 30 kHz 지원 계획 없음을 명시. **n78 이 필요하면 OAI nr-UE 를 쓴다.**

단, 이건 **srsRAN_4G 의 UE 컴포넌트 하나만의 문제**다. srsRAN gNB 는 정상이며 계속 주력이다.
실제 안드로이드 폰이 UE 자리에 들어오면 이 제약 자체가 사라진다.

## OAI 설정에서 걸렸던 것 (전부 해결)

| 증상 | 원인 |
|---|---|
| `expected a string input for do_SRS` | 정수 → 문자열(`"periodic"`) 로 스펙 변경 |
| `k2 >= GET_DURATION_RX_TO_TX` assert | `min_rxtxtime` 기본 2, UE 는 3 이상 요구 → **6 으로** |
| `cannot open include file` | `@include "neighbour-config-rfsim.conf"` (2셀 핸드오버용, 불필요) |
| `no active gNB found/mismatch` | `gNB_name` 만 바꾸고 `Active_gNBs` 를 안 바꿈 |

리포의 OAI 설정이 v2.3.0 시절 것이라 2026.w38 이미지와 안 맞았다.
정본은 로컬 클론 `sdr-tools/5g-ran/openairinterface5g` (tag 2026.w37) 의 레퍼런스를 기준으로 재작성.

## 2026-10-05 추가 완료분

- **B210 실제 RF 송신 성공** — 3350.01 MHz n78, LibreSDR FPGA 이미지, USB3
- **RF 경로 종단간 검증** — 모뎀이 `AT+COPS=?` 로 우리 셀 `00101` 탐지 (AcT 12 = NR SA)
  → 동축·감쇠기 40dB·MHF4 피그테일·ANT1 포트·주파수 계획 전부 정상 확인
- **모뎀 RM520N-GL 확보 및 동작 확인** — n78 지원, SIM 슬롯 정상(`CPIN: READY`)
- **SIM 리더(Identiv SCR35xx) + pySim 환경 구축**
- **알리 공백카드 판정** — 2G GSM 전용으로 확정. 4G/5G 불가 (`docs/sim-cards.md`)

## 중단 지점 — 해소됨

**~~유효한 USIM 이 없어 상용 단말 접속(RACH→인증→PDU)을 못 했다.~~**
sysmoISIM-SJA5 를 발급해 모뎀(2026-10-13)과 차폐함 안 실물 폰(2026-10-15)으로 전부 통했다.
**이 문서는 거기까지의 기록이고, 현재 지점은 `NEXT.md` 가 가진다.**

## 남은 일

1. **`SMF_DNS1=8.8.8.8`** — 통신 두절 대비 망인데 외부 DNS 를 본다. `dns` 컨테이너로 변경 필요.
2. **대시보드** — Grafana :3000, Open5GS WebUI :9999, Prometheus :9090 이미 기동됨. 구성 미착수.
3. ~~**실장비 RF** — 차폐함/감쇠기 입고 대기~~ → 입고·사용 중(TOJOIN MS3020-A). 남은 세 줄은 아래 그대로 유효하다.
   - B210 은 USB3 에서 40 MHz(106 PRB) 가 한계선. 실제 RF 는 srsRAN 20 MHz/51 PRB 구성 권장.
   - `~/.uhd/uhd.conf` 시리얼별 FPGA 매핑 미검증 (물리적 재삽입 필요)
   - B210 커넥터가 SMA 인지 RP-SMA 인지 육안 미확인
4. **4G LTE** — 5G 검증 후 실제 배치 목표
