"""Serves a project's scene pages over http: /kit/* from the project's own kit/ folder when it has one, else from the
skill's kit; everything else from the project folder. Usage: serve.py <projectDir> <port> <kitDir>"""
import http.server, os, sys, urllib.parse

ROOT, PORT, KIT = os.path.abspath(sys.argv[1]), int(sys.argv[2]), os.path.abspath(sys.argv[3])
OWN_KIT = os.path.join(ROOT, 'kit')


class H(http.server.SimpleHTTPRequestHandler):
    def translate_path(self, path):
        path = urllib.parse.unquote(urllib.parse.urlsplit(path).path)
        parts = [p for p in path.split('/') if p and p != '..']
        if parts[:1] == ['kit']:
            own = os.path.join(OWN_KIT, *parts[1:])
            return own if os.path.exists(own) else os.path.join(KIT, *parts[1:])
        return os.path.join(ROOT, *parts)

    def end_headers(self):
        self.send_header('Accept-Ranges', 'bytes'); self.send_header('Cache-Control', 'no-store'); super().end_headers()

    def do_GET(self):
        # byte ranges, which a browser needs to seek in a recording placed in a scene
        rng = self.headers.get('Range', '')
        path = self.translate_path(self.path)
        if not rng.startswith('bytes=') or not os.path.isfile(path): return super().do_GET()
        size = os.path.getsize(path); a, _, b = rng[6:].split(',')[0].partition('-')
        start = int(a) if a else max(0, size - int(b)); end = min(size - 1, int(b)) if a and b else size - 1
        if start >= size: self.send_error(416); return
        self.send_response(206); self.send_header('Content-Type', self.guess_type(path))
        self.send_header('Content-Range', f'bytes {start}-{end}/{size}'); self.send_header('Content-Length', str(end - start + 1)); self.end_headers()
        with open(path, 'rb') as f:
            f.seek(start); left = end - start + 1
            while left > 0:
                chunk = f.read(min(1 << 16, left))
                if not chunk: break
                self.wfile.write(chunk); left -= len(chunk)

    def log_message(self, *a): pass


class S(http.server.ThreadingHTTPServer):
    # several headless browsers load their pages at once; the default queue of 5 waiting connections drops some of
    # their script requests, and a page then loads without its scripts
    request_queue_size = 256
    daemon_threads = True


S(('127.0.0.1', PORT), H).serve_forever()
