#!/usr/bin/env python3
"""IMS AKAv1-MD5 전체 등록: REGISTER → 401 챌린지 → RES 계산 → REGISTER → 200 OK"""
import socket, random, string, sys, base64, hashlib, subprocess, re

PCSCF, SRC = sys.argv[1], sys.argv[2]
IMSI  = "001011234567895"
REALM = "ims.mnc001.mcc001.3gppnetwork.org"
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import labsecrets
# 카드 키는 configs/secrets/lab.env 에서 읽는다.
_k, _o = labsecrets.need('UE1_KI', 'UE1_OPC')
KI  = bytes.fromhex(_k)
OPC = bytes.fromhex(_o)
IMPI, IMPU = f"{IMSI}@{REALM}", f"sip:{IMSI}@{REALM}"
URI = f"sip:{REALM}"

# ---------- MILENAGE ----------
def aes(k, d): return subprocess.run(["openssl","enc","-aes-128-ecb","-K",k.hex(),"-nopad"],
                                     input=d, capture_output=True).stdout[:16]
rot = lambda b,n: b[n//8:]+b[:n//8]
xor = lambda a,b: bytes(x^y for x,y in zip(a,b))
C=[bytes(16)]+[ (v).to_bytes(16,'big') for v in (1,2,4,8)]; R=[64,0,32,64,96]
def f2345(ki,opc,rand):
    t=aes(ki,xor(rand,opc))
    o=[xor(aes(ki,xor(rot(xor(t,opc),R[i]),C[i])),opc) for i in range(1,5)]
    return o[0][8:], o[1], o[2], o[0][:6]          # RES, CK, IK, AK
def f1(ki,opc,rand,sqn,amf):
    t=aes(ki,xor(rand,opc)); in1=sqn+amf+sqn+amf
    o=xor(aes(ki,xor(xor(t,rot(xor(in1,opc),R[0])),C[0])),opc)
    return o[:8]

# ---------- SIP ----------
rnd=lambda n:''.join(random.choices(string.ascii_lowercase+string.digits,k=n))
CALLID, TAG = rnd(16), rnd(10)
sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM); sock.bind((SRC,5060)); sock.settimeout(6)

def send(msg, label):
    sock.sendto(msg.encode(),(PCSCF,5060))
    for _ in range(4):
        try: d,_a = sock.recvfrom(65535)
        except socket.timeout: return None
        t=d.decode(errors='replace'); st=t.split("\r\n")[0]
        print(f"  ← [{label}] {st}")
        if not st.startswith("SIP/2.0 1"): return t
    return None

def register(cseq, auth):
    return "\r\n".join([
      f"REGISTER {URI} SIP/2.0",
      f"Via: SIP/2.0/UDP {SRC}:5060;rport;branch=z9hG4bK{rnd(12)}","Max-Forwards: 70",
      f"From: <{IMPU}>;tag={TAG}", f"To: <{IMPU}>", f"Call-ID: {CALLID}",
      f"CSeq: {cseq} REGISTER", f"Contact: <sip:{IMSI}@{SRC}:5060>;expires=600000",
      auth, "Supported: path","Expires: 600000","Content-Length: 0","",""])

print(f"  → 1차 REGISTER (빈 인증) → {PCSCF}:5060")
r1 = send(register(1, f'Authorization: Digest username="{IMPI}",realm="{REALM}",'
                      f'nonce="",uri="{URI}",response="",algorithm=AKAv1-MD5'), "1차")
if not r1 or "401" not in r1.split("\r\n")[0]:
    print("  ✗ 401 챌린지를 못 받음"); sys.exit(1)

wa = [l for l in r1.split("\r\n") if l.lower().startswith("www-authenticate")][0]
nonce = re.search(r'nonce="([^"]+)"', wa).group(1)
raw = base64.b64decode(nonce); RAND, AUTN = raw[:16], raw[16:32]
print(f"\n  nonce  : {nonce[:40]}...")
print(f"  RAND   : {RAND.hex()}")
print(f"  AUTN   : {AUTN.hex()}")

RES, CK, IK, AK = f2345(KI,OPC,RAND)
sqn = xor(AUTN[:6], AK); amf = AUTN[6:8]
mac = f1(KI,OPC,RAND,sqn,amf)
print(f"  SQN    : {sqn.hex()}   AMF: {amf.hex()}")
print(f"  MAC-A  : {mac.hex()}  {'✅ 네트워크 인증 OK' if mac==AUTN[8:16] else '❌ 불일치'}")
print(f"  RES    : {RES.hex()}")
print(f"  CK/IK  : {CK.hex()} / {IK.hex()}")

# RFC 3310: password = RES 원시 옥텟
md5 = lambda b: hashlib.md5(b).hexdigest()
ha1 = md5(IMPI.encode()+b":"+REALM.encode()+b":"+RES)
ha2 = md5(f"REGISTER:{URI}".encode())
nc, cnonce = "00000001", rnd(16)
resp = md5(f"{ha1}:{nonce}:{nc}:{cnonce}:auth:{ha2}".encode())
print(f"  digest : {resp}\n")

auth2 = (f'Authorization: Digest username="{IMPI}",realm="{REALM}",nonce="{nonce}",'
         f'uri="{URI}",response="{resp}",algorithm=AKAv1-MD5,cnonce="{cnonce}",'
         f'qop=auth,nc={nc}')
print(f"  → 2차 REGISTER (RES 응답)")
r2 = send(register(2, auth2), "2차")
if r2:
    for l in r2.split("\r\n"):
        if l.startswith(("Service-Route","P-Associated-URI","Path","Contact","Expires","Warning")):
            print(f"        {l[:150]}")
