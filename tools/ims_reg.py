#!/usr/bin/env python3
import socket, random, string, sys
PCSCF = sys.argv[1]; SRC = sys.argv[2]
IMSI="001011234567895"; REALM="ims.mnc001.mcc001.3gppnetwork.org"
IMPI=f"{IMSI}@{REALM}"; IMPU=f"sip:{IMSI}@{REALM}"
rnd=lambda n:''.join(random.choices(string.ascii_lowercase+string.digits,k=n))
msg="\r\n".join([
 f"REGISTER sip:{REALM} SIP/2.0",
 f"Via: SIP/2.0/UDP {SRC}:5060;rport;branch=z9hG4bK{rnd(12)}","Max-Forwards: 70",
 f"From: <{IMPU}>;tag={rnd(10)}", f"To: <{IMPU}>", f"Call-ID: {rnd(16)}",
 "CSeq: 1 REGISTER", f"Contact: <sip:{IMSI}@{SRC}:5060>;expires=600000",
 f'Authorization: Digest username="{IMPI}",realm="{REALM}",nonce="",uri="sip:{REALM}",response="",algorithm=AKAv1-MD5',
 "Supported: path","Expires: 600000","Content-Length: 0","",""])
s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM); s.bind((SRC,5060)); s.settimeout(6)
print(f"  → REGISTER 전송 → {PCSCF}:5060\n")
s.sendto(msg.encode(),(PCSCF,5060))
for i in range(4):
    try:
        data,addr=s.recvfrom(65535); t=data.decode(errors='replace')
        status=t.split("\r\n")[0]
        print(f"  ← [{i+1}] {status}")
        for line in t.split("\r\n"):
            if line.startswith(("WWW-Authenticate","Security-Server","Service-Route","P-Associated-URI","Path","Warning","Reason")):
                print(f"        {line[:160]}")
        if not status.startswith("SIP/2.0 1"): break
    except socket.timeout:
        print(f"  ← [{i+1}] 타임아웃"); break
