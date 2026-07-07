"""Tiny server for the timeline editor: serves a project folder and accepts
PUT /timeline.json so the editor's Save button persists placements.
Run: python3 serve.py [project_folder]  ->  http://localhost:8093/editor.html
(default folder: demo_project)
"""
import http.server
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
folder = sys.argv[1] if len(sys.argv) > 1 else "demo_project"
os.chdir(os.path.join(HERE, folder))


class H(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        # the editor UI is shared by all projects; always serve the repo copy
        if self.path.split("?")[0].lstrip("/") == "editor.html":
            with open(os.path.join(HERE, "editor.html"), "rb") as f:
                body = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        super().do_GET()

    def do_PUT(self):
        if self.path.lstrip("/") != "timeline.json":
            self.send_error(403)
            return
        n = int(self.headers["Content-Length"])
        body = self.rfile.read(n)
        with open("timeline.json", "wb") as f:
            f.write(body)
        self.send_response(200)
        self.end_headers()

    def do_POST(self):
        # file import: POST /upload?name=<filename> with raw bytes
        from urllib.parse import urlparse, parse_qs, unquote
        u = urlparse(self.path)
        if u.path != "/upload":
            self.send_error(403)
            return
        name = unquote(parse_qs(u.query).get("name", [""])[0])
        name = os.path.basename(name)  # no path tricks
        if not name.lower().endswith((".wav", ".aif", ".aiff", ".mp3", ".m4a",
                                      ".mp4", ".mov", ".webm", ".png", ".jpg", ".jpeg", ".gif")):
            self.send_error(400)
            return
        os.makedirs("imported", exist_ok=True)
        n = int(self.headers["Content-Length"])
        with open(os.path.join("imported", name), "wb") as f:
            f.write(self.rfile.read(n))
        self.send_response(200)
        self.end_headers()
        self.wfile.write(("imported/" + name).encode())

    def log_message(self, *a):
        pass


print("editor: http://localhost:8093/editor.html")
http.server.ThreadingHTTPServer(("127.0.0.1", 8093), H).serve_forever()
