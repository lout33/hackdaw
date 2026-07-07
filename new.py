"""Scaffold a new project folder.

Usage: python3 new.py <folder> <media files...>
       python3 new.py my_song song.wav cover.png clip.mp4

Creates <folder>/, copies the media in, and writes a starter timeline.json
with one clip per file (each on its own track, starting at 0 s).
Then: python3 serve.py <folder>  ->  http://localhost:8093/editor.html

Note: the audio renderer (timeline.py) expects 48 kHz WAV stems.
"""
import json
import os
import shutil
import sys

MEDIA = (".wav", ".aif", ".aiff", ".mp3", ".m4a",
         ".mp4", ".mov", ".webm", ".png", ".jpg", ".jpeg", ".gif")

if len(sys.argv) < 3:
    sys.exit(__doc__.strip())

folder, files = sys.argv[1], sys.argv[2:]
bad = [f for f in files if not f.lower().endswith(MEDIA)]
if bad:
    sys.exit(f"unsupported media: {', '.join(bad)}")
if os.path.exists(os.path.join(folder, "timeline.json")):
    sys.exit(f"{folder}/timeline.json already exists — refusing to overwrite")

os.makedirs(folder, exist_ok=True)
stems, clips = {}, []
for i, path in enumerate(files):
    name = os.path.splitext(os.path.basename(path))[0]
    shutil.copy(path, os.path.join(folder, os.path.basename(path)))
    stems[name] = os.path.basename(path)
    clips.append({"stem": name, "start": 0, "track": i + 1, "gain_db": 0})

timeline = {
    "vocal_anchor": 1.0,
    "n_tracks": max(len(files), 3),
    "stems": stems,
    "clips": clips,
    "track_gains": {},
    "muted_tracks": [],
}
with open(os.path.join(folder, "timeline.json"), "w") as f:
    json.dump(timeline, f, indent=1)

print(f"{folder}/ ready — {len(files)} clip(s)")
print(f"next: python3 serve.py {folder}")
