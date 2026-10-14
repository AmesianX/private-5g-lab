#!/usr/bin/env python3
"""IMS VoNR 통화 테스트: UA-A, UA-B 를 IMS AKAv1-MD5 로 각각 등록한 뒤
   A → B 로 INVITE → 180 → 200 OK → ACK → RTP 양방향 → BYE 까지 수행한다.

   사용법:  ims_call.py <PCSCF_IP> <SRC_IP> [통화초]
   ims_full_reg.py 의 MILENAGE/SIP 구현을 그대로 쓰되 통화 단계를 덧붙였다.
"""
import socket, random, string, sys, base64, hashlib, subprocess, re, threading, time, struct, select, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import labsecrets

# 카드 키는 저장소에 두지 않는다. configs/secrets/lab.env 에서 읽는다.
_K1, _O1, _K2, _O2 = labsecrets.need('UE1_KI', 'UE1_OPC', 'UE2_KI', 'UE2_OPC')

PCSCF = sys.argv[1]
SRC   = sys.argv[2]
ROLE  = sys.argv[3] if len(sys.argv) > 3 else "both"   # reg-a|reg-b|caller|callee|both
TALK  = float(sys.argv[4]) if len(sys.argv) > 4 else 3.0
VIDEO = os.environ.get("VIDEO", "0") == "1"      # VIDEO=1 이면 SDP 에 m=video 추가
REALM = "ims.mnc001.mcc001.3gppnetwork.org"

# 가입자 두 명 (PyHSS ims_hss_db 와 일치해야 한다)
UA_A = dict(name="A", imsi="001011234567895", msisdn="821099994531",
            ki=_K1,
            opc=_O1, sip_port=5060, rtp_port=40000)
UA_B = dict(name="B", imsi="001011234567896", msisdn="821099994532",
            ki=_K2,
            opc=_O2, sip_port=5062, rtp_port=40002)

# ---------- MILENAGE (ims_full_reg.py 와 동일) ----------
def aes(k, d):
    return subprocess.run(["openssl", "enc", "-aes-128-ecb", "-K", k.hex(), "-nopad"],
                          input=d, capture_output=True).stdout[:16]
