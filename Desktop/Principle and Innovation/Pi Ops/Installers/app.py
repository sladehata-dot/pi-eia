#!/usr/bin/env python3
"""
Pi Ops – Installer Onboarding  |  Local Web App
================================================
Run:  python app.py
Open: http://localhost:3000
"""

import sys
import io
import json
import base64
import queue
import threading
import webbrowser
from pathlib import Path
from flask import Flask, render_template, request, jsonify, Response, stream_with_context, send_file

# ── Import business logic from installer_onboarding.py ────────────────────────
sys.path.insert(0, str(Path(__file__).parent))
import installer_onboarding as onb

app = Flask(__name__)

# ── Config ─────────────────────────────────────────────────────────────────────
# SERVER_URL is the base URL installers will use to open the agreement.
# For local use keep localhost:3000.
# To send to external installers, replace with your public domain, e.g.:
#   SERVER_URL = "https://principleinnovation.tech"
SERVER_URL = "http://localhost:3000"

AGREEMENT_HTML    = Path(__file__).parent / "Pi_Primary_Electrical_Installation_Agreement_DIGITAL.html"
SMTP_CONFIG_FILE  = Path(__file__).parent / ".smtp_config.json"   # persists across restarts

# ── Mail provider presets (mirrors the GUI) ────────────────────────────────────
MAIL_PRESETS = {
    "Principle Innovation (.tech)": ("mail.principleinnovation.tech", 465),
    "Gmail (smtp.gmail.com)":       ("smtp.gmail.com",               587),
    "Outlook / Microsoft 365":      ("smtp.office365.com",           587),
    "Zoho Mail":                    ("smtp.zoho.com.au",             465),
}

# ── SMTP config cache — persisted to disk so it survives server restarts ───────
def _load_smtp() -> dict:
    try:
        if SMTP_CONFIG_FILE.exists():
            return json.loads(SMTP_CONFIG_FILE.read_text())
    except Exception:
        pass
    return {}

def _save_smtp(cfg: dict) -> None:
    try:
        SMTP_CONFIG_FILE.write_text(json.dumps(cfg))
    except Exception:
        pass

_cached_smtp: dict = _load_smtp()   # load at startup

# ── CORS — allow requests from the local file system and localhost ─────────────
@app.after_request
def add_cors(response):
    """Allow the agreement HTML to POST here whether opened from server or disk."""
    response.headers["Access-Control-Allow-Origin"]  = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response


# ── Routes ─────────────────────────────────────────────────────────────────────

def make_agreement_url(name: str, company: str, email: str) -> str:
    """Return a URL that opens the agreement pre-filled with installer details."""
    data = {
        "mode":      "installer",
        "instName":  name,
        "bizName":   company,
        "instEmail": email,
    }
    b64 = base64.b64encode(json.dumps(data).encode()).decode()
    return f"{SERVER_URL}/agreement#d={b64}"


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/agreement")
def agreement():
    """Serve the digital agreement HTML so installers can open it via link."""
    return send_file(AGREEMENT_HTML, mimetype="text/html")


@app.route("/run", methods=["POST"])
def run_workflow():
    """
    Runs the selected workflow phase and streams log output back as
    Server-Sent Events so the browser log updates in real time.
    """
    global _cached_smtp
    data = request.get_json(force=True)

    phase    = data.get("phase",    "agreement")
    name     = data.get("name",     "").strip()
    company  = data.get("company",  "").strip()
    email    = data.get("email",    "").strip()
    date     = data.get("date",     "").strip()
    dry_run  = data.get("dry_run",  True)
    password = data.get("password", "")
    provider = data.get("provider", "Principle Innovation (.tech)")
    custom_host = data.get("custom_host", "").strip()
    custom_port = data.get("custom_port", 465)

    # Build SMTP config
    if provider == "Custom SMTP…" or provider not in MAIL_PRESETS:
        host = custom_host
        port = int(custom_port)
    else:
        host, port = MAIL_PRESETS[provider]

    smtp_cfg = {
        "smtp_host":     host,
        "smtp_port":     port,
        "smtp_user":     onb.PI_EMAIL,
        "smtp_password": password,
    }

    # Cache and persist SMTP config (not during dry run — password not entered)
    if not dry_run and password:
        _cached_smtp = smtp_cfg
        _save_smtp(smtp_cfg)

    onb.DRY_RUN = dry_run

    # Generate agreement link so the email contains a button, not an attachment
    onb.AGREEMENT_URL = make_agreement_url(name, company, email)

    def generate():
        """Yields SSE events as log lines arrive from the workflow thread."""
        q      = queue.Queue()
        errors = []

        class _Capture:
            def write(self, s):
                if s:
                    q.put(("log", s))
            def flush(self):
                pass

        old_out = sys.stdout
        sys.stdout = _Capture()

        def worker():
            try:
                if phase == "agreement":
                    result = onb.run_agreement_phase(name, company, email, smtp_cfg)
                else:
                    result = onb.run_onboarding(name, company, email, date, smtp_cfg)
                q.put(("done", result))
            except Exception as exc:
                errors.append(str(exc))
                q.put(("error", str(exc)))
            finally:
                sys.stdout = old_out

        t = threading.Thread(target=worker, daemon=True)
        t.start()

        while True:
            try:
                kind, payload = q.get(timeout=60)
                if kind == "log":
                    yield f"data: {json.dumps({'type': 'log', 'msg': payload})}\n\n"
                elif kind == "done":
                    yield f"data: {json.dumps({'type': 'done', 'ok': bool(payload)})}\n\n"
                    break
                elif kind == "error":
                    yield f"data: {json.dumps({'type': 'error', 'msg': payload})}\n\n"
                    break
            except queue.Empty:
                yield f"data: {json.dumps({'type': 'ping'})}\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control":   "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.route("/submit-agreement", methods=["POST", "OPTIONS"])
def submit_agreement():
    """Receive the installer-signed agreement HTML and email it to Pi for countersigning."""
    # Handle CORS preflight
    if request.method == "OPTIONS":
        return jsonify({}), 200

    if not _cached_smtp:
        return jsonify({"ok": False,
                        "error": "Email not configured — please run Phase 1 (Send Email) first."})
    try:
        data       = request.get_json(force=True)
        html       = data.get("html",      "")
        biz_name   = data.get("bizName",   "Installer")
        inst_name  = data.get("instName",  "")
        inst_email = data.get("instEmail", "")
        abn        = data.get("abn",       "")
        inst_date  = data.get("instDate",  "")
        onb.send_signed_to_pi(
            inst_name, biz_name, inst_email, abn, inst_date, html, _cached_smtp
        )
        return jsonify({"ok": True})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)})


# ── Launch ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = 3000
    url  = f"http://localhost:{port}"
    print(f"\n  Pi Ops – Installer Onboarding")
    print(f"  Running at  {url}")
    if _cached_smtp:
        print(f"  SMTP config loaded from disk ({_cached_smtp.get('smtp_host','')})")
    else:
        print(f"  No SMTP config yet — run Phase 1 to configure email.")
    print(f"  Press Ctrl+C to stop.\n")
    threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    app.run(host="localhost", port=port, debug=False, threaded=True)
