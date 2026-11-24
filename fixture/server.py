"""Deterministic, CPU-only OpenAI-compatible HTTP fixture for integration tests."""

import argparse
import json
import threading
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

MODEL = "ops-fixture"
MAX_BODY = 128 * 1024
COUNTS: Counter[int] = Counter()
LOCK = threading.Lock()
USAGE = {"prompt_tokens": 4, "completion_tokens": 2, "total_tokens": 6}
EXTRACTION_FIXTURES = {
    "Invoice": {"invoice_id": "OPS-1", "supplier": "Fixture",
                "total_minor": 500, "currency": "USD", "due_date": None},
    "ClinicalNote": {"visit_date": None, "symptom": None,
                     "documented_finding": None, "follow_up_days": None},
    "Contract": {"contract_id": None, "counterparty": None, "effective_date": None,
                 "notice_days": None, "jurisdiction": None},
    "SupportToolCall": {"tool": None, "arguments": {"ticket_id": None, "priority": None}},
}


def completion_text(payload):
    response_format = payload.get("response_format")
    if isinstance(response_format, dict):
        if response_format.get("type") == "json_object":
            return json.dumps({"category": "other", "tool": "record_request",
                               "summary": "Fixture workflow", "reference": None,
                               "amount_cents": None, "currency": None})
        if response_format.get("type") == "json_schema":
            try:
                title = response_format["json_schema"]["schema"]["title"]
                return json.dumps(EXTRACTION_FIXTURES[title])
            except (KeyError, TypeError):
                raise ValueError("Unsupported fixture schema") from None
    return "ops fixture"


class Handler(BaseHTTPRequestHandler):
    def send_body(self, status, body, content_type):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, status, payload):
        self.send_body(status, json.dumps(payload).encode(), "application/json")

    def do_GET(self):
        if self.path == "/health":
            self.send_json(200, {"status": "ok"})
        elif self.path == "/v1/models":
            self.send_json(200, {"object": "list", "data": [{"id": MODEL, "object": "model"}]})
        elif self.path == "/metrics":
            with LOCK:
                metrics = ['# TYPE ops_fixture_requests_total counter']
                metrics.extend(
                    f'ops_fixture_requests_total{{status="{status}"}} {count}'
                    for status, count in sorted(COUNTS.items())
                )
            self.send_body(200, ("\n".join(metrics) + "\n").encode(), "text/plain; version=0.0.4")
        else:
            self.send_error(404)

    def chat_error(self, status, message):
        with LOCK:
            COUNTS[status] += 1
        self.send_json(status, {"error": {"message": message, "type": "invalid_request_error"}})

    def do_POST(self):
        if self.path != "/v1/chat/completions":
            self.send_error(404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= MAX_BODY:
                self.chat_error(413, "Expected a bounded request with Content-Length")
                return
            payload = json.loads(self.rfile.read(length))
        except (ValueError, UnicodeError):
            self.chat_error(400, "Invalid JSON")
            return
        if not isinstance(payload, dict) or not isinstance(payload.get("messages"), list):
            self.chat_error(400, "Expected messages")
            return
        if payload.get("model") != MODEL:
            self.chat_error(404, "Model not found")
            return

        try:
            content = completion_text(payload)
        except ValueError as exc:
            self.chat_error(400, str(exc))
            return
        with LOCK:
            COUNTS[200] += 1
        message = {"role": "assistant", "content": content}
        common = {"id": "chatcmpl-ops-fixture", "created": 0, "model": MODEL}
        if payload.get("stream") is True:
            def chunk(choices, **fields):
                return dict(common, object="chat.completion.chunk", choices=choices, **fields)

            packets = [
                chunk([{"index": 0, "delta": message, "finish_reason": None}]),
                chunk([{"index": 0, "delta": {}, "finish_reason": "stop"}]),
            ]
            options = payload.get("stream_options")
            if isinstance(options, dict) and options.get("include_usage"):
                packets.append(chunk([], usage=USAGE))
            body = "".join(f"data: {json.dumps(packet)}\n\n" for packet in packets)
            self.send_body(200, (body + "data: [DONE]\n\n").encode(), "text/event-stream")
        else:
            self.send_json(200, dict(
                common, object="chat.completion", usage=USAGE,
                choices=[{"index": 0, "message": message, "finish_reason": "stop"}],
            ))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()
    with ThreadingHTTPServer((args.host, args.port), Handler) as server:
        print(server.server_port, flush=True)
        server.serve_forever()


if __name__ == "__main__":
    main()
