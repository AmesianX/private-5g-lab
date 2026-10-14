# 주파수 계획

## 채택값 (n78, rfsim 및 실장비 공통 기준)

| 항목 | 값 |
|---|---|
| pointA | ARFCN **622056** = 3330.84 MHz |
| SSB | ARFCN **623328** = 3349.92 MHz (GSCN 7742) |
| 캐리어 | 3330.84 ~ 3369.00 MHz (106 PRB @ 30 kHz) |
| SCS | 30 kHz (μ=1, 프레임당 20슬롯) |
| TDD | DDDDDDFFFFUUUU, 주기 5 ms |
| PLMN | 001/01 (시험용) |

## 한국 상용 n78 할당과 이격

| 사업자 | 대역 | 우리 상단(3369.00)과의 이격 |
|---|---|---|
| LG U+ | 3400-3500 MHz | **31.00 MHz** |
| KT | 3500-3600 MHz | 131.00 MHz |
| SKT | 3600-3700 MHz | 231.00 MHz |

## 계산식

```
NR-ARFCN (3000~24250 MHz):  F = 3000 + 0.015 x (N - 600000)  MHz
n78 채널 래스터:            N 은 3의 배수
SSB 동기 래스터(GSCN):      SS_ref = 3000 + N_gscn x 1.44 MHz
```

## 주파수를 옮기는 올바른 방법

**GSCN 래스터 정수배(1.44 MHz 배수)로 pointA 와 SSB 를 통째로 시프트한다.**
그러면 offsetToPointA 와 kSSB 가 불변이라 다른 필드를 건드릴 필요가 없다.

이번에 적용한 값: **269.28 MHz 하향 = 187 x 1.44 MHz**

```
SSB    641280 -> 623328   (3619.20 -> 3349.92 MHz)
pointA 640008 -> 622056   (3600.12 -> 3330.84 MHz)
offsetToPointA 86 RB, kSSB 0  — 불변
```

검증: 시프트 후 gNB 가 출력한 UE 권장 커맨드라인이 `--ssb 516` 으로, OAI 기본값과 일치했다.

## 업스트림 설정의 위험

OAI/srsRAN 예제 설정은 대부분 **SSB ARFCN 641280 = 3619.2 MHz** 를 기본으로 쓴다.
이는 **SKT 할당(3600-3700) 한복판**이다. 실장비(B210)에 그대로 물리면 상용망을 때린다.

교정한 파일:
- `configs/oai/gnb.sa.band78.fr1.106PRB.usrpb210.conf` — 실장비용. 원본은 `configs/_backup/*.skt.bak`
- `configs/oai/gnb.n78.rfsim.conf` — rfsim 용. 2셀 핸드오버 include 도 제거 (그 안에 641280 이 또 있었다)

srsRAN 실장비 설정 `configs/srsran/gnb.yml` 은 별도로 `dl_arfcn 623334` (3350.01 MHz, 20 MHz BW) 사용.
