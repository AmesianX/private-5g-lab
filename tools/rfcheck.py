#!/usr/bin/env python3
"""ALFA 안테나/부스터 체인 검증 도구.

내장 wifi 카드를 동시 기준(reference)으로 써서 환경 변동을 상쇄하고,
ALFA - 내장 의 dB 차이(delta)를 설정별로 비교한다.
스캔은 전부 passive(무송신)라서 안테나 미연결 상태에서도 PA에 무리가 없다.
"""
import csv, os, re, statistics as st, subprocess, sys, time

ALFA = "wlx00c0cab8dc52"
REF = "wlp195s0"
FREQS = "2412 2442 2457 5180 5220 5765".split()
CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rf_samples.csv")

BSS_RE = re.compile(r"^BSS ([0-9a-f:]{17})")
SIG_RE = re.compile(r"^\s+signal:\s+(-?[\d.]+) dBm")
FRQ_RE = re.compile(r"^\s+freq:\s+([\d.]+)")
SSID_RE = re.compile(r"^\s+SSID: (.*)$")


def scan(dev):
    cmd = ["sudo", "-n", "timeout", "25", "iw", "dev", dev, "scan",
           "freq", *FREQS, "passive"]
    return subprocess.Popen(cmd, stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL, text=True)


def parse(out):
    rows, cur = [], None
    for line in out.splitlines():
        m = BSS_RE.match(line)
        if m:
            if cur and cur.get("signal") is not None:
                rows.append(cur)
            cur = {"bssid": m.group(1), "signal": None, "freq": None, "ssid": ""}
            continue
        if cur is None:
            continue
        if (m := SIG_RE.match(line)):
            cur["signal"] = float(m.group(1))
        elif (m := FRQ_RE.match(line)):
            cur["freq"] = float(m.group(1))
        elif (m := SSID_RE.match(line)):
            cur["ssid"] = m.group(1)
    if cur and cur.get("signal") is not None:
        rows.append(cur)
    return rows


def measure(label, rounds):
    new = []
    for r in range(1, rounds + 1):
        # 두 라디오를 동시에 돌려 같은 순간의 전파 환경을 본다
        pa, pr = scan(ALFA), scan(REF)
        oa, _ = pa.communicate()
        orr, _ = pr.communicate()
        for radio, out in (("alfa", oa), ("ref", orr)):
            for row in parse(out):
                new.append([label, r, radio, row["bssid"], row["freq"],
                            row["signal"], row["ssid"]])
        print(f"  round {r}/{rounds}: alfa={sum(1 for x in new if x[1]==r and x[2]=='alfa')} "
              f"ref={sum(1 for x in new if x[1]==r and x[2]=='ref')} APs", flush=True)
        time.sleep(1)
    exists = os.path.exists(CSV)
    with open(CSV, "a", newline="") as f:
        w = csv.writer(f)
        if not exists:
            w.writerow(["label", "round", "radio", "bssid", "freq", "signal", "ssid"])
        w.writerows(new)
    print(f"\n[{label}] {len(new)} samples -> {CSV}")


def load():
    if not os.path.exists(CSV):
        return {}
    data = {}
    with open(CSV) as f:
        for row in csv.DictReader(f):
            key = (row["label"], row["radio"], row["bssid"])
            data.setdefault(key, {"sig": [], "freq": float(row["freq"]),
                                  "ssid": row["ssid"]})["sig"].append(float(row["signal"]))
    return data


def summarize(label, data, band=None):
    """band: None=전체, 24=2.4GHz, 5=5GHz"""
    def inband(f):
        return band is None or (band == 24 and f < 3000) or (band == 5 and f >= 5000)
    alfa = {b: v for (l, r, b), v in data.items() if l == label and r == "alfa" and inband(v["freq"])}
    ref = {b: v for (l, r, b), v in data.items() if l == label and r == "ref" and inband(v["freq"])}
    common = sorted(set(alfa) & set(ref))
    deltas = [st.median(alfa[b]["sig"]) - st.median(ref[b]["sig"]) for b in common]
    return {"n_alfa": len(alfa), "n_ref": len(ref), "n_common": len(common),
            "delta": st.median(deltas) if deltas else None,
            "alfa_med": st.median([st.median(v["sig"]) for v in alfa.values()]) if alfa else None,
            "common": common, "alfa": alfa, "ref": ref}


def report(labels=None):
    data = load()
    if not data:
        print("샘플 없음. 먼저 measure 를 실행하세요.")
        return
    order = []
    for (l, _, _) in data:
        if l not in order:
            order.append(l)
    labels = labels or order
    print("=" * 74)
    print(f"{'설정':<18} {'대역':<6} {'ALFA AP':>8} {'기준 AP':>8} {'공통':>5} {'ALFA-기준':>10}")
    print("-" * 74)
    for lb in labels:
        for band, name in ((24, "2.4G"), (5, "5G"), (None, "전체")):
            s = summarize(lb, data, band)
            if s["n_alfa"] == 0 and s["n_ref"] == 0:
                continue
            d = f"{s['delta']:+.1f} dB" if s["delta"] is not None else "n/a"
            print(f"{lb:<18} {name:<6} {s['n_alfa']:>8} {s['n_ref']:>8} {s['n_common']:>5} {d:>10}")
        print("-" * 74)
    if len(labels) >= 2:
        print("\n### 설정 간 차이 (기준 설정 대비)")
        base = labels[0]
        for lb in labels[1:]:
            for band, name in ((24, "2.4G"), (5, "5G")):
                a = summarize(base, data, band)["delta"]
                b = summarize(lb, data, band)["delta"]
                if a is None or b is None:
                    continue
                print(f"  {name:<5} {lb} vs {base}: {b - a:+.1f} dB")


def detail(label):
    data = load()
    s = summarize(label, data)
    print(f"\n[{label}] AP별 상세 (ALFA - 기준)")
    print(f"{'BSSID':<19} {'MHz':>6} {'ALFA':>7} {'기준':>7} {'차이':>8}  SSID")
    for b in sorted(s["common"], key=lambda x: s["alfa"][x]["freq"]):
        a, r = st.median(s["alfa"][b]["sig"]), st.median(s["ref"][b]["sig"])
        print(f"{b:<19} {s['alfa'][b]['freq']:>6.0f} {a:>7.1f} {r:>7.1f} {a-r:>+8.1f}  {s['alfa'][b]['ssid'][:24]}")
    only = sorted(set(s["alfa"]) - set(s["ref"]))
    if only:
        print(f"\nALFA만 수신 ({len(only)}개):")
        for b in only:
            print(f"  {b} {s['alfa'][b]['freq']:.0f} MHz {st.median(s['alfa'][b]['sig']):.1f} dBm  {s['alfa'][b]['ssid'][:24]}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "report"
    if cmd == "measure":
        measure(sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 6)
        report()
    elif cmd == "detail":
        detail(sys.argv[2])
    elif cmd == "reset":
        os.path.exists(CSV) and os.remove(CSV)
        print("초기화 완료")
    else:
        report(sys.argv[2:] or None)
