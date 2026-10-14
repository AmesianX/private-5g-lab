#!/usr/bin/env python3
"""미니 MMSC — 이미지 한 장을 실물 단말에 MMS 로 밀어 넣는다.

우리 코어에는 MMSC 가 없다. MMS 는 문자와 전혀 다른 경로로 움직인다.

  1) 망이 **WAP 푸시 SMS**(목적지 포트 2948)로 `M-Notification.ind` 를 보낸다.
     거기에는 본문이 아니라 **가져갈 URL**(X-Mms-Content-Location)만 들어 있다.
  2) 단말이 그 URL 을 **데이터망(mms/internet APN)으로 HTTP GET** 해서
     `M-Retrieve.conf` 를 받고, 그 안의 multipart 에서 이미지를 꺼낸다.

그래서 이 도구는 둘 다 한다 — 알림 PDU 를 만들어 주고(tools/ims_sms_mt.py 가 실어 나른다),
본문을 내려 줄 HTTP 서버를 띄운다.

인코딩은 WSP(OMA WAP-230) + MMS 인캡슐레이션(OMA MMS-ENC) 이다.

사용:
  serve  : mmsc.py serve <바인드IP> <포트> <이미지> <발신번호> <수신번호> [제목]
  notify : mmsc.py notify <URL> <본문크기> → WAP 푸시 PDU 를 hex 로 출력
"""
import os, sys, time, pathlib

# 같은 Transaction-Id 로 두 번 보내면 단말이 중복으로 보고 버린다.
# 알림과 본문이 같은 값을 써야 하므로 환경변수로 맞춘다.
MY_TID = os.environ.get("MMS_TID", "T1").encode()
from http.server import BaseHTTPRequestHandler, HTTPServer

# ── WSP 기본 인코딩 ─────────────────────────────────────────────
def uintvar(n):
    """7비트씩 쪼개고 마지막 바이트만 최상위 비트를 0 으로 둔다."""
    if n == 0:
        return b"\x00"
    out = []
    while n:
        out.insert(0, n & 0x7F); n >>= 7
    return bytes(b | 0x80 for b in out[:-1]) + bytes([out[-1]])


def text(s):
    return s.encode() + b"\x00"


def long_int(n):
    b = n.to_bytes(max(1, (n.bit_length() + 7) // 8), 'big')
    return bytes([len(b)]) + b


# ── MMS 헤더 코드 (OMA MMS-ENC) ─────────────────────────────────
MSG_TYPE, TID, VERSION, FROM, TO, SUBJECT = 0x8C, 0x98, 0x8D, 0x89, 0x97, 0x96
MSG_CLASS, MSG_SIZE, EXPIRY, CONTENT_LOC, DATE, CONTENT_TYPE = 0x8A, 0x8E, 0x88, 0x83, 0x85, 0x84
M_NOTIFICATION_IND, M_RETRIEVE_CONF = 0x82, 0x84
MMS_1_2 = 0x92


def addr(number):
    """주소는 '+<번호>/TYPE=PLMN' 형식. 길이+부호화형식(0x80)+문자열."""
    s = text(f"+{number}/TYPE=PLMN")
    return bytes([len(s) + 1, 0x80]) + s


def notification_ind(url, size, tid=MY_TID, frm=None):
    b = bytes([MSG_TYPE, M_NOTIFICATION_IND])
    b += bytes([TID]) + tid + b"\x00"
    b += bytes([VERSION, MMS_1_2])
    if frm:
        b += bytes([FROM]) + addr(frm)
    b += bytes([MSG_CLASS, 0x80])                       # personal
    b += bytes([MSG_SIZE]) + long_int(size)
    b += bytes([EXPIRY, 0x04, 0x81]) + long_int(86400)  # relative 24h
    b += bytes([CONTENT_LOC]) + text(url)
    return b


def wap_push(payload):
    """WSP Push PDU. TID | 0x06 | 헤더길이 | Content-Type + X-Wap-Application-Id | 본문
       Content-Type 0x3E = application/vnd.wap.mms-message → 단문정수 0xBE.
       0xAF = X-Wap-Application-Id, 0x8A = x-wap-application:mms.ua"""
    headers = bytes([0xBE, 0xAF, 0x8A])
    return bytes([0x01, 0x06]) + uintvar(len(headers)) + headers + payload


def retrieve_conf(image: bytes, ctype: str, frm: str, to: str, subject: str, tid=MY_TID):
    h = bytes([MSG_TYPE, M_RETRIEVE_CONF])
    h += bytes([TID]) + tid + b"\x00"
    h += bytes([VERSION, MMS_1_2])
    h += bytes([DATE]) + long_int(int(time.time()))
    h += bytes([FROM]) + addr(frm)
    h += bytes([TO]) + text(f"+{to}/TYPE=PLMN")
    h += bytes([SUBJECT]) + text(subject)
    h += bytes([CONTENT_TYPE, 0xA3])                    # 0x23 multipart.mixed
    # multipart: 항목수(uintvar) + [헤더길이, 데이터길이, 헤더, 데이터]
    part_hdr = bytes([0x80 | 0x1E if False else 0x9E])  # 0x1E = image/jpeg → 0x9E
    if ctype == 'image/png':
        part_hdr = bytes([0x80 | 0x1C])                 # 0x1C = image/png → 0x9C
    part_hdr += b"\x8E" + text("mms.jpg")               # Content-Location
    body = uintvar(1) + uintvar(len(part_hdr)) + uintvar(len(image)) + part_hdr + image
    return h + body


class Handler(BaseHTTPRequestHandler):
    PAYLOAD = b""

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/vnd.wap.mms-message")
        self.send_header("Content-Length", str(len(self.PAYLOAD)))
        self.end_headers()
        self.wfile.write(self.PAYLOAD)
        print(f"  ← GET {self.path} from {self.client_address[0]}  ({len(self.PAYLOAD)}B 전송)")

    def do_POST(self):                                   # 단말이 보내는 MMS(MO) 수신
        n = int(self.headers.get("Content-Length", 0))
        d = self.rfile.read(n)
        pathlib.Path("/tmp/mms_mo.bin").write_bytes(d)
        print(f"  ← POST {self.path}  {n}B → /tmp/mms_mo.bin")
        self.send_response(200)
        self.send_header("Content-Type", "application/vnd.wap.mms-message")
        self.send_header("Content-Length", "0"); self.end_headers()

    def log_message(self, *a):
        pass


def main():
    mode = sys.argv[1]
    if mode == "notify":
        url, size = sys.argv[2], int(sys.argv[3])
        frm = sys.argv[4] if len(sys.argv) > 4 else None
        print(wap_push(notification_ind(url, size, frm=frm)).hex())
        return 0
    if mode == "serve":
        ip, port, img, frm, to = sys.argv[2], int(sys.argv[3]), sys.argv[4], sys.argv[5], sys.argv[6]
        subject = sys.argv[7] if len(sys.argv) > 7 else "사설 5G MMS"
        data = pathlib.Path(img).read_bytes()
        ct = 'image/png' if img.lower().endswith('.png') else 'image/jpeg'
        Handler.PAYLOAD = retrieve_conf(data, ct, frm, to, subject)
        print(f"  MMSC http://{ip}:{port}/mms  이미지 {len(data)}B  본문 {len(Handler.PAYLOAD)}B")
        print(f"  알림용 크기 인자: {len(Handler.PAYLOAD)}")
        HTTPServer((ip, port), Handler).serve_forever()
    return 2


if __name__ == "__main__":
    sys.exit(main())
