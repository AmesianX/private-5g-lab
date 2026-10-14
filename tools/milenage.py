"""3GPP TS 35.206 MILENAGE — openssl AES-128-ECB 사용 (외부 의존 없음)"""
import subprocess

def aes128(key: bytes, data: bytes) -> bytes:
    p = subprocess.run(
        ["openssl","enc","-aes-128-ecb","-K",key.hex(),"-nopad"],
        input=data, capture_output=True)
    return p.stdout[:16]

def rot(b: bytes, n: int) -> bytes:
    n //= 8
    return b[n:] + b[:n]

def xor(a: bytes, b: bytes) -> bytes:
    return bytes(x ^ y for x, y in zip(a, b))

C = [bytes(16), (1).to_bytes(16,'big'), (2).to_bytes(16,'big'),
     (4).to_bytes(16,'big'), (8).to_bytes(16,'big')]
R = [64, 0, 32, 64, 96]

def f1(ki, opc, rand, sqn, amf):
    temp = aes128(ki, xor(rand, opc))
    in1  = sqn + amf + sqn + amf
    out1 = aes128(ki, xor(xor(temp, rot(xor(in1, opc), R[0])), C[0]))
    out1 = xor(out1, opc)
    return out1[:8], out1[8:]          # MAC-A, MAC-S

def f2345(ki, opc, rand):
    temp = aes128(ki, xor(rand, opc))
    o2 = xor(aes128(ki, xor(rot(xor(temp,opc), R[1]), C[1])), opc)
    o3 = xor(aes128(ki, xor(rot(xor(temp,opc), R[2]), C[2])), opc)
    o4 = xor(aes128(ki, xor(rot(xor(temp,opc), R[3]), C[3])), opc)
    o5 = xor(aes128(ki, xor(rot(xor(temp,opc), R[4]), C[4])), opc)
    return o2[8:], o3, o4, o2[:6], o5[:6]   # RES, CK, IK, AK, AK*
