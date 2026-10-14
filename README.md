# private5g — 사설 로컬 5G SA 망

목적: 상용망 두절 시 가동할 자체 통신망. 5G SA 로 검증한 뒤 **4G LTE 가 실제 배치 목표**.

> ## 👉 이어서 작업하려면 **[NEXT.md](NEXT.md)** 를 먼저 읽을 것
>
> 마지막 작업 **2026-10-05** / 중단 사유: **유효한 USIM 없음** (sysmoISIM 주문 대기)
> 망은 완성됐고 **RF 경로까지 검증 완료**. 카드만 오면 바로 재개된다.

## 안전 원칙 (항상 유효)

- 상용망 교란 금지. **로컬망 구축이 목적**이다.
- PLMN 은 시험용 **001/01** 고정. 상용(450-05 SKT / 450-06 LGU+ / 450-08 KT) 절대 사용 금지.
- 주파수는 한국 상용 할당과 반드시 교차 확인. n78 상용: LG U+ 3400-3500 / KT 3500-3600 / SKT 3600-3700 MHz.
- TX 게인은 항상 최소에서 시작. RF 단계 전에 동축/차폐 먼저 확인.
- rfsim / ZMQ 경로는 **전파 방사 0** (TCP 로 IQ 교환). 실장비 단계에서만 실제 송신.
- **업스트림 예제 설정의 주파수는 믿지 말 것.** 대부분 상용 대역 한복판을 기본값으로 쓴다.

## 디렉토리

```
private5g/
├── bin/         제어 스크립트 (여기서만 실행)
├── compose/     우리 docker compose 파일
├── configs/     설정 정본 — 고칠 때는 반드시 여기를 고친다
│   └── _backup/ 변경 이력 백업
├── docs/        주파수 계획, 진행 상황
├── tools/       측정/검증 스크립트
└── upstream ->  ../sdr-tools/docker/docker_open5gs  (남의 클론, 심볼릭)
```

### 정본과 런타임의 관계

코어/IMS/srsRAN 컨테이너는 **upstream 클론의 compose 파일**로 뜨기 때문에 설정도 그 트리 안에 있어야 한다.
그래서 `configs/` 를 정본으로 두고 `bin/deploy-configs.sh` 가 클론으로 복사한다.
**클론 안에서 직접 고치면 다음 배포 때 덮어써진다.** 항상 `configs/` 를 고칠 것.

OAI n78 스택(`compose/oai_n78_rfsim.yaml`)만은 클론 의존이 없어 이 디렉토리에서 자립 동작한다.

## 사용법

```bash
bin/core-ctl.sh START          # 코어(5GC+IMS) 기동. 설정 자동 배포 후 기동
bin/ran-ctl.sh  START n78      # OAI gNB + nr-UE, n78 TDD 30kHz, rfsim
bin/ran-ctl.sh  START n3       # srsRAN gNB + srsUE, n3 FDD 15kHz, ZMQ
bin/ran-ctl.sh  STOP
bin/core-ctl.sh STOP
bin/deploy-configs.sh --check  # 정본과 런타임 차이 확인
```

n78 과 n3 프로파일은 **UE1 IMSI 를 공유하므로 동시 기동 금지.**

`core-ctl.sh START` 는 컨테이너 기동 후 **코어 SBI 메시가 수렴할 때까지 기다린다**(NF 5종 연결 확인, 보통 10초).
이 대기가 없으면 UE 등록이 AUSF HTTP 504 로 거부된다(`Registration reject [90]`). 실측으로 확인한 레이스다.

## 이식성

디렉토리명이나 위치에 의존하지 않는다. 설정은 `bin/_common.sh` 한 곳뿐이며 환경변수로 덮을 수 있다.

```bash
CORE_PROJECT=myran   bin/core-ctl.sh START    # compose 프로젝트명(=네트워크 접두사) 변경
UPSTREAM_DIR=/path/to/docker_open5gs bin/ran-ctl.sh STATUS   # 클론 위치 변경
```

- compose 프로젝트명은 디렉토리명에서 유도하지 않고 `CORE_PROJECT` 로 고정한다.
- `upstream` 심볼릭은 편의용이며 정본은 `UPSTREAM_DIR` 값이다. 실행할 때마다 갱신된다.
- 클론을 못 찾으면 조용히 깨지지 않고 **경로를 찍으며 중단**한다.

## 현재 상태

- 5GC + IMS(VoNR) 25 컨테이너 동작. IMS 등록 200 OK 확인 (`tel:9076543210` 할당).
- **n78 TDD 30 kHz 종단간 검증 완료** — 동기 → SIB1 → RACH → NAS 등록 → PDU 세션 → 데이터.
- **B210 실제 RF 송신 완료** — 3350.01 MHz n78. 모뎀이 우리 셀을 탐지함(`00101`, NR SA)
- RF 경로(동축+감쇠기+MHF4+ANT1) 검증 완료
- **남은 것: 유효한 USIM 하나.** 상용 단말 접속만 미완

자세한 내용은 `docs/` 참조.

## 관련 디렉토리 (여기 밖)

- `../LibreSDR_B200/` — B210 클론 FPGA 비트스트림, `~/.uhd/uhd.conf` 시리얼별 매핑
- `../sdr-tools/` — SDR 리포 수집 (5g-core / 5g-ran / 5g-ue / osmocom / classic ...)
