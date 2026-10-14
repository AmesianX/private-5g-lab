# 영상통화와 멀티미디어(MMS) — 실물 단말로 확인

2026-10-15. 차폐함 안 갤럭시 S22+ 기준. 음성·문자가 된 다음 단계다.

## 영상통화 (5QI 2)

`tools/ims_call.py` 를 `VIDEO=1` 로 돌리면 SDP 에 `m=video`(H264)가 붙는다.
음성 통화와 같은 절차를 타고, 추가로 필요한 것은 **가입자 프로파일의 5QI 2 PCC 규칙**뿐이다
(`configs/db/subscriber.template.json` 에 들어 있다).

```bash
PID=$(docker inspect -f '{{.State.Pid}}' oainrue)
sudo nsenter -t $PID -n env VIDEO=1 ~/.venv/bin/python3 tools/ims_call.py \
  172.22.0.21 <UE IP> caller 20 sip:821099994533@ims.mnc001.mcc001.3gppnetwork.org
```

실측: `audio 송신 996 / 수신 129`, **`video 송신 332 / 수신 2697`**. 20초 동안 단말이
초당 약 135 패킷을 올려보냈다 — 실제 카메라 스트림이다.

화면에 "상대방 영상 준비 중"이 남는 것은 **우리 쪽이 진짜 H264 를 안 보내기 때문**이다.
스크립트는 RTP 헤더만 맞춘 더미를 보낸다. 단말→망 방향은 정상이고, 망→단말 방향에
실제 영상을 넣으려면 인코더를 붙여야 한다.

## MMS — 문자와 전혀 다른 경로다

MMS 는 SMS 로 본문을 나르지 않는다. 두 단계로 움직인다.

1. 망이 **WAP 푸시 SMS**(목적지 포트 2948, 8비트 데이터)로 `M-Notification.ind` 를 보낸다.
   그 안에는 본문이 아니라 **가져갈 URL**(`X-Mms-Content-Location`)과 크기만 들어 있다.
2. 단말이 그 URL 을 **데이터망으로 HTTP GET** 해서 `M-Retrieve.conf` 를 받고,
   multipart 안에서 이미지를 꺼낸다.

우리 코어에는 MMSC 가 없어서 `tools/mmsc.py` 로 만들었다. 알림 PDU 생성(WSP Push +
MMS 인캡슐레이션)과 본문 HTTP 서버를 한 도구가 같이 한다. 전송은
`tools/ims_sms_mt.py` 의 WAP 푸시 모드(`hex:` 접두사)가 맡는다.

```bash
# 본문 서버
MMS_TID=T1 python3 tools/mmsc.py serve 0.0.0.0 8099 image.jpg 821099994531 821099994533 "제목"
# 알림 전송 (URL 은 매번 다르게)
PUSH=$(MMS_TID=T1 python3 tools/mmsc.py notify "http://<호스트>:8099/m/$(date +%s)" <본문크기> 821099994531)
python3 tools/ims_sms_mt.py 172.22.0.20 821099994533 821099994531 "hex:$PUSH"
```

### 막혔던 곳 네 군데

**`ApnException: Can not find valid APN`.** 데이터망은 `MMS` 능력까지 붙어서 올라와 있는데도
MmsService 가 APN 을 못 찾는다. AOSP `ApnSettings.load()` 는 **`mmsc` 칸이 비어 있으면 그 행을
건너뛴다.** APN 에 `type=...,mms` 만 넣어서는 안 되고 MMSC URL 이 있어야 한다.

**`content insert` 로는 MMSC URL 을 넣을 수 없다.** 이 빌드의 바인딩 파서가 값의 콜론에서
쪼개진다(`--bind mmsc:s:http://...` → `Binding not well formed`). `cmd phone cc` 로 캐리어
설정을 덮어쓰는 길은 루트로도 `Permission denied`. 결국 **APN 편집 화면을 adb 로 조작**해서
넣었다. `am start -a android.intent.action.EDIT -d content://telephony/carriers/<id>` 로 열고,
`uiautomator dump` 로 좌표를 얻어 `input text` 로 URL 을 치고, 메뉴에서 **저장**을 눌러야
DB 에 반영된다. 대화상자에서 확인만 누르면 화면에만 보이고 DB 는 그대로다.

**같은 Transaction-Id 는 버려진다.** 두 번째 푸시가 아무 반응도 못 얻었다. 알림과 본문이
같은 TID 를 써야 하고, 재시험할 때는 TID 를 바꿔야 한다.

**같은 Content-Location URL 도 버려진다.** TID 를 바꿔도 URL 이 같으면 단말이 중복으로 본다.
보낼 때마다 URL 경로를 다르게 해야 한다. 서버는 어떤 경로로 와도 같은 본문을 주면 된다.

### 실측

| 방향 | 결과 |
|---|---|
| 망 → 단말 (MT) | 알림 88~93B 한 통 → 단말이 `GET /m/<n>` 으로 10,442B 수신, 이미지 표시 |
| 단말 → 망 (MO) | 단말이 `POST /mms` 로 10,802B 전송. SMIL + JPEG |

MO 로 받은 JPEG 은 **원본과 SHA256 이 같다**(10,342B, 480×320). 왕복 무손실이다.
MT GET 의 출발지는 `172.22.0.8`(UPF)로 찍힌다 — 단말이 우리 5G 데이터망으로 가져갔다는 증거다.

관련: [[shieldbox-phone.md]], [[sim-vs-real.md]]
