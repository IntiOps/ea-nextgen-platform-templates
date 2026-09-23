import json
import os


def handler(event, context):
    return {"statusCode": 200, "headers": {"content-type": "application/json"},
            "body": json.dumps({"status": "ok", "revision": os.environ["SOURCE_REVISION"]})}
