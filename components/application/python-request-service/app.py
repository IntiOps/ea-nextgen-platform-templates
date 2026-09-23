import argparse
from wsgiref.simple_server import make_server
import json
from service import Conflict, Store


def application(store):
    def handle(env, start_response):
        status, result = '200 OK', None
        path, method = env.get('PATH_INFO', ''), env.get('REQUEST_METHOD', '')
        try:
            if method == 'GET' and path == '/health':
                result = {'status': 'ok'}
            elif method == 'POST' and path in ('/requests', '/jobs'):
                length = int(env.get('CONTENT_LENGTH') or 0)
                if not 0 < length <= 8192:
                    raise ValueError('body must contain 1–8192 bytes')
                body = json.loads(env['wsgi.input'].read(length))
                if not isinstance(body, dict):
                    raise ValueError('JSON object required')
                result = (store.create_request(body.get('title')) if path == '/requests' else
                          store.enqueue(env.get('HTTP_IDEMPOTENCY_KEY'), body.get('text')))
                status = '201 Created'
            elif method == 'GET' and path.startswith('/requests/'):
                result = store.get_request(path.removeprefix('/requests/'))
            elif method == 'GET' and path.startswith('/jobs/'):
                result = store.get_job(path.removeprefix('/jobs/'))
            if result is None:
                status, result = '404 Not Found', {'error': 'not found'}
        except Conflict as exc:
            status, result = '409 Conflict', {'error': str(exc)}
        except (ValueError, UnicodeError):
            status, result = '400 Bad Request', {'error': 'invalid request'}
        output = json.dumps(result).encode()
        start_response(status, [('Content-Type', 'application/json'), ('Content-Length', str(len(output)))])
        return [output]
    return handle


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--database', required=True)
    parser.add_argument('--port', type=int, default=8080)
    parser.add_argument('--worker-once', action='store_true')
    args = parser.parse_args()
    store = Store(args.database)
    if args.worker_once:
        print(json.dumps(store.work_once()))
    else:
        # Development server intentionally binds localhost, not an exposed cloud endpoint.
        with make_server('127.0.0.1', args.port, application(store)) as server:
            server.serve_forever()
