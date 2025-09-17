from __future__ import annotations

import json
import logging
import os
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Union

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

APP = FastAPI(title="Fluent Bit Demo Receiver")

# Environment configuration
LOG_ROOT = Path(os.getenv("LOG_ROOT", "/logs"))
APP_LOG_PATH = Path(os.getenv("APP_LOG_PATH", str(LOG_ROOT / "app" / "app.log")))
RECEIVED_LOG_PATH = Path(
    os.getenv("RECEIVED_LOG_PATH", str(LOG_ROOT / "received" / "ingest.log"))
)

# Ensure directories exist
(APP_LOG_PATH.parent).mkdir(parents=True, exist_ok=True)
(RECEIVED_LOG_PATH.parent).mkdir(parents=True, exist_ok=True)

# Configure application logger to write to file and stdout
app_logger = logging.getLogger("app")
app_logger.setLevel(logging.INFO)
if not app_logger.handlers:
    # File handler
    fh = logging.FileHandler(APP_LOG_PATH)
    fh.setLevel(logging.INFO)
    fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    app_logger.addHandler(fh)

    # Stdout handler
    sh = logging.StreamHandler()
    sh.setLevel(logging.INFO)
    sh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    app_logger.addHandler(sh)

# Background thread to simulate app log generation
_stop_bg = threading.Event()


def _bg_logger() -> None:
    i = 0
    while not _stop_bg.is_set():
        i += 1
        # Emit a simple structured JSON-like message as a single line
        msg = json.dumps(
            {
                "event": "heartbeat",
                "counter": i,
                "component": "demo-app",
            }
        )
        app_logger.info(msg)
        _stop_bg.wait(5.0)


_bg_thread: threading.Thread | None = None


@APP.on_event("startup")
async def on_startup() -> None:
    global _bg_thread
    _bg_thread = threading.Thread(target=_bg_logger, name="bg-logger", daemon=True)
    _bg_thread.start()
    app_logger.info("App startup complete; background logger thread started")


@APP.on_event("shutdown")
async def on_shutdown() -> None:
    _stop_bg.set()
    app_logger.info("App shutting down; stopping background logger")


@APP.get("/")
async def root() -> Dict[str, Any]:
    return {"status": "ok"}


@APP.get("/test-logs")
async def test_logs() -> Dict[str, Any]:
    """Test endpoint that generates various log messages for Fluent Bit to capture"""
    import random

    # Generate some sample log messages
    user_id = random.randint(1000, 9999)
    action = random.choice(
        ["login", "logout", "view_profile", "update_settings", "search"]
    )

    app_logger.info(f"User {user_id} performed action: {action}")
    app_logger.info(f"Processing request from IP: 192.168.1.{random.randint(1, 254)}")
    app_logger.warning(
        f"Rate limit check for user {user_id}: {random.randint(1, 10)}/10 requests"
    )

    if random.choice([True, False]):
        app_logger.error(
            f"Simulated error: Database connection timeout for user {user_id}"
        )

    app_logger.info(f"Request completed successfully for action: {action}")

    return {
        "status": "success",
        "message": f"Generated logs for user {user_id} action {action}",
        "logs_generated": 4 if random.choice([True, False]) else 5,
    }


@APP.get("/audit-logs")
async def audit_logs() -> Dict[str, Any]:
    """Generate a mix of [audit]-tagged and non-audit logs.

    This endpoint is used to demonstrate Fluent Bit filtering, where only lines
    containing the literal token "[audit]" should be forwarded downstream.
    """
    import random

    user_id = random.randint(1000, 9999)
    resource = random.choice(["profile", "settings", "billing", "projects"])

    # Audit logs (should be forwarded)
    app_logger.info(f"[audit] user={user_id} action=read resource={resource}")
    app_logger.info(
        f"[audit] user={user_id} action=update resource={resource} result=success"
    )

    app_logger.info("bumindu")
    app_logger.info("[audit] bumindu")

    # Non-audit logs (should be dropped)
    app_logger.info(f"User {user_id} viewed the {resource} page")
    app_logger.warning(f"Cache miss for user {user_id} {resource}")

    return {
        "status": "success",
        "message": "Emitted [audit] and non-audit logs",
        "audit_logs": 2,
        "non_audit_logs": 2,
    }


def _normalize_records(
    payload: Union[Dict[str, Any], List[Any]],
) -> List[Dict[str, Any]]:
    # Fluent Bit HTTP output can send batches; accept object or list
    if isinstance(payload, list):
        records: List[Dict[str, Any]] = []
        for item in payload:
            if isinstance(item, dict):
                records.append(item)
            else:
                records.append({"message": str(item)})
        return records
    elif isinstance(payload, dict):
        return [payload]
    else:
        return [{"message": str(payload)}]


@APP.post("/ingest")
async def ingest(request: Request) -> JSONResponse:
    try:
        body = await request.body()
        # Best-effort JSON parsing; if not JSON, wrap as text
        try:
            data = json.loads(body.decode("utf-8"))
        except Exception:
            data = {"message": body.decode("utf-8", errors="replace")}

        records = _normalize_records(data)

        # Append to received log file and also print to stdout
        with open(RECEIVED_LOG_PATH, "a", encoding="utf-8") as f:
            for rec in records:
                line = json.dumps(rec, ensure_ascii=False)
                print(f"INGEST: {line}")
                f.write(line + "\n")

        return JSONResponse({"status": "received", "count": len(records)})
    except Exception as e:
        app_logger.exception("Error in /ingest: %s", e)
        return JSONResponse({"status": "error", "detail": str(e)}, status_code=500)
