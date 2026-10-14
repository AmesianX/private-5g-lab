#!/usr/bin/python3
"""B210 포트별 수신 전력 측정 — 안테나 연결 여부 판정용"""
import sys, numpy as np, uhd

serial = sys.argv[1]
freq   = float(sys.argv[2]) if len(sys.argv) > 2 else 2412e6
gain   = float(sys.argv[3]) if len(sys.argv) > 3 else 40.0
N, RATE = 400000, 2e6

usrp = uhd.usrp.MultiUSRP(f"serial={serial}")
print(f"  [{serial}]  {freq/1e6:.0f} MHz, gain {gain:.0f} dB")
print(f"  {'포트':<8}{'채널':<6}{'안테나':<8}{'수신전력':>12}")
print("  " + "-"*36)
names = {(0,"TX/RX"):"TRXA", (0,"RX2"):"RXA", (1,"RX2"):"RXB", (1,"TX/RX"):"TRXB"}
for ch in (0, 1):
    for ant in ("TX/RX", "RX2"):
        try:
            usrp.set_rx_antenna(ant, ch)
            s = usrp.recv_num_samps(N, freq, RATE, [ch], gain)
            d = np.asarray(s).flatten()[2000:]
            p = 20*np.log10(np.sqrt(np.mean(np.abs(d)**2)) + 1e-12)
            print(f"  {names[(ch,ant)]:<8}{ch:<6}{ant:<8}{p:>9.1f} dBFS")
        except Exception as e:
            print(f"  {names[(ch,ant)]:<8}{ch:<6}{ant:<8}{'ERR':>12}  {str(e)[:40]}")
