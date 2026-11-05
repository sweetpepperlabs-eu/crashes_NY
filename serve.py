#!/usr/bin/env python3
"""Static file server with HTTP Range requests.

PMTiles reads the archive in small byte ranges. Python's built-in
http.server on 3.9 ignores Range and sends the whole file.
"""

import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer


class Handler(SimpleHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def end_headers(self):
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def do_GET(self):
        path = self.translate_path(self.path.split("?", 1)[0])
        range_header = self.headers.get("Range")
        if not range_header or os.path.isdir(path):
            return super().do_GET()

        try:
            file = open(path, "rb")
        except OSError:
            self.send_error(404, "File not found")
            return

        try:
            size = os.fstat(file.fileno()).st_size
            start, end = parse_range(range_header, size)
        except ValueError:
            file.close()
            self.send_error(416, "Requested Range Not Satisfiable")
            return

        length = end - start + 1
        self.send_response(206)
        self.send_header("Content-Type", self.guess_type(path))
        self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("Content-Length", str(length))
        self.end_headers()
        try:
            file.seek(start)
            remaining = length
            while remaining:
                chunk = file.read(min(64 * 1024, remaining))
                if not chunk:
                    break
                self.wfile.write(chunk)
                remaining -= len(chunk)
        finally:
            file.close()


def parse_range(header, size):
    if not header.startswith("bytes="):
        raise ValueError("unsupported range unit")
    spec = header.removeprefix("bytes=").split(",", 1)[0].strip()
    if "-" not in spec:
        raise ValueError("missing dash")
    start_text, end_text = spec.split("-", 1)
    if start_text == "":
        count = int(end_text)
        if count <= 0:
            raise ValueError("empty suffix")
        start = max(size - count, 0)
        end = size - 1
    else:
        start = int(start_text)
        end = int(end_text) if end_text else size - 1
    if start < 0 or end < start or start >= size:
        raise ValueError("range outside file")
    return start, min(end, size - 1)


def main():
    port = 8765
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"Serving http://127.0.0.1:{port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
