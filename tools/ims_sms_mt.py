#!/usr/bin/env python3
"""미니 SMSC — MT 문자를 SMS-DELIVER 로 직접 만들어 S-CSCF 에 넣는다.

우리 kamailio SMSC 의 `SMS_TO_3GPP` 는 MO TPDU 에서 본문 텍스트만 뽑아
`$tpdu(payload) = $avp(text)` 로 DELIVER 를 새로 만든다. smsops 의 `$tpdu()` 에는
UDH 필드가 없어서, 연결 문자(분할) 정보가 그 자리에서 통째로 사라진다.
그래서 단말은 쪼개진 조각을 서로 무관한 문자로 보고, 워커가 비동기라 순서까지 섞인다.

이 도구는 SMSC 가 해야 할 일을 그대로 한다 — UDH 를 붙인 SMS-DELIVER 를 만들어
RP-DATA(Network→MS)로 감싸고, SMSC 신원으로 S-CSCF 에 MESSAGE 를 보낸다.

사용: ims_sms_mt.py <S-CSCF IP> <수신 MSISDN> <발신 번호> "<본문>"
"""
import random, re, socket, string, sys, time

REALM = "ims.mnc001.mcc001.3gppnetwork.org"
SCSCF_PORT = 6060
SMSC_URI = f"sip:smsc.{REALM}"
UD_OCTET_MAX = 140                      # TS 23.040 상한. UCS2 70자.
CONCAT_CHARS = (UD_OCTET_MAX - 6) // 2  # UDH 6옥텟 제외 → 67자/통

rnd = lambda n: ''.join(random.choices(string.ascii_lowercase + string.digits, k=n))


def bcd_number(digits):
    d = digits + ('F' if len(digits) % 2 else '')
    return bytes.fromhex(''.join(d[i + 1] + d[i] for i in range(0, len(d), 2)))


