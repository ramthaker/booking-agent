"""Zero-dependency localhost demo UI. Not suitable as an Internet-facing production server."""
from __future__ import annotations
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from .booking import BookingStore, Concierge, run_slot_race
from .mr_review import ReviewSupervisor

HTML = (Path(__file__).resolve().parent.parent / 'web' / 'index.html')


def serve(host='127.0.0.1', port=8765):
    concierge = Concierge(BookingStore())
    reviewer = ReviewSupervisor()

    class Handler(BaseHTTPRequestHandler):
        def _send(self, status, obj, content_type='application/json; charset=utf-8'):
            payload = obj if isinstance(obj, bytes) else json.dumps(obj).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(payload)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(payload)

        def do_GET(self):
            if self.path == '/':
                return self._send(200, HTML.read_bytes(), 'text/html; charset=utf-8')
            if self.path == '/api/metrics':
                return self._send(200, concierge.store.summary())
            return self._send(404, {'error':'Not found'})

        def do_POST(self):
            if self.path not in ('/api/sms', '/api/race', '/api/mr'):
                return self._send(404, {'error':'Not found'})
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if length < 2 or length > 8192:
                    return self._send(413, {'error':'Invalid body size'})
                body = json.loads(self.rfile.read(length))
                if self.path == '/api/sms':
                    return self._send(200, concierge.on_message(body['customer'], body['text'], body['message_id']).to_dict())
                if self.path == '/api/race':
                    return self._send(200, run_slot_race(20))
                if self.path == '/api/mr':
                    return self._send(200, reviewer.review(body.get('scenario','risky')))
            except (ValueError, KeyError, TypeError) as exc:
                return self._send(400, {'error':str(exc)[:160]})
            except Exception:
                return self._send(500, {'error':'Demo operation failed'})

        def log_message(self, fmt, *args):
            print('localhost demo:', fmt % args)

    httpd = ThreadingHTTPServer((host, port), Handler)
    print(f'Open http://{host}:{port} - local demo only; press Ctrl+C to stop.')
    try:
        httpd.serve_forever()
    finally:
        httpd.server_close()


if __name__ == '__main__':
    serve()
