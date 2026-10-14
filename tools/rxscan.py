#!/usr/bin/python3
import sys, numpy as np, uhd
serial = sys.argv[1]
N, RATE, GAIN = 2000000, 20e6, 60.0
usrp = uhd.usrp.MultiUSRP(f"serial={serial}")
FREQS = [(2412e6,"WiFi ch1 (혼잡)"), (2437e6,"WiFi ch6 (혼잡)"),
         (2300e6,"2300 (조용)"), (1500e6,"1500 (조용)")]
print(f"  [{serial}]  rate 20 Msps, gain {GAIN:.0f} dB")
print(f"  {'포트':<7}{'주파수':<20}{'RMS':>10}{'피크':>10}{'차이':>8}")
print("  " + "-"*56)
names = {(0,"TX/RX"):"TRXA",(0,"RX2"):"RXA",(1,"RX2"):"RXB",(1,"TX/RX"):"TRXB"}
for ch,ant in ((0,"TX/RX"),(0,"RX2"),(1,"TX/RX"),(1,"RX2")):
    usrp.set_rx_antenna(ant, ch)
    base = None
    for f,label in FREQS:
        s = usrp.recv_num_samps(N, f, RATE, [ch], GAIN)
        d = np.asarray(s).flatten()[5000:]
        rms  = 20*np.log10(np.sqrt(np.mean(np.abs(d)**2))+1e-12)
        peak = 20*np.log10(np.max(np.abs(d))+1e-12)
        if "조용" in label and base is None: base = rms
        print(f"  {names[(ch,ant)]:<7}{label:<20}{rms:>7.1f} dB{peak:>8.1f} dB", end="")
        print(f"{(rms-base):>7.1f}" if base is not None and "혼잡" not in label else "")
    print()
