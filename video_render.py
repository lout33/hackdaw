"""VIDEO renderer — reads <folder>/timeline.json (same file the web editor
saves) and composites the video/image clips over black with ffmpeg, muxing in
the mixed audio. The audio itself comes from timeline.py's output.

Layering: lower track number = on top (matches the editor's monitor).
Muted tracks are skipped. Gaps show black. Stills honor their trim length.

Usage:
    python3 video_render.py [folder] [--audio mix.wav] [--out final.mp4]
Defaults: folder=demo_project, audio=newest mix.wav / full_mix_*.wav in folder,
out=final_video.mp4
"""
import glob
import json
import os
import subprocess
import sys

W, H, FPS = 1920, 1080, 30
VIDEO = (".mp4", ".mov", ".webm")
IMAGE = (".png", ".jpg", ".jpeg", ".gif")

args = sys.argv[1:]
folder = args.pop(0) if args and not args[0].startswith("--") else "demo_project"
audio = out = None
while args:
    a = args.pop(0)
    if a == "--audio":
        audio = args.pop(0)
    elif a == "--out":
        out = args.pop(0)
out = out or "final_video.mp4"

data = json.load(open(os.path.join(folder, "timeline.json")))
muted = set(data.get("muted_tracks", []))
kind = lambda p: "video" if p.lower().endswith(VIDEO) else \
                 "image" if p.lower().endswith(IMAGE) else "audio"

clips = [c for c in data["clips"]
         if c.get("track") not in muted and kind(data["stems"][c["stem"]]) != "audio"]
if not clips:
    sys.exit("no video/image clips on unmuted tracks — nothing to render")

if audio is None:
    mixes = sorted(glob.glob(os.path.join(folder, "full_mix_*.wav")) +
                   glob.glob(os.path.join(folder, "mix.wav")), key=os.path.getmtime)
    audio = os.path.basename(mixes[-1]) if mixes else None
    print(f"audio: {audio or 'NONE (silent render)'}")


def probe_dur(path):
    r = subprocess.run(["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                        "-of", "csv=p=0", path], capture_output=True, text=True)
    return float(r.stdout.strip())


def span(c):
    p = os.path.join(folder, data["stems"][c["stem"]])
    a = c.get("trim_start", 0)
    if "trim_end" in c:
        b = c["trim_end"]
    elif kind(p) == "image":
        b = a + 5
    else:
        b = probe_dur(p)
    return p, a, b


spans = [span(c) for c in clips]
total = max(c["start"] + (b - a) for c, (p, a, b) in zip(clips, spans))
if audio:
    total = max(total, probe_dur(os.path.join(folder, audio)))

# inputs + per-clip filter chains
cmd = ["ffmpeg", "-y"]
fparts = [f"color=c=black:s={W}x{H}:r={FPS}:d={total:.3f}[base]"]
for i, (c, (path, a, b)) in enumerate(zip(clips, spans)):
    if kind(path) == "image":
        cmd += ["-loop", "1", "-t", f"{b - a:.3f}", "-i", path]
        trim = ""
    else:
        cmd += ["-i", path]
        trim = f"trim=start={a:.3f}:end={b:.3f},"
    fparts.append(
        f"[{i}:v]{trim}setpts=PTS-STARTPTS,fps={FPS},"
        f"scale={W}:{H}:force_original_aspect_ratio=decrease,"
        f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,"
        f"setpts=PTS+{c['start']:.3f}/TB[v{i}]")

# overlay bottom-up: higher track first, track 0 last => track 0 wins (top lane on top)
order = sorted(range(len(clips)), key=lambda i: -clips[i]["track"])
cur = "base"
for n, i in enumerate(order):
    c = clips[i]
    _, a, b = spans[i]
    nxt = "vout" if n == len(order) - 1 else f"b{n}"
    fparts.append(f"[{cur}][v{i}]overlay=eof_action=pass:"
                  f"enable='between(t,{c['start']:.3f},{c['start'] + b - a:.3f})'[{nxt}]")
    cur = nxt

if audio:
    cmd += ["-i", os.path.join(folder, audio)]
cmd += ["-filter_complex", ";".join(fparts), "-map", "[vout]"]
if audio:
    cmd += ["-map", f"{len(clips)}:a", "-c:a", "aac", "-b:a", "320k"]
cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "medium", "-crf", "18",
        "-t", f"{total:.3f}", os.path.join(folder, out)]

for c, (p, a, b) in zip(clips, spans):
    print(f'{c["start"]:7.2f}s  track {c["track"]}  {os.path.basename(p)}  [{a:.2f}→{b:.2f}]')
print("\nffmpeg…")
subprocess.run(cmd, check=True)
print(f"\n{os.path.join(folder, out)}  ({total:.1f} s)")
