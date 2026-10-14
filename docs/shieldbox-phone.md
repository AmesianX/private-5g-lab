# 차폐함 안 실물 단말 — 유심 발급부터 통화까지

2026-10-15. 장비: TOJOIN MS3020-A 차폐함, 갤럭시 S22+(SM-S9060, Android 14, Magisk),
sysmoISIM-SJA5, B210(`serial=<B210 시리얼>`), srsRAN gNB + Open5GS + Kamailio IMS.

차폐함은 닫으면 안을 볼 수 없다. 그래서 **단말 제어와 증거 수집을 전부 adb 로** 한다.
화면 증거는 `docs/screenshots/` 에 있다.

## 1. 유심은 클론하지 않는다

모뎀 카드를 복제해 폰에 꽂으면 **코어가 한 가입자로 보기 때문에** 나중에 붙은 쪽이
앞선 쪽을 밀어낸다. 단말이 둘이면 가입자도 둘이어야 한다. 발급 절차는 [[sim-cards.md]].

## 2. 유선 adb — 랜 관통으로

차폐함 필터 패널의 USB 관통은 LC 저역통과라 USB 2.0 하이스피드 열거가 실패한다(충전만 된다).
그래서 **USB-C→이더넷 어댑터 + RJ45 관통**으로 간다. 자세한 것은 메모리
`project_shieldbox_phone_adb` 에 있고, 요점은 셋이다.

- 안드로이드 **무선 디버깅은 와이파이 연결을 전제**로 한다. 이더넷만 있으면 토글은 켜지지만
  IP·포트가 안 뜨고 서버도 안 올라온다. 첫 페어링만 와이파이로 하고, 그 뒤
  `service.adb.tcp.port 5555` 로 바꿔 두면 와이파이를 떼도 유선으로 계속 붙는다.
- 페어링 포트는 팝업이 떠 있는 동안만 열린다. **포트는 `nmap -Pn -p30000-49999 --open` 으로
  찾으면 되므로 사용자에게는 6자리 코드만 물으면 된다.**
- 재부팅 복구는 `/data/adb/service.d/99-ethadb.sh`(고정 IP·경로·포트·adbd 재기동).

### "인터넷을 사용할 수 없음" 없애기

우리 망은 외부로 안 나가니 캡티브 포털 검증이 항상 실패한다. 검증 자체를 끈다.

```bash
adb shell settings put global captive_portal_mode 0
adb shell settings put global captive_portal_detection_enabled 0
adb shell settings put global captive_portal_use_https 0
adb shell settings put global captive_portal_http_url ""
adb shell settings put global captive_portal_https_url ""
```

## 3. 단말이 셀에 붙지 않을 때 본 것들

순서대로 걸렸던 세 가지다.

**기지국 로그 레벨이 `warning` 이면 RACH 가 안 보인다.** 붙는지 안 붙는지 판단조차 못 한다.
`configs/srsran/gnb.yml` 의 `all_level` 을 `info` 로 올려야 `rach`·`RRC Setup`·`c-rnti` 가 찍힌다.

**단말은 묵은 셀 정보를 들고 있다.** 뚜껑을 열어 둔 동안 잡은 상용 셀 정보가 남아 OUT_OF_SERVICE
로 떠 있다. `cmd connectivity airplane-mode enable/disable` 로 라디오를 한 번 리셋하면
몇 초 만에 우리 셀을 찾는다.

**srsRAN gNB 는 IPv4v6 PDU 세션을 지원하지 않는다.**

```
[NGAP] [W] Unsupported PDU Session Type: ipv4v6
[NGAP] [I] Validation of PDUSessionResourceSetupRequest failed
[NGAP] [W] Some or all PDUSessionResourceSetupItems failed to setup
```

폰은 IPv4v6 로 요청하고, 우리 가입자 프로파일도 type 3(IPv4v6)이라 그대로 내려간다.
세션이 올라오자마자 `UE Context Release` 로 끊기고 100초마다 무한 재시도한다. **코어에서
그 가입자의 세션 타입을 1(IPv4)로** 바꾸면 끝난다.