rot = lambda b, n: b[n // 8:] + b[:n // 8]
xor = lambda a, b: bytes(x ^ y for x, y in zip(a, b))
C = [bytes(16)] + [(v).to_bytes(16, 'big') for v in (1, 2, 4, 8)]
R = [64, 0, 32, 64, 96]

def f2345(ki, opc, rand):
    t = aes(ki, xor(rand, opc))
    o = [xor(aes(ki, xor(rot(xor(t, opc), R[i]), C[i])), opc) for i in range(1, 5)]
    return o[0][8:], o[1], o[2], o[0][:6]        # RES, CK, IK, AK

def f1(ki, opc, rand, sqn, amf):
    t = aes(ki, xor(rand, opc)); in1 = sqn + amf + sqn + amf
    o = xor(aes(ki, xor(xor(t, rot(xor(in1, opc), R[0])), C[0])), opc)
    return o[:8]

rnd = lambda n: ''.join(random.choices(string.ascii_lowercase + string.digits, k=n))
md5 = lambda b: hashlib.md5(b).hexdigest()


def sdp(src, rtp_port):
    lines = [
        "v=0", f"o=- {random.randint(1,2**31)} 1 IN IP4 {src}", "s=-",
        f"c=IN IP4 {src}", "t=0 0",
        f"m=audio {rtp_port} RTP/AVP 97 98 101",
        "a=rtpmap:97 AMR-WB/16000/1",
        "a=fmtp:97 mode-change-capability=2;max-red=0",
        "a=rtpmap:98 AMR/8000/1",
        "a=fmtp:98 mode-change-capability=2;max-red=0",
        "a=rtpmap:101 telephone-event/8000",
        "a=fmtp:101 0-15",
        "a=ptime:20", "a=maxptime:240", "a=sendrecv",
        # TS 24.229 전제조건. 우리는 전용 베어러를 따로 세우지 않으므로
        # "이미 충족(curr=sendrecv)"으로 선언해 단말이 UPDATE 를 기다리지 않게 한다.
        "a=curr:qos local sendrecv", "a=curr:qos remote sendrecv",
        "a=des:qos mandatory local sendrecv",
        "a=des:qos mandatory remote sendrecv"]
    if VIDEO:
        lines += [f"m=video {rtp_port + 4} RTP/AVP 96",
                  "a=rtpmap:96 H264/90000",
                  "a=fmtp:96 profile-level-id=42e01f;packetization-mode=1",
                  "a=sendrecv"]
    return "\r\n".join(lines + [""])


class UA:
    def __init__(self, cfg):
        self.__dict__.update(cfg)
        self.ki = bytes.fromhex(self.ki); self.opc = bytes.fromhex(self.opc)
        self.impi = f"{self.imsi}@{REALM}"
        # 실물 단말과 같은 신원 체계. IMPI 는 IMSI 기반이지만 **공개 신원(IMPU)은
        # 번호 기반**이다(TS 23.003). IMSI 형식 IMPU 로 걸면 I-CSCF 가
        # `500 Server error on LIR select next S-CSCF` 를 돌려준다 — 실측 확인.
        self.impu = f"sip:{self.msisdn}@{REALM}"
        self.uri  = f"sip:{REALM}"
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((SRC, self.sip_port)); self.sock.settimeout(8)
        # P-CSCF 는 요청이 UDP 한계(1300B)를 넘으면 RFC 3261 18.1.1 에 따라 TCP 로
        # 전환한다. terminating INVITE 가 그 크기를 넘으므로 TCP 도 받아야 한다.
        self.tcp_srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tcp_srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.tcp_srv.bind((SRC, self.sip_port)); self.tcp_srv.listen(4)
        self.tcp_conn = None
        self.rtp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.rtp.bind((SRC, self.rtp_port)); self.rtp.setblocking(False)
        self.vrtp = None
        if VIDEO:
            self.vrtp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.vrtp.bind((SRC, self.rtp_port + 4)); self.vrtp.setblocking(False)
        self.vrtp_rx = 0; self.vrtp_tx = 0
        self.callid = rnd(16); self.tag = rnd(10)
        self.rtp_rx = 0; self.rtp_tx = 0
        self.log = []

    def p(self, msg):
        line = f"  [{self.name}] {msg}"
        print(line, flush=True); self.log.append(line)

    def reply(self, msg):
        """TCP 로 들어온 요청이면 그 연결로, 아니면 UDP 로 내보낸다."""
        if self.tcp_conn:
            self.tcp_conn.sendall(msg.encode())
        else:
            self.sock.sendto(msg.encode(), (PCSCF, 5060))

    def recv_next(self, timeout):
        """현재 쓰고 있는 전송 경로에서 다음 메시지를 받는다."""
        if self.tcp_conn:
            self.tcp_conn.settimeout(timeout)
            return recv_sip_tcp(self.tcp_conn)
        self.sock.settimeout(timeout)
        d, _ = self.sock.recvfrom(65535)
        return d

    def send(self, msg, expect_final=True):
        self.sock.sendto(msg.encode(), (PCSCF, 5060))
        for _ in range(6):
            try:
                d, _a = self.sock.recvfrom(65535)
            except socket.timeout:
                return None
            t = d.decode(errors='replace'); st = t.split("\r\n")[0]
            self.p(f"← {st}")
            if st.startswith("SIP/2.0 1") and expect_final:
                continue
            return t
        return None

    # ---------- 등록 ----------
    def register_msg(self, cseq, auth):
        return "\r\n".join([
            f"REGISTER {self.uri} SIP/2.0",
            f"Via: SIP/2.0/UDP {SRC}:{self.sip_port};rport;branch=z9hG4bK{rnd(12)}",
            "Max-Forwards: 70",
            f"From: <{self.impu}>;tag={self.tag}", f"To: <{self.impu}>",
            f"Call-ID: {self.callid}", f"CSeq: {cseq} REGISTER",
            f"Contact: <sip:{self.msisdn}@{SRC}:{self.sip_port}>;expires=600000",
            auth, "Supported: path", "Expires: 600000", "Content-Length: 0", "", ""])

    def register(self):
        self.p(f"→ 1차 REGISTER ({self.msisdn})")
        r1 = self.send(self.register_msg(1,
             f'Authorization: Digest username="{self.impi}",realm="{REALM}",'
             f'nonce="",uri="{self.uri}",response="",algorithm=AKAv1-MD5'))
        if not r1 or "401" not in r1.split("\r\n")[0]:
            self.p("✗ 401 챌린지 실패"); return False

        wa = [l for l in r1.split("\r\n") if l.lower().startswith("www-authenticate")][0]
        nonce = re.search(r'nonce="([^"]+)"', wa).group(1)
        raw = base64.b64decode(nonce); RAND, AUTN = raw[:16], raw[16:32]
        RES, CK, IK, AK = f2345(self.ki, self.opc, RAND)
        sqn = xor(AUTN[:6], AK); amf = AUTN[6:8]
        mac = f1(self.ki, self.opc, RAND, sqn, amf)
        self.p(f"MAC-A {'✅ 망 인증 OK' if mac == AUTN[8:16] else '❌ 불일치'}  RES={RES.hex()}")
        if mac != AUTN[8:16]:
            return False

        ha1 = md5(self.impi.encode() + b":" + REALM.encode() + b":" + RES)
        ha2 = md5(f"REGISTER:{self.uri}".encode())
        nc, cnonce = "00000001", rnd(16)
        resp = md5(f"{ha1}:{nonce}:{nc}:{cnonce}:auth:{ha2}".encode())
        auth2 = (f'Authorization: Digest username="{self.impi}",realm="{REALM}",'
                 f'nonce="{nonce}",uri="{self.uri}",response="{resp}",'
                 f'algorithm=AKAv1-MD5,cnonce="{cnonce}",qop=auth,nc={nc}')
        self.p("→ 2차 REGISTER (RES)")
        r2 = self.send(self.register_msg(2, auth2))
        if not r2 or not r2.split("\r\n")[0].startswith("SIP/2.0 200"):
            self.p("✗ 등록 실패"); return False
        for l in r2.split("\r\n"):
            if l.startswith(("Service-Route", "P-Associated-URI")):
                self.p(f"  {l[:130]}")
        self.p("✅ 등록 완료")
        return True

    # ---------- RTP ----------
    def rtp_stream(self, peer_ip, peer_port, seconds, peer_vport=None):
        """오디오는 PCMU 무음(PT 0, 20ms), 비디오는 H.264 PT 96 더미를 흘린다.
           실제 코덱 인코딩이 아니라 미디어 경로가 양방향으로 열리는지 보는 용도다."""
        assrc = random.randint(0, 2**32 - 1); aseq = 0; ats = 0
        vssrc = random.randint(0, 2**32 - 1); vseq = 0; vts = 0
        apay = b'\xff' * 160                         # PCMU 무음
        vpay = bytes([0x21]) + b'\x00' * 199         # H.264 NAL 더미
        t_end = time.time() + seconds
        tick = 0
        while time.time() < t_end:
            h = struct.pack("!BBHII", 0x80, 0, aseq & 0xFFFF, ats & 0xFFFFFFFF, assrc)
            try:
                self.rtp.sendto(h + apay, (peer_ip, peer_port)); self.rtp_tx += 1
            except OSError:
                pass
            aseq += 1; ats += 160
            # 비디오는 매 3틱(약 60ms, 약 16fps)마다 한 프레임
            if self.vrtp and peer_vport and tick % 3 == 0:
                vh = struct.pack("!BBHII", 0x80, 96, vseq & 0xFFFF, vts & 0xFFFFFFFF, vssrc)
                try:
                    self.vrtp.sendto(vh + vpay, (peer_ip, peer_vport)); self.vrtp_tx += 1
                except OSError:
                    pass
                vseq += 1; vts += 5400
            for sk, isvid in ((self.rtp, False), (self.vrtp, True)):
                if sk is None:
                    continue
                try:
                    while True:
                        sk.recvfrom(4096)
                        if isvid: self.vrtp_rx += 1
                        else:     self.rtp_rx += 1
                except (BlockingIOError, socket.timeout, OSError):
                    pass
            tick += 1
            time.sleep(0.02)


def parse_sdp_media(body):
    ip = re.search(r'c=IN IP4 ([0-9.]+)', body)
    port = re.search(r'm=audio (\d+)', body)
    return (ip.group(1) if ip else None, int(port.group(1)) if port else None)


def parse_sdp_video(body):
    m = re.search(r'm=video (\d+)', body)
    return int(m.group(1)) if m else None


def bcd_number(digits):
    """TP-DA/TP-OA 용 반옥텟 스왑 BCD. 홀수 길이는 F 로 채운다."""
    d = digits + ('F' if len(digits) % 2 else '')
    return bytes.fromhex(''.join(d[i + 1] + d[i] for i in range(0, len(d), 2)))


# 우리 SMSC(kamailio smsops)는 UCS2 의 TP-UDL 을 옥텟이 아니라 문자수 한도(70)와
# 비교한다. 그래서 한 통에 들어가는 UD 는 70 옥텟 = 한글 35자가 상한이다.
# 넘치면 UDH 연결 문자로 쪼개 보내지만, SMSC 가 본문만 뽑아 TPDU 를 다시 만들기
# 때문에 **단말에서 합쳐지지 않는다**(실측 확인). 긴 문자를 한 통으로 보내려면
# 이 MO 경로가 아니라 tools/ims_sms_mt.py(미니 SMSC, MT 직접 주입)를 쓸 것.
UD_OCTET_MAX = 70
CONCAT_CHARS = (UD_OCTET_MAX - 6) // 2          # 32


def encode_sms_submit(dest_msisdn, text, mr=0):
    """TS 23.040 SMS-SUBMIT TPDU. 한글이 섞이므로 DCS 0x08(UCS2)로 보낸다."""
    da = bytes([len(dest_msisdn), 0x91]) + bcd_number(dest_msisdn)   # 0x91 = international/ISDN
    ud = text.encode('utf-16-be')
    if len(ud) > UD_OCTET_MAX:
        ud = ud[:UD_OCTET_MAX]
    # TP-MTI=01(SUBMIT), VPF=00(없음)  / TP-PID=00 / TP-DCS=08(UCS2)
    return bytes([0x01, mr]) + da + bytes([0x00, 0x08, len(ud)]) + ud


def encode_sms_submit_parts(dest_msisdn, text, mr=0):
    """길이에 관계없이 보낼 수 있도록 SMS-SUBMIT 을 UDH 연결 문자로 쪼갠다."""
    if len(text.encode('utf-16-be')) <= UD_OCTET_MAX:
        return [encode_sms_submit(dest_msisdn, text, mr)]
    chunks = [text[i:i + CONCAT_CHARS] for i in range(0, len(text), CONCAT_CHARS)]
    if len(chunks) > 255:
        chunks = chunks[:255]
    da = bytes([len(dest_msisdn), 0x91]) + bcd_number(dest_msisdn)
    ref = random.randint(1, 255)
    out = []
    for i, c in enumerate(chunks, 1):
        # UDH: 05 00 03 <ref> <전체> <순번>  (IEI 0x00 = 8비트 참조 연결 문자)
        udh = bytes([0x05, 0x00, 0x03, ref, len(chunks), i])
        ud = udh + c.encode('utf-16-be')
        # TP-MTI=01 + UDHI(0x40). UCS2 라 TP-UDL 은 UDH 포함 옥텟 수.
        out.append(bytes([0x41, (mr + i) & 0xFF]) + da
                   + bytes([0x00, 0x08, len(ud)]) + ud)
    return out


def encode_rp_data_mo(tpdu, mr=1):
    """TS 24.011 RP-DATA (MS→Network). RP-OA/RP-DA 는 길이 0(망이 SMSC 결정)."""
    return bytes([0x00, mr, 0x00, 0x00, len(tpdu)]) + tpdu


def decode_sms_deliver(blob):
    """수신한 RP-DATA(Network→MS) 안의 SMS-DELIVER 에서 발신번호와 본문을 뽑는다."""
    try:
        i = 0
        mti = blob[i] & 0x07; i += 1          # RP-MTI
        i += 1                                # RP-MR
        oa_len = blob[i]; i += 1 + oa_len     # RP-OA
        da_len = blob[i]; i += 1 + da_len     # RP-DA
        ud_len = blob[i]; i += 1              # RP-UD 길이
        t = blob[i:i + ud_len]
        j = 0
        first = t[j]; j += 1                  # TP-MTI 등
        oal = t[j]; j += 1                    # TP-OA 자릿수
        j += 1                                # TON/NPI
        nb = (oal + 1) // 2
        oa_bcd = t[j:j + nb]; j += nb
        sender = ''.join(f"{b & 0x0F}{b >> 4}" for b in oa_bcd)[:oal]
        j += 1                                # TP-PID
        dcs = t[j]; j += 1                    # TP-DCS
        j += 7                                # TP-SCTS (7바이트)
        udl = t[j]; j += 1
        ud = t[j:j + (udl if dcs & 0x0C else udl)]
        if dcs & 0x08:                        # UCS2
            body = ud.decode('utf-16-be', errors='replace')
        else:
            body = ud.decode('latin-1', errors='replace')
        return sender, body, dcs
    except Exception as e:
        return None, f"(디코드 실패: {e}) raw={blob.hex()}", None


def run_sms_send(ua, target, text, dest_msisdn=None):
    """IMS SMS. 실제 단말과 같은 application/vnd.3gpp.sms + RP-DATA/TPDU 로 보낸다.
       SMSC 의 OTT(text/plain) 경로는 dcs 를 채우지 않아 DB insert 가 깨진다."""
    dest = dest_msisdn or UA_B['msisdn']
    parts = encode_sms_submit_parts(dest, text)
    if len(parts) > 1:
        ua.p(f"본문 {len(text)}자 → 연결 문자 {len(parts)}통으로 분할")
        ok = True
        for n, tp in enumerate(parts, 1):
            ua.p(f"--- {n}/{len(parts)}통")
            if not _send_one_sms(ua, target, tp, dest, text):
                ok = False
        return ok
    return _send_one_sms(ua, target, parts[0], dest, text)


def _send_one_sms(ua, target, tpdu, dest, text):
    body = encode_rp_data_mo(tpdu)
    head = "\r\n".join([
        f"MESSAGE {target} SIP/2.0",
        f"Via: SIP/2.0/UDP {SRC}:{ua.sip_port};rport;branch=z9hG4bK{rnd(12)}",
        "Max-Forwards: 70",
        f"From: <{ua.impu}>;tag={rnd(10)}", f"To: <{target}>",
        f"Call-ID: {rnd(16)}", "CSeq: 1 MESSAGE",
        f"P-Preferred-Identity: <{ua.impu}>",
        "Content-Type: application/vnd.3gpp.sms",
        "Accept-Contact: *;+g.3gpp.smsip",
        f"Content-Length: {len(body)}", "", ""])
    msg = head.encode() + body
    ua.p(f"→ MESSAGE {target}  (3GPP SMS, TPDU {len(tpdu)}B, RP-DATA {len(body)}B)")
    ua.p(f"   수신번호 {dest} / UCS2 / 본문 {text!r}")
    ua.sock.settimeout(15)
    ua.sock.sendto(msg, (PCSCF, 5060))
    final = None
    for _ in range(8):
        try:
            d, _ = ua.sock.recvfrom(65535)
        except socket.timeout:
            break
        t = d.decode(errors='replace'); first = t.split("\r\n")[0]
        ua.p(f"← {first}")
        if first.startswith(("SIP/2.0 2", "SIP/2.0 4", "SIP/2.0 5", "SIP/2.0 6")):
            final = first; break
    ok = bool(final and final.startswith("SIP/2.0 2"))
    print(f"\n=== SMS 발신 결과 ===\n  {final or '응답 없음'}   {'✅' if ok else '❌'}")
    return ok


def recv_sip_tcp(conn):
    """TCP 는 스트림이라 한 번 읽어서는 본문이 덜 온다. Content-Length 만큼 채운다.
       덜 읽으면 SDP 가 통째로 비어 `발신측 미디어 None:None` 이 된다."""
    buf = b""
    while b"\r\n\r\n" not in buf:
        c = conn.recv(65535)
        if not c:
            return buf
        buf += c
    head, body = buf.split(b"\r\n\r\n", 1)
    need = 0
    for l in head.decode(errors='replace').split("\r\n"):
        if l.lower().startswith("content-length:"):
            need = int(l.split(":", 1)[1].strip() or 0)
    while len(body) < need:
        c = conn.recv(65535)
        if not c:
            break
        body += c
    return head + b"\r\n\r\n" + body


def run_sms_recv(ua, wait=40):
    """MESSAGE 를 기다려 200 OK 로 응답하고 본문을 출력한다 (UDP+TCP)."""
    ua.p(f"MESSAGE 대기 ({wait}s, UDP+TCP)…")
    r, _, _ = select.select([ua.sock, ua.tcp_srv], [], [], wait)
    if not r:
        ua.p("✗ MESSAGE 수신 타임아웃"); return False
    if ua.tcp_srv in r:
        conn, addr = ua.tcp_srv.accept(); conn.settimeout(8)
        d = recv_sip_tcp(conn); ua.tcp_conn = conn
        ua.p(f"TCP 연결 수신 {addr[0]}:{addr[1]}")
    else:
        d, _ = ua.sock.recvfrom(65535)
    t = d.decode(errors='replace'); first = t.split("\r\n")[0]
    ua.p(f"← {first}")
    if not first.startswith("MESSAGE"):
        ua.p("✗ MESSAGE 아님"); return False
    # 본문이 3GPP SMS 면 바이너리다. 원시 바이트에서 잘라야 깨지지 않는다.
    raw_body = d.split(b"\r\n\r\n", 1)[1] if b"\r\n\r\n" in d else b""
    ctype = next((l for l in t.split("\r\n") if l.lower().startswith("content-type")), "")
    frm = next((l for l in t.split("\r\n") if l.startswith("From:")), "")
    ua.p(f"{ctype}")
    ua.p(f"발신: {frm}")
    if "vnd.3gpp.sms" in ctype.lower():
        sender, body_text, dcs = decode_sms_deliver(raw_body)
        ua.p(f"RP-DATA {len(raw_body)}B  →  발신번호 {sender}  DCS 0x{dcs:02x}" if dcs is not None
             else f"RP-DATA {len(raw_body)}B")
        ua.p(f"본문: {body_text!r}")
        body = body_text
    else:
        body = raw_body.decode(errors='replace')
        ua.p(f"본문({len(raw_body)}B): {body!r}")

    hdr = {}
    for l in t.split("\r\n"):
        for k in ("Via", "From", "To", "Call-ID", "CSeq", "Record-Route"):
            if l.startswith(k + ":"):
                hdr.setdefault(k, []).append(l)
    ok = "\r\n".join(["SIP/2.0 200 OK"] + hdr.get("Via", []) +
                     [hdr["From"][0], hdr["To"][0] + f";tag={rnd(10)}",
                      hdr["Call-ID"][0], hdr["CSeq"][0], "Content-Length: 0", "", ""])
    ua.reply(ok)
    ua.p("→ 200 OK")
    print(f"\n=== SMS 착신 결과 ===\n  본문 수신 ✅  {body!r}")
    return True


def run_callee(ua, talk, wait=40):
    """등록된 UA 로 INVITE 를 기다려 180/200 응답하고 RTP·BYE 까지 처리."""
    ua.p(f"INVITE 대기 ({wait}s, UDP+TCP)…")
    r, _, _ = select.select([ua.sock, ua.tcp_srv], [], [], wait)
    if not r:
        ua.p("✗ INVITE 수신 타임아웃"); return False
    if ua.tcp_srv in r:
        conn, addr = ua.tcp_srv.accept()
        conn.settimeout(8)
        d = recv_sip_tcp(conn)
        ua.tcp_conn = conn
        ua.p(f"TCP 연결 수신 {addr[0]}:{addr[1]}")
    else:
        d, _ = ua.sock.recvfrom(65535)
    t = d.decode(errors='replace'); first = t.split("\r\n")[0]
    ua.p(f"← {first}")
    if not first.startswith("INVITE"):
        ua.p(f"✗ INVITE 아님"); return False

    hdr = {}
    for l in t.split("\r\n"):
        for k in ("Via", "From", "To", "Call-ID", "CSeq", "Record-Route"):
            if l.startswith(k + ":"):
                hdr.setdefault(k, []).append(l)
    body = t.split("\r\n\r\n", 1)[1] if "\r\n\r\n" in t else ""
    pip, pport = parse_sdp_media(body)
    ua.p(f"발신측 미디어 {pip}:{pport}")

    btag = rnd(10)
    def resp(code, reason, with_sdp=False):
        lines = hdr.get("Via", []) + hdr.get("Record-Route", []) + [
            hdr["From"][0], hdr["To"][0] + f";tag={btag}",
            hdr["Call-ID"][0], hdr["CSeq"][0],
            f"Contact: <sip:{ua.msisdn}@{SRC}:{ua.sip_port}>"]
        if with_sdp:
            sd = sdp(SRC, ua.rtp_port)
            lines += ["Content-Type: application/sdp",
                      f"Content-Length: {len(sd)}", "", sd]
        else:
            lines += ["Content-Length: 0", "", ""]
        return "\r\n".join([f"SIP/2.0 {code} {reason}"] + lines)

    ua.p("→ 180 Ringing")
    ua.reply(resp(180, "Ringing"))
    time.sleep(0.4)
    ua.p("→ 200 OK (SDP)")
    ua.reply(resp(200, "OK", True))

    try:
        d2 = ua.recv_next(8)
        ua.p(f"← {d2.decode(errors='replace').split(chr(13))[0]}")
    except (socket.timeout, OSError):
        ua.p("ACK 미수신 (계속)")

    pvport = parse_sdp_video(body)
    if pip and pport:
        ua.p(f"RTP {talk}s 송수신  (audio {pport}" + (f" / video {pvport})" if pvport else ")"))
        ua.rtp_stream(pip, pport, talk, pvport)

    got_bye = False
    try:
        d3 = ua.recv_next(12)
        t3 = d3.decode(errors='replace'); f3 = t3.split("\r\n")[0]
        ua.p(f"← {f3}")
        if f3.startswith("BYE"):
            h = {}
            for l in t3.split("\r\n"):
                for k in ("Via", "From", "To", "Call-ID", "CSeq"):
                    if l.startswith(k + ":"):
                        h.setdefault(k, []).append(l)
            ok = "\r\n".join(["SIP/2.0 200 OK"] + h.get("Via", []) +
                             [h["From"][0], h["To"][0], h["Call-ID"][0],
                              h["CSeq"][0], "Content-Length: 0", "", ""])
            ua.reply(ok)
            ua.p("→ 200 OK (BYE 응답)")
            got_bye = True
    except (socket.timeout, OSError):
        ua.p("BYE 미수신")

    v = f"   video 송신 {ua.vrtp_tx} 수신 {ua.vrtp_rx}" if ua.vrtp else ""
    print(f"\n=== 착신측 결과 ===\n  audio 송신 {ua.rtp_tx} 수신 {ua.rtp_rx}{v}  BYE {'✅' if got_bye else '—'}")
    return True


def send_prack(ua, resp, target, callid, atag, rseq, cseq):
    """18x(Require: 100rel)에 대한 신뢰성 확인. 다이얼로그 안에서 보내야 한다."""
    lines = resp.split("\r\n")
    to_hdr = next(l for l in lines if l.startswith("To:"))
    rr = [l.replace("Record-Route:", "Route:", 1)
          for l in lines if l.startswith("Record-Route:")]
    ct = [l for l in lines if l.lower().startswith("contact:")]
    m = re.search(r'<([^>]+)>', ct[0]) if ct else None
    rt = m.group(1) if m else target
    msg = "\r\n".join([f"PRACK {rt} SIP/2.0",
        f"Via: SIP/2.0/UDP {SRC}:{ua.sip_port};rport;branch=z9hG4bK{rnd(12)}",
        "Max-Forwards: 70"] + rr + [f"From: <{ua.impu}>;tag={atag}", to_hdr,
        f"Call-ID: {callid}", f"CSeq: {cseq} PRACK",
        f"RAck: {rseq} 1 INVITE", "Content-Length: 0", "", ""])
    ua.p(f"→ PRACK (RAck {rseq} 1 INVITE)")
    ua.sock.sendto(msg.encode(), (PCSCF, 5060))


def run_caller(ua, target, talk):
    """등록된 UA 로 target 에 INVITE → ACK → RTP → BYE."""
    sd = sdp(SRC, ua.rtp_port)
    acallid, atag = rnd(16), rnd(10)
    invite = "\r\n".join([
        f"INVITE {target} SIP/2.0",
        f"Via: SIP/2.0/UDP {SRC}:{ua.sip_port};rport;branch=z9hG4bK{rnd(12)}",
        "Max-Forwards: 70",
        f"From: <{ua.impu}>;tag={atag}", f"To: <{target}>",
        f"Call-ID: {acallid}", "CSeq: 1 INVITE",
        f"Contact: <sip:{ua.msisdn}@{SRC}:{ua.sip_port}>",
        f"P-Preferred-Identity: <{ua.impu}>",
        "Allow: INVITE,ACK,CANCEL,BYE,UPDATE,PRACK",
        "Supported: 100rel,timer,precondition", "Content-Type: application/sdp",
        f"Content-Length: {len(sd)}", "", sd])
    ua.p(f"→ INVITE {target}")
    ua.sock.settimeout(15)
    ua.sock.sendto(invite.encode(), (PCSCF, 5060))

    final, early_body = None, ""
    pracked, pcseq = set(), 1
    for _ in range(40):
        try:
            d, _ = ua.sock.recvfrom(65535)
        except socket.timeout:
            break
        t = d.decode(errors='replace'); first = t.split("\r\n")[0]
        ua.p(f"← {first}")
        if first.startswith("SIP/2.0 1"):
            # 전제조건 방식에서는 SDP 응답이 183 에 실려 온다. 200 OK 에는 없다.
            if "\r\n\r\n" in t and "m=audio" in t:
                early_body = t.split("\r\n\r\n", 1)[1]
            rseq = next((l.split(":", 1)[1].strip()
                         for l in t.split("\r\n") if l.lower().startswith("rseq:")), None)
            if rseq and rseq not in pracked:
                pracked.add(rseq); pcseq += 1
                send_prack(ua, t, target, acallid, atag, rseq, pcseq)
            continue
        if first.startswith(("SIP/2.0 2", "SIP/2.0 4", "SIP/2.0 5", "SIP/2.0 6")):
            # PRACK 에 대한 200 OK 를 통화 응답으로 착각하면 그 자리에서 끊긴다.
            cs = next((l.split(":", 1)[1].strip()
                       for l in t.split("\r\n") if l.lower().startswith("cseq:")), "")
            if not cs.upper().endswith("INVITE"):
                ua.p(f"   (무시: {cs} 에 대한 응답)")
                continue
            final = t; break
    bye_cseq = pcseq + 1

    if not (final and final.split("\r\n")[0].startswith("SIP/2.0 200")):
        ua.p(f"✗ 통화 성립 실패: {final.split(chr(13))[0] if final else '응답 없음'}")
        return False

    body = final.split("\r\n\r\n", 1)[1] if "\r\n\r\n" in final else ""
    if "m=audio" not in body and early_body:
        ua.p("   200 OK 에 SDP 없음 → 183 의 응답 SDP 사용")
        body = early_body
    bip, bport = parse_sdp_media(body)
    ua.p(f"착신측 미디어 {bip}:{bport}")
    to_hdr = [l for l in final.split("\r\n") if l.startswith("To:")][0]

    # RFC 3261 12.1.2: 2xx 의 Record-Route 를 그 순서대로 Route set 으로 쓴다.
    # Record-Route 헤더 이름을 그대로 넣으면 프록시가 다이얼로그를 못 찾아 404 가 된다.
    rr = [l.replace("Record-Route:", "Route:", 1)
          for l in final.split("\r\n") if l.startswith("Record-Route:")]
    # 2xx 에 대한 ACK/BYE 의 Request-URI 는 remote target(200 OK 의 Contact)이다.
    ct = [l for l in final.split("\r\n") if l.lower().startswith("contact:")]
    m = re.search(r'<([^>]+)>', ct[0]) if ct else None
    remote_target = m.group(1) if m else target
    ua.p(f"remote target {remote_target}  (Route {len(rr)}개)")

    def req(method, cseq):
        return "\r\n".join([f"{method} {remote_target} SIP/2.0",
            f"Via: SIP/2.0/UDP {SRC}:{ua.sip_port};rport;branch=z9hG4bK{rnd(12)}",
            "Max-Forwards: 70"] + rr + [f"From: <{ua.impu}>;tag={atag}", to_hdr,
            f"Call-ID: {acallid}", f"CSeq: {cseq} {method}",
            f"Contact: <sip:{ua.msisdn}@{SRC}:{ua.sip_port}>",
            "Content-Length: 0", "", ""])

    ua.p("→ ACK  (통화 성립)")
    ua.sock.sendto(req("ACK", 1).encode(), (PCSCF, 5060))

    bvport = parse_sdp_video(body)
    if bip and bport:
        ua.p(f"RTP {talk}s 송수신  (audio {bport}" + (f" / video {bvport})" if bvport else ")"))
        ua.rtp_stream(bip, bport, talk, bvport)

    ua.p("→ BYE")
    ua.sock.sendto(req("BYE", bye_cseq).encode(), (PCSCF, 5060))
    ua.sock.settimeout(10)
    try:
        d, _ = ua.sock.recvfrom(65535)
        ua.p(f"← {d.decode(errors='replace').split(chr(13))[0]}")
    except socket.timeout:
        ua.p("BYE 응답 타임아웃")

    v = f"   video 송신 {ua.vrtp_tx} 수신 {ua.vrtp_rx}" if ua.vrtp else ""
    print(f"\n=== 발신측 결과 ===\n  audio 송신 {ua.rtp_tx} 수신 {ua.rtp_rx}{v}  통화 성립 ✅")
    return True


def main():
    print(f"\n=== IMS 테스트  P-CSCF={PCSCF}  SRC={SRC}  role={ROLE} ===\n")

    if ROLE == "reg-a":
        sys.exit(0 if UA(UA_A).register() else 1)
    if ROLE == "reg-b":
        sys.exit(0 if UA(UA_B).register() else 1)
    if ROLE == "callee":
        u = UA(UA_B)
        if not u.register():
            sys.exit(1)
        sys.exit(0 if run_callee(u, TALK) else 1)
    if ROLE == "caller":
        u = UA(UA_A)
        if not u.register():
            sys.exit(1)
        tgt = sys.argv[5] if len(sys.argv) > 5 else f"sip:{UA_B['msisdn']}@{REALM}"
        sys.exit(0 if run_caller(u, tgt, TALK) else 1)
    if ROLE == "sms-send":
        u = UA(UA_A)
        if not u.register():
            sys.exit(1)
        tgt = sys.argv[5] if len(sys.argv) > 5 else f"sip:{UA_B['msisdn']}@{REALM}"
        text = sys.argv[6] if len(sys.argv) > 6 else "사설 5G IMS 문자 테스트"
        dest = sys.argv[7] if len(sys.argv) > 7 else UA_B['msisdn']
        sys.exit(0 if run_sms_send(u, tgt, text, dest) else 1)
    if ROLE == "sms-recv":
        u = UA(UA_B)
        if not u.register():
            sys.exit(1)
        sys.exit(0 if run_sms_recv(u) else 1)

    a, b = UA(UA_A), UA(UA_B)

    print("--- 1단계: UA-B 등록 (착신측) ---")
    if not b.register():
        sys.exit("UA-B 등록 실패")
    print("\n--- 2단계: UA-A 등록 (발신측) ---")
    if not a.register():
        sys.exit("UA-A 등록 실패")

    # 착신·발신 모두 실물 단말로 검증된 run_callee/run_caller 를 쓴다.
    # 예전에는 전체 모드가 자기만의 INVITE·응답 코드를 따로 들고 있었다. 그쪽 착신부는
    # UDP 만 들어서, INVITE 가 1300바이트를 넘어 P-CSCF 가 TCP 로 넘기면 받지 못했다.
    # 그때 발신측에 보이던 것이 `500 Server error on LIR select next S-CSCF` 다.
    # LIR 실패가 아니라 착신부가 TCP 를 안 들어서 생긴 증상이었다.
    state = {}

    def callee():
        state['ok'] = run_callee(b, TALK)

    th = threading.Thread(target=callee, daemon=True)
    th.start()
    time.sleep(1.0)

    print("\n--- 3단계: UA-A → UA-B INVITE ---")
    ok = run_caller(a, f"sip:{b.msisdn}@{REALM}", TALK)
    th.join(timeout=TALK + 15)
    state['bye'] = bool(state.get('ok'))
    print("\n=== 결과 ===")
    print(f"  UA-A RTP  송신 {a.rtp_tx}  수신 {a.rtp_rx}")
    print(f"  UA-B RTP  송신 {b.rtp_tx}  수신 {b.rtp_rx}")
    if state.get('err'):
        print(f"  착신측 오류: {state['err']}")
    print(f"  통화 성립: {'✅' if ok else '❌'}   BYE 확인: {'✅' if state.get('bye') else '—'}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
