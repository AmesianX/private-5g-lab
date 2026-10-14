#!/usr/bin/python3.12
"""차폐함 누설 계측 — B210 포트별 수신 레벨(dBFS).

절대 dBm 은 교정된 신호원이 없어 알 수 없다. 그래서 **송신 켬/끔 차이**를 본다.
차이가 잡음바닥 흔들림 이내면 누설은 이 장비의 검출 한계 아래라는 뜻이다.
"""
import sys, numpy as np, uhd

serial = sys.argv[1]
gain = float(sys.argv[2]) if len(sys.argv) > 2 else 60.0
freqs = [(float(a.split(':')[0]), a.split(':')[1]) for a in sys.argv[3:]]
RATE, N = 2e6, 400000
PORTS = [(0, "TX/RX"), (0, "RX2"), (1, "TX/RX"), (1, "RX2")]

u = uhd.usrp.MultiUSRP(f"serial={serial}")
print(f"  [{serial}] rate {RATE/1e6:.0f} Msps, gain {gain:.0f} dB, 샘플 {N}\n")
print(f"  {'주파수':<22}{'ch0 TX/RX':>11}{'ch0 RX2':>11}{'ch1 TX/RX':>11}{'ch1 RX2':>11}")
print("  " + "-" * 66)
for f, label in freqs:
    row = []
    for ch, ant in PORTS:
        try:
            u.set_rx_antenna(ant, ch)
            u.set_rx_gain(gain, ch)
            d = u.recv_num_samps(N, f, RATE, [ch], gain)[0]
            d = d[len(d) // 10:]                      # 정착 구간 버림
            rms = float(np.sqrt(np.mean(np.abs(d) ** 2)))
            row.append(f"{20*np.log10(rms+1e-12):11.2f}")
        except Exception as e:
            row.append(f"{'err':>11}")
            print(f"    ({ch},{ant}) {e}", file=sys.stderr)
    print(f"  {label:<22}" + "".join(row))
