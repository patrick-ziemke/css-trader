from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import os
import subprocess
from scanner.database import add_position, record_sell


class TradeHandler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_POST(self):
        if self.path != "/trade":
            self.send_error(404)
            return

        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        try:
            payload = json.loads(body)
        except Exception:
            self.send_error(400, "Invalid JSON")
            return

        action = payload.get("action")
        ticker = payload.get("ticker", "").upper()
        shares = float(payload.get("shares", 0))
        price = float(payload.get("price", 0))

        if action == "buy":
            add_position(
                ticker=ticker,
                shares=shares,
                entry_price=price,
                stop=float(payload.get("stop", 0)),
                target=float(payload.get("target", 0)),
                atr=float(payload.get("atr", 0)),
                sector_etf=payload.get("sector_etf", "N/A"),
                score=int(payload.get("score", 0))
            )
            result = {"ok": True, "action": "buy", "ticker": ticker,
                      "shares": shares, "price": price}

        elif action == "sell":
            result = record_sell(
                ticker=ticker,
                shares_sold=shares,
                exit_price=price,
                exit_reason=payload.get("reason", "manual")
            )
        else:
            self.send_error(400, "Unknown action")
            return

        # Auto-push updated JSON to GitHub
        try:
            subprocess.run(["git", "add", "data/"], check=True)
            subprocess.run(
                ["git", "commit", "-m",
                 f"Trade log: {action} {ticker} {shares}@{price}"],
                check=True)
            subprocess.run(["git", "push"], check=True)
        except Exception as e:
            print(f"[api] Git push failed: {e}")

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(result).encode())

    def log_message(self, format, *args):
        print(f"[api] {format % args}")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    print(f"[api] Trade logger running on port {port}")
    HTTPServer(("0.0.0.0", port), TradeHandler).serve_forever()
