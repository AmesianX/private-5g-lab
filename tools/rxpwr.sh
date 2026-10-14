#!/bin/bash
# B210 포트별 수신 전력 측정
SER=$1; FREQ=${2:-2412e6}; GAIN=${3:-40}
EX=/usr/libexec/uhd/examples/rx_samples_to_file
TMP=/tmp/rxcap.dat
printf "%-6s %-8s %s\n" "채널" "안테나" "수신전력(dBFS)"
for CH in 0 1; do
  for ANT in "TX/RX" "RX2"; do
    timeout 60 $EX --args "serial=$SER" --freq $FREQ --rate 2e6 --gain $GAIN \
      --nsamps 400000 --channels $CH --ant "$ANT" --type float --file $TMP >/dev/null 2>&1
    P=$(python3 - "$TMP" <<'PY'
import numpy as np, sys
try:
    d = np.fromfile(sys.argv[1], dtype=np.complex64)
    d = d[2000:]
    p = np.sqrt(np.mean(np.abs(d)**2))
    print(f"{20*np.log10(p+1e-12):.1f}")
except Exception as e:
    print("ERR")
PY
)
    printf "%-6s %-8s %s\n" "$CH" "$ANT" "$P"
    rm -f $TMP
  done
done