```bash
docker exec mongo mongosh --quiet open5gs --eval \
 'db.subscribers.updateOne({imsi:"..."},{$set:{"slice.0.session.0.type":1,"slice.0.session.1.type":1}})'
```

APN 도 없으면 넣어야 한다(`content insert --uri content://telephony/carriers`, numeric=00101).

### 인터넷 APN 이 안 올라올 때 — APN 설정을 뒤지기 전에

APN 행, 선호 APN, 세션 타입을 한참 확인했지만 전부 헛다리였다. 라디오 로그의 이 한 줄이
답이었다.

```
DNC-0: Re-evaluating 0 unsatisfied network requests
```

미충족 네트워크 요청이 **0개**다. 우리가 adb 를 쓰려고 붙여 둔 **이더넷이 이미 기본
인터넷 요청을 만족시키고 있어서**, 안드로이드가 셀룰러 데이터 호를 요청조차 하지 않는다.
제어 경로를 만든 것이 측정 대상을 가린 셈이다.

```bash
adb shell settings put global mobile_data_always_on 1
adb shell su -c "svc data disable"; sleep 4; adb shell su -c "svc data enable"
```

그러면 `internet` DNN 세션이 따로 올라온다(`rmnet_data0`, 10.45 대역).
실측: UPF 게이트웨이까지 RTT 25~31 ms, 외부 8.8.8.8 까지 54~58 ms, 손실 0%.

## 4. 등록 확인

```
registrationState  HOME   (domain=PS, transportType=WWAN)
기술               NR                      ← 5G SA
NR-ARFCN           623040
PLMN               001/01, mAlphaLong "Open5GS"
```

단말이 밴드를 `77` 로 보고하는 것은 정상이다. 3350 MHz 는 n77·n78 범위가 겹친다.

IMS 등록은 P-CSCF 로그의 Contact 로 확인한다.

```
sip:821099994533@10.46.0.15:6200
  +g.3gpp.icsi-ref=...mmtel  audio  video  +g.3gpp.smsip
```

상태바에 **HD** 아이콘이 뜨면 단말 쪽에서도 IMS 가 올라온 것이다.

## 5. 전화와 문자

실물 단말은 스크립트끼리 통하던 설정을 전부 거절한다. 조건과 함정은
메모리 `project_private5g_ims_call_recipe` 에 정리했다. 요점만:

- **AMR-WB/AMR 만 받는다.** G.711 이면 `488 Not Acceptable Here`.
- **PRACK 필수.** 183 이 `Require: 100rel` 로 온다. 안 하면 183 재전송 끝에 `500`.
- **전제조건을 "이미 충족"으로 선언**하면 UPDATE 왕복 없이 `180 Ringing` 이 온다.
- **SDP 응답은 183 에 있다.** `200 OK` 에는 없다. 그리고 PRACK 의 200 OK 를 통화 응답으로
  착각하지 않도록 **CSeq 메서드를 확인**해야 한다.

문자 길이 상한은 스펙(140옥텟)이 아니라 **우리 SMSC 버그로 한글 35자**다. 넘기면
`Length of TP-User-Data payload exceeds maximum length!`. 쪼개 보내면 전부 도착하지만
SMSC 가 UDH 를 버리고 재인코딩하므로 **합쳐지지 않고 순서도 섞인다.**

## 6. adb 로 증거 남기기

```bash
adb shell input keyevent KEYCODE_WAKEUP
adb shell su -c "screencap -p /data/local/tmp/s.png"
adb pull /data/local/tmp/s.png docs/screenshots/NN-이름.png
adb shell input keyevent 79     # 수신 전화 받기
adb shell input keyevent 6      # 통화 종료(막힌 호 상태 정리)
```

`486 Busy Here` 가 나오면 앞선 호가 단말에 남아 있는 것이다. keyevent 6 으로 정리하고 다시 건다.

관련: [[sim-cards.md]], [[rf-cabling.md]], [[modem.md]]
