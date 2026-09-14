import json
from http.server import BaseHTTPRequestHandler, HTTPServer

GROUPS: set[str] = set()


class Handler(BaseHTTPRequestHandler):
    
    def _send(self, status: int, body: dict | None ) -> None:
        self.send_response(status)
        if body:
            payload = json.dumps(body).encode()
            self.send_header("Content-Type", "application/json")
        else:
            payload = b""
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        if payload:
            self.wfile.write(payload)
            
    def _body(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if length == 0:
            return {}
        return json.loads(self.rfile.read(length))
    
    def do_GET(self) -> None:
        parts = self.path.strip("/").split("/")
        if len(parts) == 3 and parts[0] == "v1" and parts[1] == "group":
            group_id = parts[2]
            if group_id in GROUPS:
                self._send(status=200, body={"groupId": group_id})
            else:
                self._send(status=404, body=None)
        else:
            self._send(status=400, body=None)

    def do_POST(self) -> None:
        if self.path != "/v1/group/":
            self._send(status=404, body=None)
            return
        group_id = self._body().get("groupId")
        if not group_id:
            self._send(400, None)
            return
        if group_id in GROUPS:
            self._send(400, None)
            return
        GROUPS.add(group_id)
        self._send(201, None)
        
    def do_DELETE(self) -> None:
        if self.path != "/v1/group/":
            self._send(404, None)
            return
        group_id = self._body().get("groupId")
        if group_id not in GROUPS or not group_id:
            self._send(404, None)
            return
        GROUPS.discard(group_id)
        self._send(200, None)
    
    def log_message(self, format: str, *args) -> None:
        print(f"[mock-node] {self.command} {self.path}")

if __name__ == "__main__":
    print(f"[mock-node] listening on :{8000}")
    HTTPServer(("0.0.0.0",8000), Handler).serve_forever()