# private5g — A Private Local 5G SA Network

[한국어](README.md) · **English**

> **Phreaking was the hacker's playground of the 1970s. Today, it's building your own local 5G network.**

This repository brings up a **working 5G standalone (SA) mobile network** on one Linux box and one SDR. Real commercial handsets attach to it, phones ring, and texts and pictures go back and forth.

📕 **The whole journey of building this network is written up as a book:** *Building a Local 5G Network — A Hacker's Field Guide to Mobile Networks* (in Korean)
· [**Download the PDF**](https://github.com/AmesianX/local-5g-handbook/releases/latest/download/local-5g-handbook-ko.pdf) · [Manuscript repository](https://github.com/AmesianX/local-5g-handbook)

<table>
<tr>
<td align="center"><img src="docs/screenshots/06-%ED%86%B5%ED%99%94%EC%A4%91.png" width="260" alt="A VoNR call on our own network, HD and 5G in the status bar"><br><sub>A VoNR call carried over our own network. <code>HD</code> · <code>5G</code> in the status bar</sub></td>
<td align="center"><img src="docs/screenshots/09-%EB%AC%B8%EC%9E%90-270%EC%9E%90%ED%95%9C%ED%86%B5.png" width="260" alt="A 270-character text arriving as a single message"><br><sub>A 270-character text arriving whole, not in pieces</sub></td>
</tr>
</table>

## Why we built it

In the 1970s, phone phreaks whistled 2600 Hz into a handset to move switches on the far side of a continent, and through that crack they got hooked on peering into the guts of a vast telephone network. For the half-century that followed, mobile networks were the most closed territory a hacker could face. Now the core has turned into Linux processes calling one another over HTTP/2, and the base station runs on a software radio plugged into USB. If the phreaks found ways to fool the switch, we now get to **own the switch**. We sign up subscribers on SIMs whose secret keys we chose and burned ourselves, ring a real phone with a number we issued, and follow every message in between, from first to last, in Wireshark.

Nor does it end as a toy. The network's only way out to the internet is the Linux box's default route, so take the box and the radio somewhere the commercial network has gone dark, plug in a satellite terminal, and our cell comes alive right there. That is the real goal of this repository: **a network of our own to bring up when the commercial network is down.** It has been validated on 5G SA, and the actual deployment target is 4G LTE.

We publish this repository and the book because we want to leave a signpost at every spot where we got lost. We lost half a day to a single USB 2.0 cable, and watched a real phone reject, on its very first call, a call setup that had worked between our scripts for four months. We would like the next person not to throw away the same hours in the same places.

## 🤖 Don't type it in by hand — hand it to Claude Code

Further down, this README describes how to rebuild the same network from bare metal, step by step, with a way to verify each step. You don't have to type it in line by line, though. Open [Claude Code](https://claude.com/claude-code) in a clone of this repository and hand it over like this:

```text
Rebuild this network from scratch following the rebuild guide in the README.
Show me that each step's verification passed, and stop to get my confirmation right before the base station transmits.
```

It will fetch the upstream project, load the images, render the configuration, provision the subscribers and bring up the core and IMS, verifying as it goes, and be done in no time. That this procedure really stands up from this repository alone was confirmed on 2026-10-15: we wiped everything down to the database volumes and rebuilt from a fresh clone from GitHub.

**But the things you can hold in your hand have to be prepared by a person in advance.** Claude Code builds software; it can't buy a card or tighten a cable.

- **USIM** — a card you can write keys to (we used the sysmoISIM-SJA5) and a PC/SC card reader. Put the Ki, OPc and ADM1 values that come with the card into `configs/secrets/lab.env`, copied from `configs/secrets/lab.env.example`. Be sure to read the USIM trap under "0. Hardware" first.
- **Hardware** — a Linux host with a USB 3.0 port (Ubuntu 24.04), an SDR (USRP B210 or compatible), a UE (Quectel RM520N-GL 5G modem, or a real phone plus a shield box), coaxial cables, **40 dB attenuators**, and 50 Ω terminators.
- **Wiring and permission to transmit** — connecting cables, fitting the attenuators, and checking the wiring with your own eyes before the base station transmits for the first time are a person's job. Connect directly without an attenuator and you burn the B210's receiver; let it leak into the air and you interfere with other people's communications.

---

## What you end up with

| | Measured |
|---|---|
| 5G SA registration | A real Galaxy S22+ shows `HOME`, technology `NR`, PLMN `001/01` |
| Data | RTT to the UPF 25–31 ms, to the outside 54–58 ms, 0 % loss |
| Voice (VoNR) | Incoming call shown on the handset, call established, RTP in both directions |
| Video call | Video RTP sent 332 / received 2697 (20 s) |
| SMS | No length limit (UDH concatenated SMS). 270 characters merged into one message |
| Multimedia (MMS) | Both directions. A JPEG sent by the handset matches the original by SHA256 |
| RF leakage | Not detected outside the shield box (method and limits: [book §15.5a](https://github.com/AmesianX/local-5g-handbook/blob/master/15-%EC%8B%9C%ED%97%98%EC%A0%88%EC%B0%A8%EC%99%80%EC%B8%A1%EC%A0%95.md)) |

## ⚠ Before you transmit — mandatory

Radio goes through walls. **The moment you radiate into the open air, you are operating a radio station that requires a licence.** Under Korea's Radio Waves Act, establishing or operating an unlicensed radio station is punishable by up to 3 years in prison or a fine of up to 30 million won. Check the rules where you live.

- PLMN is fixed to the test code **001/01**. Never use commercial codes (450-05 SKT / 450-06 LGU+ / 450-08 KT)
- Cross-check the frequency against commercial allocations. n78 in Korea: LG U+ 3400–3500 / KT 3500–3600 / SKT 3600–3700 MHz
- **Don't trust the frequencies in upstream examples.** Most default to the middle of a commercial band
- Transmit over **direct coax + attenuators**, terminate unused ports with **50 Ω**, and use a **shield box** if you can
- Always start the transmit gain at the minimum
- If an SDR with an antenna is attached to the same host, make sure that device is never opened (`serial=` pin)

Details: [book Appendix D, "Radio and legal notice"](https://github.com/AmesianX/local-5g-handbook/blob/master/%EB%B6%80%EB%A1%9DD-%EC%A0%84%ED%8C%8C%EC%99%80%EB%B2%95%EA%B7%9C%EA%B3%A0%EC%A7%80.md).

---

# Rebuild guide

Follow the steps in order. Each step ends with **how to verify** it. If verification fails, don't move on — it will come back later as some unrelated-looking symptom.

> **Verification record.** This procedure was actually torn down and rebuilt end to end on 2026-10-15.
> We removed the containers **and the database volumes** with `docker compose down -v`, then
> **cloned this repository fresh** from GitHub and rebuilt from that alone. Result: rendered configs
> bit-identical to before, core NFs 5/5, 3 subscribers created, and the real handset re-registered on `00101`,
> got both its internet (10.45.x) and IMS (10.46.x) sessions, and exchanged texts.
>
> The process exposed **three defects in this repository**, which we fixed: the upstream path could not be
> found through a symlink; `cd && pwd` returned the logical path so the symlink pointed at itself; and
> **on an empty database the PyHSS APN rows were never created, so subscriber provisioning hit a
> foreign-key constraint.** That last kind never shows up on a lab that is already running.

## 0. Hardware — be especially careful with the USIM

| Item | What we used | Notes |
|---|---|---|
| Linux host | Ubuntu 24.04, x86_64 | Anything that runs Docker |
| SDR | Ettus **USRP B210** / LibreSDR B220mini | **Pin the serial** of the unit that transmits |
| USIM | **sysmoISIM-SJA5** | **Read the trap below** |
| Card reader | PC/SC CCID (Identiv SCR35xx etc.) | `pcscd` |
| UE ① modem | Quectel **RM520N-GL** + carrier board | USB, `2c7c:0801` |
| UE ② real handset | Galaxy S22+ (SM-S9060), **root required** | To control it inside the shield box |
| Shield box | TOJOIN MS3020-A | 4 SMA feed-throughs, filter panel |
| Attenuators | 30 dB · 40 dB SMA | Transmit path |
| Terminators | 50 Ω SMA | Every unused port |
| USB-C Ethernet adapter | RTL8153 family | Wired adb to the handset in the shield box |
| Coax cables | SMA | Longer means more loss. Record the lengths |

### 🔴 The USIM trap — this is where we were stuck the longest

**AliExpress "LTE Blank USIM" cards and the like will not work.** The listing says
`Compatible: 4G FDD LTE, WCDMA and GSM`, but the actual card is **2G GSM only**.
There is no `EF.DIR`, no AID and no `ADF.USIM` — only `DF_GSM(7F20)`. Finding the ADM key doesn't help,
because the USIM application physically isn't there. We didn't know this, and only found out after
using up a card chasing the ADM key.

**Telling whether a card is a USIM takes one minute. Do this before chasing ADM.**

```bash
sudo ~/.venv/bin/python3 pySim-read.py -p0 | head -20
# You must see "Autodetected card type" and ADF.USIM. If not, throw that card away.
```

**The proper cards came from Europe.** We ordered the **sysmoISIM-SJA5** from sysmocom in Germany.

- Shop: <https://shop.sysmocom.de/SIM/Cards/>
- **The product name must include `with ADM keys`.** Without the ADM key you can't write to the card;
  sysmocom sends **ADM1 by e-mail** for each order
- Pick the **regular card, not MFF2 (solder type)**
- The only difference between 9FV and S17 is who computes the SUCI. Open5GS defaults to the null scheme,
  so **9FV is enough**, and S17 is often out of stock
- Shipping takes a while. **Order first, so you aren't waiting for cards with the whole network already built.**
  That is exactly how our work once stalled

Full notes: [docs/sim-cards.md](docs/sim-cards.md).

## 1. Host prerequisites

```bash
sudo apt update
sudo apt install -y docker.io docker-compose-v2 git python3-pip \
                    pcscd pcsc-tools android-tools-adb nmap avahi-utils \
                    uhd-host python3-uhd zstd
sudo usermod -aG docker "$USER"          # log in again afterwards
sudo uhd_images_downloader               # UHD firmware/FPGA
sudo systemctl enable --now pcscd
python3 -m venv ~/.venv && ~/.venv/bin/pip install pyscard
```

**Get ModemManager out of the way.** Left alone, it grabs the modem's AT port and kills the QMI session.
The symptom is "it works, then drops", which makes the cause hard to find.

```bash
sudo systemctl mask ModemManager          # or exclude just that device via udev
```

**Verify** — `docker ps` runs without a permission error and `uhd_find_devices` sees the SDR.

> `python3-uhd` is installed for the system Python version. `import uhd` does not work inside `~/.venv`.
> Run the measurement tool (`tools/leakscan.py`) with **the system Python**, e.g. `/usr/bin/python3.12`.

## 2. Clone this repository and upstream

The core and IMS containers use the upstream project's compose files. Our configs are the **source of truth**;
the upstream clone is the **deployment target**.

```bash
git clone <this repository> ~/work/private5g
git clone https://github.com/herlesupreeth/docker_open5gs.git /path/to/docker_open5gs
git -C /path/to/docker_open5gs checkout 1f3bcf7

ln -s /path/to/docker_open5gs ~/work/private5g/upstream
```

**A symlink is all it takes.** You don't need to copy our directory layout — the scripts look for the
`upstream` link first. (You can also set it with the `UPSTREAM_DIR` environment variable.)

**Don't touch** the upstream clone. Edits made there are overwritten by the next deploy.

**Verify** — `./bin/deploy-configs.sh --check` does not complain that the upstream clone can't be found.

## 3. Container images

Pulling from ghcr.io is the normal route, but upstream may move or delete tags.
**In case they can't be found online, the exact images we ran are attached to this repository's release.**
This repository alone is enough to restore everything.

```bash
./bin/load-images.sh            # downloads release images-v1, checks checksums, then docker load
```

11 images, 4.0 GB compressed in total. **Both the local tags compose uses and the ghcr tags** are included.

**Verify** — `docker images | grep docker_open5gs` shows both `latest` and `master`.

## 4. Fill in the secrets

Real keys and host-specific values come from **this one file** only. The repository holds just the template.

```bash
cp configs/secrets/lab.env.example configs/secrets/lab.env
chmod 600 configs/secrets/lab.env
$EDITOR configs/secrets/lab.env
```

| Value | Where it comes from |
|---|---|
| `DOCKER_HOST_IP` | The host's LAN address (`ip -br addr`) |
| `B210_SERIAL` | `serial:` from `uhd_find_devices`. **The one unit that will transmit** |
| `PHONE_IP` | A static address for the handset in the shield box |
| `UE*_KI`, `UE*_OPC` | Values from the card supplier (sysmocom e-mail/CSV) |
| `UE3_ADM1`, `UE3_ICCID` | Used when programming the card |

**Verify** — `./bin/deploy-configs.sh` does not report unfilled tokens.
If something is empty, it **names what is missing and stops.**

## 5. Deploy configs · start the core · create subscribers

```bash
cd ~/work/private5g
./bin/deploy-configs.sh        # render templates + deploy into the upstream tree
./bin/core-ctl.sh START        # waits until NFs are 5/5
./bin/provision-subscribers.sh # "creates" 2 APNs + 3 subscribers
./bin/provision-subscribers.sh --check
```

`provision-subscribers.sh` **creates rather than restores a dump.** On an empty database it builds the APNs
(`internet`, `ims`) and the subscribers from the template
[`configs/db/subscriber.template.json`](configs/db/subscriber.template.json), reading values from `lab.env`.
It is idempotent, so running it repeatedly doesn't pile up duplicates.

**Verify** — `--check` reports 3 subscriber rows in mongo and 3 rows each in PyHSS `auc`/`subscriber`/`ims_subscriber`.

## 6. Programming the USIM

### 6.1 Reading what the supplier sent

sysmocom sends a card list per order, as CSV or e-mail. One line is one card, and we only need four fields.

| Field | Example | Used for |
|---|---|---|
| ICCID | `894944…` 19 digits | Card identity. Cannot be changed |
| **ADM1** | 8 digits | **Write permission.** Without it you can write nothing |
| **Ki** | 32 hex digits | Authentication key. Card and HSS must match |
| **OPc** | 32 hex digits | Operator variant |

The rest (PIN1/PUK1/PIN2/PUK2 and the nine KIC/KID/KIK values) are for OTA and unused in our lab.
These values **never go into the repository.** Keep them only in `configs/secrets/lab.env`.

> **ADM1 has a limited number of retries.** Enter wrong values repeatedly and the card locks permanently.
> We lost a different card that way. **Never guess.**

### 6.2 Check the reader and the card

```bash
sudo systemctl start pcscd
sudo pcsc_scan -r                     # is the reader visible?
```

Get pySim.

```bash
git clone https://gitea.osmocom.org/sim-card/pysim.git ~/work/pysim
cd ~/work/pysim && ~/.venv/bin/pip install -r requirements.txt
```

**Always read before you write.** This one read tells you both "is it a USIM?" and "is ADM1 right?".

```bash
sudo ~/.venv/bin/python3 pySim-read.py -p0 | head -25
```

- `Autodetected card type: sysmoISIM-SJA5` → a card we know
- Further down you must see `ISIM Service Table` and `ADF.USIM`. **If not, the card can't be used** (section 0)
- If `Service 122/123` (5GS) is present, 5G SA is possible

Check ADM1 in pySim-shell, **using the proper command only** —
`apdu --raw` returns non-standard responses and still burns down the retry counter.

```bash
sudo ~/.venv/bin/python3 pySim-shell.py -p0
# (inside the shell)
verify_adm <ADM1>        # no error means it passed. If wrong, it tells you "N tries left"
exit
```

### 6.3 Writing

Subscriber 3 (the handset in the shield box) as the example. Values come from `lab.env`.

```bash
cd ~/work/pysim
set -a; source ~/work/private5g/configs/secrets/lab.env; set +a

sudo ~/.venv/bin/python3 pySim-prog.py -p0 -t sysmoISIM-SJA5 -a "$UE3_ADM1" \
  -x 001 -y 01 --mnclen 2 -n P5G \
  -i "$UE3_IMSI" -k "$UE3_KI" -o "$UE3_OPC" \
  -M e1ffffffffffffffffffffffff06815384090067ffffffffff000000 \
  --msisdn 821099994533 \
  --ims-hdomain ims.mnc001.mcc001.3gppnetwork.org \
  --impi "$UE3_IMSI@ims.mnc001.mcc001.3gppnetwork.org" \
  --impu "sip:$UE3_IMSI@ims.mnc001.mcc001.3gppnetwork.org"
```

What each argument means, and its traps:

| Argument | Meaning | Watch out |
|---|---|---|
| `-t sysmoISIM-SJA5` | Card type | Ki lives in a **card-specific file**, so the type must be right |
| `-x 001 -y 01 --mnclen 2` | MCC/MNC and MNC length | Also sets the MNC length in `EF.AD` |
| `-n P5G` | Service provider name (SPN) | Shown in the handset's status bar |
| `-i / -k / -o` | IMSI / Ki / OPc | **Must match what you put in the HSS** |
| `-M …` | Preserve the original EF.SMSP | Omit it and pySim's default SMSC (+1555…) overwrites it. Our SMSC is SIP-only and has no E.164 number |
| `--ims-hdomain/--impi/--impu` | ISIM identity | Required for VoNR · IMS |
| (ICCID) | — | **Cannot be written on this card type.** It just warns and moves on; the factory value stays |

> **Don't make clones (two cards with the same IMSI).** The core sees one subscriber, so whichever attaches
> later pushes the earlier one off. Two handsets need two subscribers.

### 6.4 Checking what was written

Start with what can be read back.

```bash
sudo ~/.venv/bin/python3 pySim-read.py -p0 | grep -iE 'ICCID|^IMSI|SPN|PLMNwAcT|Home Network Domain|IMS private|IMS public'
```

Expected:

```
ICCID: 894944…                 (factory value, unchanged)
IMSI:  001011234567897
SPN:   P5G
PLMNwAcT: 00f110ffff           ← MCC 001 / MNC 01
Home Network Domain Name: ims.mnc001.mcc001.3gppnetwork.org
IMS private user identity: 001011234567897@ims…
IMS public user identity:  sip:001011234567897@ims…
```

### 6.5 Checking that Ki really went in — the only way

**Ki cannot be read from the card.** So the only check is to make the card authenticate.
It is far faster, and the cause is far clearer, than plugging it into a handset and seeing "it won't attach".

① Compute the expected values for an arbitrary RAND and SQN.

```bash
cd ~/work/private5g
set -a; source configs/secrets/lab.env; set +a
python3 - <<'PY'
import os, sys
sys.path.insert(0, 'tools')
from milenage import f1, f2345, xor
ki, opc = bytes.fromhex(os.environ['UE3_KI']), bytes.fromhex(os.environ['UE3_OPC'])
rand = bytes.fromhex('00112233445566778899aabbccddeeff')
sqn, amf = bytes.fromhex('000000000020'), bytes.fromhex('8000')   # SQN 32
maca, _ = f1(ki, opc, rand, sqn, amf)
res, ck, ik, ak, _ = f2345(ki, opc, rand)
print('RAND', rand.hex())
print('AUTN', (xor(sqn, ak) + amf + maca).hex())
print('expected RES', res.hex(), '\nexpected CK ', ck.hex(), '\nexpected IK ', ik.hex())
PY
```

② Feed them to the card.

```bash
cd ~/work/pysim
printf 'select ADF.USIM\nauthenticate <RAND> <AUTN>\n' > /tmp/auth.script
sudo ~/.venv/bin/python3 pySim-shell.py -p0 --script /tmp/auth.script
```

③ If the `res`/`ck`/`ik` the card returns **match the computed values, Ki and OPc went in correctly.**

```json
{"successful_3g_authentication": {"res": "…", "ck": "…", "ik": "…", "kc": "…"}}
```

④ **This test advances the card's SQN.** Set the HSS-side SQN higher than that so the first attach doesn't
need a resynchronisation (AUTS) round trip.

```bash
docker exec mongo mongosh --quiet open5gs --eval \
 'db.subscribers.updateOne({imsi:"001011234567897"},{$set:{"security.sqn":NumberLong("64")}})'
curl -s -X PATCH http://127.0.0.1:8080/auc/3 -H 'Content-Type: application/json' -d '{"sqn":64}'
```

> Reading a failure — if `authenticate` returns `synchronisation_failure`, **the SQN is too low**,
> not the Ki. Raise the SQN and try again. If `res` comes back **different**, that is a Ki · OPc mismatch.

## 7. RF wiring

- B210 **TX/RX (port 1)** → 30 dB attenuation → shield-box SMA feed-through → inner antenna
- B210 **RX2 (port 2)** → attenuator → shield-box SMA feed-through → inner antenna
- **Terminate every unused port with 50 Ω.** Tighten connectors fully by hand
- **Write down** cable lengths and attenuation values. When the link budget doesn't add up later, that record is your only clue

Details: [docs/rf-cabling.md](docs/rf-cabling.md).

## 8. Base station

```bash
cd upstream && docker compose -p docker_open5gs -f srsgnb.yaml up -d
docker logs srsgnb | tail -5
```

You should see `==== gNB started ===` and `N2: Connection to AMF … completed`.

**Keep the log level at `info`.** At `warning`, RACH and RRC aren't logged and you can't even tell whether
the UE is attaching. It's `all_level` in `configs/srsran/gnb.yml.in`.

**Verify** — `docker logs srsgnb | grep -c LIBUSB` is 0 and `Operating over USB 3.` is present.

## 9. Attaching UEs

For the modem see [docs/modem.md](docs/modem.md); for the handset in the shield box see
[docs/shieldbox-phone.md](docs/shieldbox-phone.md).

The handset inside the shield box **can't be controlled through a USB feed-through** — the filter panel is
an LC low-pass, so USB 2.0 high-speed enumeration fails (it only charges). Use **wired adb over an RJ45
feed-through and a USB-C Ethernet adapter.**

Three things you must do on the handset:

```bash
adb shell settings put global captive_portal_mode 0             # removes "no internet access"
adb shell settings put global captive_portal_detection_enabled 0
adb shell settings put global mobile_data_always_on 1            # wired adb would otherwise block cellular
```

You also need an APN (`numeric=00101`, `apn=internet`, `type=default,supl,mms`).
For MMS, the `mmsc` field **must not be empty** (see troubleshooting below).

## 10. Checking it works

```bash
./bin/selftest.sh
PID=$(docker inspect -f '{{.State.Pid}}' oainrue)
sudo nsenter -t $PID -n ~/.venv/bin/python3 tools/ims_call.py 172.22.0.21 <UE IP> both 10
python3 tools/ims_sms_mt.py 172.22.0.20 821099994533 821099994531 "rebuild check"
```

Expected output of `selftest.sh` (the script reports in Korean: core start, RAN start, UE attach, tunnel
interface, user plane, external reachability, config-vs-runtime match):

```
1. 코어 기동 + 준비 대기          OK   코어 준비 완료 (NF 5/5, 10초)
2. RAN 기동 (n78)                 OK
3. UE 접속 (최대 60초)            OK   IPv4: 10.46.0.2
4. 터널 인터페이스 oaitun_ue1      OK   10.46.0.2
5. 사용자 평면 (UPF 게이트웨이)    OK   10.46.0.1 0% packet loss
5b. 외부 통신 (참고)              OK   건너뜀 — 이 UE 는 ims DNN
6. 정본 vs 런타임 설정 일치        OK   차이 0 건
=== 전체 통과 ===
```

> `selftest.sh` **brings the core and RAN down when it finishes.** If you're working with a real handset,
> bring them back up afterwards with `./bin/core-ctl.sh START` and the base station.
>
> 5b being "skipped" (건너뜀) is normal. This simulated UE is for IMS testing and uses the `ims` DNN, which isn't
> routed to the internet. Check external reachability with the modem or a real handset.

**Even if the log says "call established ✅", it wasn't if RTP is 0.** Always look at the packet counts.

---

# Troubleshooting — where we lost the most time

In order of how much time each actually ate during the build. All the cases and how we tracked them down are in
[book chapter 17, "Casebook"](https://github.com/AmesianX/local-5g-handbook/blob/master/17-%ED%8A%B8%EB%9F%AC%EB%B8%94%EC%8A%88%ED%8C%85%EC%82%AC%EB%A1%80%EC%A7%91.md), twenty-four of them.

### ① The card wasn't a USIM (days)
The symptom looked like "ADM doesn't match", so we chased the ADM key. In fact it was a 2G card with no USIM
application at all. **Check for `ADF.USIM` with `pySim-read.py` first.** It takes a minute.

### ② We transmitted from the wrong SDR (9 minutes on air + half a day)
Another SDR with an antenna was plugged into the same host, and with no serial in the config, that one got opened.
**Don't start the gNB unless `device_args` in `gnb.yml` has `serial=`.**
And if the B210 comes up as USB 2.0, suspect **the cable** before the port — a USB 2.0 Micro-B cable was the
culprit and cost us half a day.

### ③ `500 Server error on LIR select next S-CSCF` (two hours, then it came back)
It reads like an LIR failure, but **the LIR succeeded.** That message lives inside a
`t_check_status("(408)")` block in the Kamailio config — it means the next hop timed out. The real cause was
**the P-CSCF sending to the UE over TCP while our UA listened only on UDP.** In IMS each hop adds headers, the
INVITE grows past 1300 bytes, and then RFC 3261 §18.1.1 sends it over TCP.
**An IMS UE must listen on TCP.**
> Four months later the same symptom came back. A **second code path that listened only on UDP** was still in
> the tool, and it surfaced once the SDP grew. When there are two paths, only one gets fixed.

### ④ The session drops right after it comes up, every 100 seconds (srsRAN + real handset)
`docker logs srsgnb | grep "Unsupported PDU Session"` → **the srsRAN gNB doesn't support IPv4v6 PDU sessions.**
Change the subscriber's session type to **1 (IPv4)**. The handset only says "disconnected" and the core only
logs "created, deleted". **Read the logs of the layer that refused — here, the base station.**

### ⑤ Subscriber provisioning breaks on an empty database
```
IntegrityError (1452) … FOREIGN KEY (`default_apn`) REFERENCES `apn` (`apn_id`)
```
PyHSS subscribers reference an APN row. **Create the APNs first.**
`bin/provision-subscribers.sh` keeps that order. This trap appears **only on a first build**, so a lab that's
already running never sees it.

### ⑥ The real handset rejects the call (`488 Not Acceptable Here`)
Calls between simulated UEs had worked for months. A real handset demands four things:
**the AMR-WB/AMR codecs** (G.711 is rejected), **PRACK** (183 with `Require: 100rel`),
**QoS precondition declarations**, and **the SDP answer arriving in the `183`, not the `200 OK`.**
When you get a `488`, first use the `Source IP` in the P-CSCF log to see **who** rejected it.

### ⑦ After adding wired adb, cellular data won't come up
The radio log says `Re-evaluating 0 unsatisfied network requests`. The **Ethernet plugged in for control already
satisfies the default internet request**, so Android never even requests cellular.
`mobile_data_always_on=1`. **A case of the observing device changing what it observes.**

### ⑧ MMS says "no valid APN"
**If the APN's `mmsc` field is empty, the whole row is ignored** (`ApnSettings.load`). Yet
`content insert --bind mmsc:s:http://...` **breaks the parser at the colon in the value.**
We ended up driving the APN edit screen over adb, and the dialog's "OK" alone doesn't write to the DB —
you have to press **Save in the menu**. And if you resend with the same Transaction-Id or the same
Content-Location URL, the handset **treats it as a duplicate and drops it.**

### ⑨ ModemManager kills the session
Check with `mmcli -L`. Mask it or exclude the device via udev. The symptom is intermittent, which makes
you suspect the RF or the core.

### ⑩ "It worked" was a wrong record
More than once we read empty output as success. A secret scan once passed silently, too
(`--cached` for `git grep` was placed after `--`, so it was taken as a path).
**A check that confirms something is absent must separately prove that the check itself worked.** Add a second
check of a different nature, or deliberately plant something that must be caught and see that it is.

---

## Directory layout

```
private5g/
├── bin/            control scripts (run them from here only)
├── compose/        our docker compose files
├── configs/        source-of-truth configs — always edit here
│   ├── secrets/    real keys and host-specific values (untracked)
│   ├── db/         subscriber profile templates
│   └── _backup/    backups of local changes (untracked)
├── docs/           build, measurement and case notes, screenshots, and the book
└── upstream ->     docker_open5gs clone (symlink, untracked)
```

## Documents (in Korean)

| Document | Contents |
|---|---|
| [docs/REBUILD.md](docs/REBUILD.md) | Rebuild procedure (the detailed version of this README) |
| [docs/sim-cards.md](docs/sim-cards.md) | Buying, programming and verifying USIMs; the cards that didn't work |
| [docs/shieldbox-phone.md](docs/shieldbox-phone.md) | Controlling the handset inside the shield box; wired adb |
| [docs/sim-vs-real.md](docs/sim-vs-real.md) | Seven gaps between simulation and real hardware |
| [docs/mms-and-video.md](docs/mms-and-video.md) | Video calls and MMS |
| [docs/shielding-measurement.md](docs/shielding-measurement.md) | Measuring shield-box leakage |
| [docs/rf-cabling.md](docs/rf-cabling.md) | RF wiring |
| [docs/frequency-plan.md](docs/frequency-plan.md) | Frequency plan |
| [local-5g-handbook](https://github.com/AmesianX/local-5g-handbook) | The book, *Building a Local 5G Network* (separate repository, [PDF](https://github.com/AmesianX/local-5g-handbook/releases/latest/download/local-5g-handbook-ko.pdf)) |

## Not tracked

| Path | Why |
|---|---|
| `configs/secrets/lab.env` | Real keys and host-specific values |
| `configs/env/env`, `configs/oai/nr-ue.n78.rfsim.conf`, `configs/srsran/gnb.yml` | Rendered from `*.in` |
| `configs/_backup/` | Local safety copies. Contain old real keys |
| `docs/book/` | Separate repository (`AmesianX/local-5g-handbook`) |
| `upstream` | Symlink to the upstream clone |