def scts(ts=None):
    """TP-SCTS 7옥텟. 반옥텟 스왑, 마지막은 타임존(15분 단위)."""
    t = time.localtime(ts or time.time())
    tz = -time.altzone // 60 if t.tm_isdst else -time.timezone // 60
    q = abs(tz) // 15
    f = [t.tm_year % 100, t.tm_mon, t.tm_mday, t.tm_hour, t.tm_min, t.tm_sec]
    out = bytes(((v % 10) << 4) | (v // 10) for v in f)
    b = ((q % 10) << 4) | (q // 10)
    if tz < 0:
        b |= 0x08                        # 음수 타임존 표시
    return out + bytes([b])


def deliver_tpdu(originator, text, udh=None):
    """TS 23.040 SMS-DELIVER. DCS 0x08(UCS2)."""
    oa = bytes([len(originator), 0x91]) + bcd_number(originator)
    ud = (udh or b'') + text.encode('utf-16-be')
    first = 0x00 | (0x40 if udh else 0x00)          # TP-MTI=00(DELIVER) + UDHI
    return bytes([first]) + oa + bytes([0x00, 0x08]) + scts() + bytes([len(ud)]) + ud


def rp_data_mt(tpdu, mr, smsc="821099990000"):
    """TS 24.011 RP-DATA (Network→MS). RP-DA 는 길이 0."""
    oa = bytes([len(smsc) // 2 + 1, 0x91]) + bcd_number(smsc)
    return bytes([0x01, mr & 0xFF]) + bytes([len(oa)]) + oa + bytes([0x00, len(tpdu)]) + tpdu


def deliver_tpdu_8bit(originator, payload, udh):
    """8비트 데이터 SMS-DELIVER. WAP 푸시는 본문이 바이너리라 DCS 0x04 를 쓴다.
       UDH 의 포트 주소지정(IEI 0x05)으로 목적지 포트 2948(MMS UA)을 지정한다."""
    oa = bytes([len(originator), 0x91]) + bcd_number(originator)
    ud = udh + payload
    if len(ud) > 140:
        raise SystemExit(f"WAP 푸시가 한 통(140옥텟)을 넘는다: {len(ud)}옥텟. URL 을 줄일 것.")
    return bytes([0x40]) + oa + bytes([0x00, 0x04]) + scts() + bytes([len(ud)]) + ud


WAP_UDH = bytes([0x06, 0x05, 0x04, 0x0B, 0x84, 0x23, 0xF0])   # dst 2948, src 9200


def parts_for(text):
    if len(text.encode('utf-16-be')) <= UD_OCTET_MAX:
        return [(None, text)]
    chunks = [text[i:i + CONCAT_CHARS] for i in range(0, len(text), CONCAT_CHARS)]
    ref = random.randint(1, 255)
    return [(bytes([0x05, 0x00, 0x03, ref, len(chunks), i]), c)
            for i, c in enumerate(chunks, 1)]


def send_wap(scscf, msisdn, sender, payload):
    """WAP 푸시 한 통. MMS 알림(M-Notification.ind)을 실어 나른다."""
    target = f"sip:{msisdn}@{REALM}"
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("", 0)); sock.settimeout(10)
    src = socket.gethostbyname(socket.gethostname()); port = sock.getsockname()[1]
    body = rp_data_mt(deliver_tpdu_8bit(sender, payload, WAP_UDH), 1)
    head = "\r\n".join([
        f"MESSAGE {target} SIP/2.0",
        f"Via: SIP/2.0/UDP {src}:{port};rport;branch=z9hG4bK{rnd(12)}",
        "Max-Forwards: 70",
        f"From: <{SMSC_URI}>;tag={rnd(10)}", f"To: <{target}>",
        f"Call-ID: {rnd(16)}@smsc", "CSeq: 1 MESSAGE",
        f"Contact: <{SMSC_URI}>",
        "Content-Type: application/vnd.3gpp.sms",
        "Request-Disposition: no-fork",
        "Accept-Contact: *;+g.3gpp.smsip",
        f"Content-Length: {len(body)}", "", ""])
    sock.sendto(head.encode() + body, (scscf, SCSCF_PORT))
    print(f"  WAP 푸시 {len(payload)}B (TPDU 포함 {len(body)}B) → {scscf}:{SCSCF_PORT}")
    for _ in range(6):
        try:
            d, _ = sock.recvfrom(65535)
        except socket.timeout:
            break
        line = d.decode(errors='replace').split("\r\n")[0]
        print(f"      ← {line}")
        if re.match(r'SIP/2\.0 [2-6]', line):
            return bool(re.match(r'SIP/2\.0 2', line))
    return False


def send(scscf, msisdn, sender, text):
    target = f"sip:{msisdn}@{REALM}"
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("", 0)); sock.settimeout(10)
    src = socket.gethostbyname(socket.gethostname())
    port = sock.getsockname()[1]
    ok = True
    pieces = parts_for(text)
    print(f"본문 {len(text)}자 → {len(pieces)}통 (통당 최대 {CONCAT_CHARS}자, UDH 연결)")
    for n, (udh, chunk) in enumerate(pieces, 1):
        body = rp_data_mt(deliver_tpdu(sender, chunk, udh), n)
        head = "\r\n".join([
            f"MESSAGE {target} SIP/2.0",
            f"Via: SIP/2.0/UDP {src}:{port};rport;branch=z9hG4bK{rnd(12)}",
            "Max-Forwards: 70",
            f"From: <{SMSC_URI}>;tag={rnd(10)}", f"To: <{target}>",
            f"Call-ID: {rnd(16)}@smsc", "CSeq: 1 MESSAGE",
            f"Contact: <{SMSC_URI}>",
            "Content-Type: application/vnd.3gpp.sms",
            "Request-Disposition: no-fork",
            "Accept-Contact: *;+g.3gpp.smsip",
            f"Content-Length: {len(body)}", "", ""])
        sock.sendto(head.encode() + body, (scscf, SCSCF_PORT))
        print(f"  {n}/{len(pieces)}  TPDU {len(body)}B  → {scscf}:{SCSCF_PORT}")
        final = None
        for _ in range(6):
            try:
                d, _ = sock.recvfrom(65535)
            except socket.timeout:
                break
            line = d.decode(errors='replace').split("\r\n")[0]
            print(f"      ← {line}")
            if re.match(r'SIP/2\.0 [2-6]', line):
                final = line; break
        if not (final and re.match(r'SIP/2\.0 2', final)):
            ok = False
        time.sleep(0.4)          # 순서 보장: 단말이 받은 순서대로 합치게 한다
    return ok


if __name__ == "__main__":
    if len(sys.argv) < 5:
        sys.exit(__doc__)
    # 본문이 "hex:..." 이면 WAP 푸시(바이너리)로 보낸다. MMS 알림용.
    if sys.argv[4].startswith("hex:"):
        sys.exit(0 if send_wap(sys.argv[1], sys.argv[2], sys.argv[3],
                               bytes.fromhex(sys.argv[4][4:])) else 1)
    sys.exit(0 if send(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]) else 1)
