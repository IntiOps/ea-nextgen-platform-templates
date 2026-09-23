# Requests and asynchronous work — local reference component

Python 3.12, standard library only. Real persistence and transactional deduplication;
not a production HTTP server or managed cloud queue. No cloud credentials needed.

```sh
python components/application/python-request-service/app.py --database /tmp/ea-requests.sqlite --port 8080
curl -X POST http://127.0.0.1:8080/requests -H 'Content-Type: application/json' -d '{"title":"Approve a purchase"}'
curl -X POST http://127.0.0.1:8080/jobs -H 'Content-Type: application/json' -H 'Idempotency-Key: example-1' -d '{"text":"process request"}'
python components/application/python-request-service/app.py --database /tmp/ea-requests.sqlite --worker-once
```

Read returned IDs through `GET /requests/{id}` and `GET /jobs/{id}`. Repeating a job
with the same key/body returns the same job; a conflicting body returns 409.
Restarting the server preserves records in the explicitly selected SQLite file.
The worker commits its local transformation with status/result atomically.

Cloud adaptation requires a production server, authentication, PostgreSQL/managed
queue adapters, DLQ/retry and lifecycle policies. This demo does not claim those
adapters. Do not use the development HTTP server for cloud deployment. Remove only
your explicitly chosen local database when no longer needed; no auto-cleanup.
