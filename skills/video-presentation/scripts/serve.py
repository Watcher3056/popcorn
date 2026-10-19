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
        self.send_header('Cache-Control', 'no-store'); super().end_headers()

    def log_message(self, *a): pass


class S(http.server.ThreadingHTTPServer):
    # several headless browsers load their pages at once; the default queue of 5 waiting connections drops some of
    # their script requests, and a page then loads without its scripts
    request_queue_size = 256
    daemon_threads = True


S(('127.0.0.1', PORT), H).serve_forever()
