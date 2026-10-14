import sys; sys.path.insert(0,'.')
from milenage import f1, f2345
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import labsecrets
# 카드 키는 configs/secrets/lab.env 에서 읽는다.
_k, _o = labsecrets.need('UE1_KI', 'UE1_OPC')
KI  = bytes.fromhex(_k)
OPC = bytes.fromhex(_o)
RAND = bytes.fromhex("500222f6ae14f6e2a4de2465d31c0e8e")
AUTN = bytes.fromhex("05e767ce2f9880007cb7cc066532c220")

RES, CK, IK, AK, _ = f2345(KI, OPC, RAND)
sqn_ak, amf, mac_a = AUTN[:6], AUTN[6:8], AUTN[8:16]
SQN = bytes(a ^ b for a, b in zip(sqn_ak, AK))
mac_calc, _ = f1(KI, OPC, RAND, SQN, amf)

exp_ck = "c6798b905d0198108b2de18381d6f399"
exp_ik = "554cfaaeb71a713b2c4176f21695f641"
ok = lambda c, e: "✅ 일치" if c == e else f"❌ 불일치 (기대 {e})"

print(f"  RES   = {RES.hex()}")
print(f"  CK    = {CK.hex()}   {ok(CK.hex(), exp_ck)}")
print(f"  IK    = {IK.hex()}   {ok(IK.hex(), exp_ik)}")
print(f"  AK    = {AK.hex()}")
print(f"  SQN   = {SQN.hex()}")
print(f"  AMF   = {amf.hex()}")
print(f"  MAC-A = {mac_calc.hex()}  vs AUTN의 {mac_a.hex()}  "
      f"{'✅ 인증 성공' if mac_calc == mac_a else '❌ 네트워크 인증 실패'}")
