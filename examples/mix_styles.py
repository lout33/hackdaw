"""Example: render one timeline in several mix styles.

The whole point of this project: timeline.json is plain JSON, so a "mix
preset" is just a short Python script. This one renders the same clips
through three different master-bus treatments:

  ed     dry upfront vocal, deeper instrumental pocket, tight glue
  big    modern big-pop: larger room, more glue pump, brighter master
  close  intimate: zero room, vocal hottest, softest compression

Any stem named "INSTRUMENTAL" goes to the instrumental bus; everything
else is treated as a vocal. All outputs loudness-matched to -14 LUFS
(needs ffmpeg) so the A/B is fair.

Usage: .venv/bin/python examples/mix_styles.py [folder]
Outputs: <folder>/full_mix_<style>.wav
"""
import json
import os
import subprocess
import sys

import numpy as np
import soundfile as sf
from pedalboard import Pedalboard, PeakFilter, HighShelfFilter, Compressor, Reverb

SR = 48000
BASE = (sys.argv[1].rstrip("/") + "/") if len(sys.argv) > 1 else "demo_project/"
AUDIO = (".wav", ".aif", ".aiff", ".mp3", ".m4a")

STYLES = {
    "ed":    dict(room=0.02, room_size=0.30, pocket=-3.0, vlift=1.5,
                  glue_thr=-16, glue_ratio=2.0, vpresence=1.5, mshelf=0.0),
    "big":   dict(room=0.12, room_size=0.50, pocket=-1.5, vlift=0.0,
                  glue_thr=-18, glue_ratio=2.0, vpresence=0.0, mshelf=1.5),
    "close": dict(room=0.00, room_size=0.30, pocket=-2.5, vlift=2.5,
                  glue_thr=-14, glue_ratio=1.4, vpresence=0.5, mshelf=0.0),
}

data = json.load(open(BASE + "timeline.json"))
anchor = data.get("vocal_anchor", 1.0)
muted = set(data.get("muted_tracks", []))
track_gains = {int(k): v for k, v in data.get("track_gains", {}).items()}
clips = [c for c in data["clips"]
         if c.get("track") not in muted
         and data["stems"][c["stem"]].lower().endswith(AUDIO)]

needed = {c["stem"] for c in clips}
stems = {}
for name, path in data["stems"].items():
    if name not in needed:
        continue
    a, sr = sf.read(BASE + path)
    assert sr == SR, path
    if a.ndim == 1:
        a = np.stack([a, a], axis=1)
    stems[name] = a.astype(np.float32)


def sliced(c):
    s = stems[c["stem"]]
    a = int(c.get("trim_start", 0) * SR)
    b = int(c["trim_end"] * SR) if "trim_end" in c else len(s)
    return s[a:b]


total = max(int(c["start"] * SR) + len(sliced(c)) for c in clips) + SR

# place once (style-independent): instrumental bus + vocal bus
inst_bus = np.zeros((total, 2), dtype=np.float32)
vocal_bus = np.zeros((total, 2), dtype=np.float32)
for c in clips:
    seg = sliced(c)
    g = 10 ** ((c.get("gain_db", 0) + track_gains.get(c.get("track"), 0)) / 20)
    i = int(c["start"] * SR)
    seg = seg[: total - i]
    if c["stem"] == "INSTRUMENTAL":
        inst_bus[i:i + len(seg)] += seg * g
    else:
        vocal_bus[i:i + len(seg)] += seg * anchor * g

for name, P in STYLES.items():
    inst = Pedalboard([PeakFilter(cutoff_frequency_hz=3000, gain_db=P["pocket"], q=0.7)])(inst_bus, SR)
    voc = vocal_bus * 10 ** (P["vlift"] / 20)
    if P["vpresence"]:
        voc = Pedalboard([PeakFilter(cutoff_frequency_hz=3500, gain_db=P["vpresence"], q=0.8)])(voc, SR)
    full = inst + voc
    if P["room"]:
        room = Pedalboard([Reverb(room_size=P["room_size"], damping=0.5,
                                  wet_level=1, dry_level=0, width=0.9)])
        full += room(voc * P["room"], SR)
    chain = [Compressor(threshold_db=P["glue_thr"], ratio=P["glue_ratio"],
                        attack_ms=30, release_ms=200)]
    if P["mshelf"]:
        chain.append(HighShelfFilter(cutoff_frequency_hz=9000, gain_db=P["mshelf"]))
    full = Pedalboard(chain)(full, SR)
    full *= 10 ** (-1.0 / 20) / (np.max(np.abs(full)) + 1e-12)
    raw = BASE + f"_tmp_{name}.wav"
    out = BASE + f"full_mix_{name}.wav"
    sf.write(raw, full, SR)
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", raw,
                    "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-ar", str(SR), out], check=True)
    os.remove(raw)
    print(f"full_mix_{name}.wav")
