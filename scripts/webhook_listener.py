import http.server
import json
import hmac
import hashlib
import sys

PORT = 9000
SECRET = "mvp-secret-key-change-me-in-prod"

class WebhookHandler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        # 1. Read Headers
        content_len = int(self.headers.get('Content-Length', 0))
        signature_header = self.headers.get('X-CliniSandbox-Signature')
        
        # 2. Read Body
        body = self.rfile.read(content_len)
        
        print("\n[+] Webhook Received!")
        print(f"    - URL: {self.path}")
        print(f"    - Signature Header: {signature_header}")
        
        # 3. Verify Signature
        # We must verify the RAW bytes, not parsed JSON
        expected_sig = hmac.new(
            SECRET.encode('utf-8'), 
            body, # Raw body bytes
            hashlib.sha256
        ).hexdigest()
        
        print(f"    - Computed Signature: {expected_sig}")
        
        if hmac.compare_digest(expected_sig, signature_header or ""):
            print("    - ✅ SIGNATURE MATCH: Trustworthy Payload")
            try:
                data = json.loads(body)
                print(f"    - Payload: {json.dumps(data, indent=2)}")
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"Webhook Accepted")
            except:
                print("    - ❌ Invalid JSON")
                self.send_response(400)
                self.end_headers()
        else:
            print("    - ❌ SIGNATURE MISMATCH: POTENTIAL ATTACK")
            self.send_response(403)
            self.end_headers()

if __name__ == "__main__":
    server = http.server.HTTPServer(('0.0.0.0', PORT), WebhookHandler)
    print(f"[*] Hospital Chatbot Listener running on port {PORT}...")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping listener.")
        server.server_close()