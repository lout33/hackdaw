"""THE TIMELINE renderer — reads <folder>/timeline.json (same file the
web editor saves) and renders the mix with the glue recipe:
3k pocket on the instrumental, hair-of-room 0.04 on vocals, 1.6:1 master glue.

The instrumental is an ordinary clip (stem "INSTRUMENTAL") — movable and
trimmable like everything else. Muted tracks are skipped. Old-format JSONs
(no instrumental clip) still render.

Loop: edit in editor.html -> Save -> run this -> <folder>/mix.wav
Usage: .venv/bin/python timeline.py [folder] [out.wav]
"""
import json
import sys
import numpy as np
import soundfile as sf
from pedalboard import Pedalboard, PeakFilter, Compressor, Reverb

SR = 48000
BASE = (sys.argv[1].rstrip("/") + "/") if len(sys.argv) > 1 else "demo_project/"
OUT = sys.argv[2] if len(sys.argv) > 2 else "mix.wav"
AUDIO = (".wav", ".aif", ".aiff", ".mp3", ".m4a")

data = json.load(open(BASE + "timeline.json"))
anchor = data.get("vocal_anchor", 1.0)
muted = set(data.get("muted_tracks", []))

# video/image clips belong to video_render.py — this renderer is audio-only
data["clips"] = [c for c in data["clips"]
                 if data["stems"][c["stem"]].lower().endswith(AUDIO)]

needed = {c["stem"] for c in data["clips"] if c.get("track") not in muted}
stems = {}
for name, path in data["stems"].items():
    if name not in needed:
        continue
    a, sr = sf.read(BASE + path)
    assert sr == SR, path
    if a.ndim == 1:
        a = np.stack([a, a], axis=1)
    stems[name] = a.astype(np.float32)

POCKET = Pedalboard([PeakFilter(cutoff_frequency_hz=3000, gain_db=-2.0, q=0.7)])
ROOM = Pedalboard([Reverb(room_size=0.30, damping=0.5, wet_level=1, dry_level=0, width=0.9)])
GLUE = Pedalboard([Compressor(threshold_db=-14, ratio=1.6, attack_ms=30, release_ms=200)])

clips = [c for c in data["clips"] if c.get("track") not in muted]
for c in data["clips"]:
    if c.get("track") in muted:
        print(f'{c["start"]:7.2f}s  {c["stem"]}  [MUTED - skipped]')


def sliced(c):
    s = stems[c["stem"]]
    a = int(c.get("trim_start", 0) * SR)
    b = int(c["trim_end"] * SR) if "trim_end" in c else len(s)
    return s[a:b]


has_inst_clip = any(c["stem"] == "INSTRUMENTAL" for c in clips)
total = max(int(c["start"] * SR) + len(sliced(c)) for c in clips) + SR

if has_inst_clip or not data.get("instrumental"):
    full = np.zeros((total, 2), dtype=np.float32)
else:  # old format: instrumental implicit at 0
    inst, sr = sf.read(BASE + data["instrumental"])
    assert sr == SR
    full = POCKET(inst.astype(np.float32), SR)
    if len(full) < total:
        full = np.vstack([full, np.zeros((total - len(full), 2), np.float32)])

track_gains = {int(k): v for k, v in data.get("track_gains", {}).items()}
vocal_bus = np.zeros_like(full)
for c in clips:
    seg = sliced(c)
    g = 10 ** ((c.get("gain_db", 0) + track_gains.get(c.get("track"), 0)) / 20)
    i = int(c["start"] * SR)
    seg = seg[: len(full) - i]
    if c["stem"] == "INSTRUMENTAL":
        full[i:i + len(seg)] += POCKET(seg * g, SR)
    else:
        vocal_bus[i:i + len(seg)] += seg * anchor * g
    print(f'{c["start"]:7.2f}s  {c["stem"]}')

full += vocal_bus + ROOM(vocal_bus * 0.04, SR)
full = GLUE(full, SR)
full *= 10 ** (-1.0 / 20) / (np.max(np.abs(full)) + 1e-12)
sf.write(BASE + OUT, full, SR)
print(f"\n{OUT}  ({len(full)/SR:.0f} s)")
