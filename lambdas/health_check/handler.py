"""Health check Lambda — validates the deployment pipeline."""

import json
import os
from datetime import datetime, timezone


def handler(event, context):
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({
            "status": "healthy",
            "component": "porth-common-components",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "region": os.environ.get("AWS_REGION", "unknown"),
        }),
    }
