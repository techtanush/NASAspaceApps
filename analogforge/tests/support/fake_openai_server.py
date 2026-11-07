"""Local Responses protocol fixture; it is never imported by production code."""

from __future__ import annotations

import json
import threading
import time
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any


@contextmanager
def fake_responses_server(mode: str = "normal", transform_submission=None):
    requests: list[dict[str, Any]] = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            return None

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            requests.append(body)
            if mode == "timeout":
                time.sleep(0.15)
            task = None
            for item in body.get("input", []) if isinstance(body.get("input"), list) else []:
                if item.get("role") == "user":
                    try:
                        task = json.loads(item["content"]).get("task")
                    except (json.JSONDecodeError, TypeError):
                        task = None
            response = {
                "id": "resp_local_" + str(len(requests)),
                "object": "response",
                "created_at": 1700000000,
                "model": body["model"],
                "status": "completed",
                "output": [],
            }
            if mode == "refusal":
                response["output"] = [
                    {
                        "type": "message",
                        "id": "msg_refusal",
                        "role": "assistant",
                        "status": "completed",
                        "content": [{"type": "refusal", "refusal": "No task result"}],
                    }
                ]
            elif body.get("text", {}).get("format", {}).get("type") == "json_schema":
                response["output"] = [
                    {
                        "type": "message",
                        "id": "msg_ok",
                        "role": "assistant",
                        "status": "completed",
                        "content": [{"type": "output_text", "text": '{"ok":true}', "annotations": []}],
                    }
                ]
            else:
                tools = {t["name"]: t for t in body["tools"]}
                if "capability_probe" in tools:
                    name, args = "capability_probe", {"ok": True}
                elif task:
                    outputs = [i for i in body["input"] if i.get("type") == "function_call_output"]
                    if not outputs:
                        name, args = "get_run_snapshot", {"sections": ["contract"]}
                    else:
                        name, args = "submit_role_result", task["payload"]["prepared_submission"]
                        if transform_submission is not None:
                            args = transform_submission(args, task)
                else:
                    name, args = "submit_role_result", {}
                arguments = (
                    "{" if mode == "malformed" or mode == "malformed_once" and len(requests) == 1 else json.dumps(args)
                )
                response["output"] = [
                    {
                        "type": "function_call",
                        "id": "fc_" + str(len(requests)),
                        "call_id": "opaque-call-" + str(len(requests)),
                        "name": name,
                        "arguments": arguments,
                        "status": "completed",
                    }
                ]
            encoded = json.dumps(response).encode()
            try:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)
            except (BrokenPipeError, ConnectionResetError):
                self.close_connection = True

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/v1", requests
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
