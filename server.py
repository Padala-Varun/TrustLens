"""
TrustLens — Flask Server with SSE
Serves the web frontend and streams pipeline progress in real-time.
"""

import json
import sys
import os
import queue
import threading
import traceback

from flask import (
    Flask,
    Response,
    request,
    send_from_directory,
    jsonify
)

from dotenv import load_dotenv

# ── Ensure project root is importable ──────────────────────
sys.path.insert(
    0,
    os.path.dirname(os.path.abspath(__file__))
)

from whoislook import get_domain_info

from websiteScrap import (
    scrape_company_website
)

from github_collector import (
    collect_github_evidence
)

from tavily_collector import (
    collect_search_evidence
)

from evidence_normalizer import (
    build_evidence_packet
)

from mistral_reasoner import (
    analyze_evidence
)


# ── Environment ────────────────────────────────────────────
load_dotenv()


# ── Flask App ──────────────────────────────────────────────
app = Flask(
    __name__,
    static_folder='web',
    static_url_path=''
)


# ============================================================
# HELPERS
# ============================================================

def clean_domain(domain):
    """Normalize domain input."""
    if not domain:
        return ""
    domain = domain.strip().lower()
    domain = (
        domain
        .replace("https://", "")
        .replace("http://", "")
        .replace("www.", "")
        .split("/")[0]
    )
    return domain


def make_json_safe(obj):
    """
    Ensure object is JSON-serializable by converting
    non-serializable types to strings.
    """
    try:
        json.dumps(obj)
        return obj
    except (TypeError, ValueError):
        pass

    if isinstance(obj, dict):
        return {
            k: make_json_safe(v)
            for k, v in obj.items()
        }
    elif isinstance(obj, (list, tuple)):
        return [
            make_json_safe(item)
            for item in obj
        ]
    else:
        return str(obj)


# ============================================================
# ROUTES — STATIC FILES
# ============================================================

@app.route('/')
def index():
    return send_from_directory('web', 'index.html')


# ============================================================
# ROUTES — SSE ANALYSIS STREAM
# ============================================================

@app.route('/api/analyze/stream')
def analyze_stream():
    """
    Server-Sent Events endpoint that runs the full
    TrustLens pipeline and streams progress events.

    Events emitted:
      - step_start  { step: "whois" }
      - step_done   { step: "whois" }
      - step_error  { step: "whois", error: "..." }
      - complete    { success: true, result: { ... } }
      - error_event { error: "..." }
    """
    domain = request.args.get('domain', '').strip()
    domain = clean_domain(domain)

    if not domain:
        def error_stream():
            payload = json.dumps({
                "error": "No domain provided."
            })
            yield f"event: error_event\ndata: {payload}\n\n"

        return Response(
            error_stream(),
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'X-Accel-Buffering': 'no',
                'Connection': 'keep-alive',
            }
        )

    # Use a queue to pass SSE messages from worker thread
    msg_queue = queue.Queue()

    def send_event(event_type, data):
        payload = json.dumps(
            make_json_safe(data)
        )
        msg_queue.put(
            f"event: {event_type}\ndata: {payload}\n\n"
        )

    def run_pipeline():
        try:
            # ── Step 1: WHOIS ──────────────────────────
            send_event("step_start", {"step": "whois"})

            try:
                whois_result = get_domain_info(domain)
                send_event("step_done", {"step": "whois"})
            except Exception as e:
                traceback.print_exc()
                whois_result = {
                    "success": False,
                    "error": str(e)
                }
                send_event("step_error", {
                    "step": "whois",
                    "error": str(e)
                })

            # ── Step 2: Website ────────────────────────
            send_event("step_start", {"step": "website"})

            try:
                website_result = scrape_company_website(
                    domain
                )
                send_event("step_done", {"step": "website"})
            except Exception as e:
                traceback.print_exc()
                website_result = {
                    "success": False,
                    "error": str(e)
                }
                send_event("step_error", {
                    "step": "website",
                    "error": str(e)
                })

            # ── Step 3: GitHub ─────────────────────────
            send_event("step_start", {"step": "github"})

            try:
                github_result = collect_github_evidence(
                    domain
                )
                send_event("step_done", {"step": "github"})
            except Exception as e:
                traceback.print_exc()
                github_result = {
                    "success": False,
                    "error": str(e)
                }
                send_event("step_error", {
                    "step": "github",
                    "error": str(e)
                })

            # ── Step 4: Tavily ─────────────────────────
            send_event("step_start", {"step": "tavily"})

            try:
                tavily_result = collect_search_evidence(
                    domain
                )
                send_event("step_done", {"step": "tavily"})
            except Exception as e:
                traceback.print_exc()
                tavily_result = {
                    "success": False,
                    "error": str(e)
                }
                send_event("step_error", {
                    "step": "tavily",
                    "error": str(e)
                })

            # ── Step 5: Normalize ──────────────────────
            send_event("step_start", {"step": "normalize"})

            try:
                evidence_packet = build_evidence_packet(
                    domain=domain,
                    whois_data=whois_result,
                    website_data=website_result,
                    github_data=github_result,
                    tavily_data=tavily_result
                )
                send_event("step_done", {"step": "normalize"})
            except Exception as e:
                traceback.print_exc()
                evidence_packet = {
                    "company_domain": domain,
                    "evidence": {},
                    "normalization_error": str(e)
                }
                send_event("step_error", {
                    "step": "normalize",
                    "error": str(e)
                })

            # ── Step 6: Mistral AI ─────────────────────
            send_event("step_start", {"step": "analysis"})

            try:
                analysis_result = analyze_evidence(
                    evidence_packet
                )
                send_event("step_done", {"step": "analysis"})
            except Exception as e:
                traceback.print_exc()
                analysis_result = {
                    "success": False,
                    "error": str(e)
                }
                send_event("step_error", {
                    "step": "analysis",
                    "error": str(e)
                })

            # ── Complete ───────────────────────────────
            full_result = {
                "company_domain": domain,
                "evidence_packet": evidence_packet,
                "analysis": analysis_result
            }

            send_event("complete", {
                "success": True,
                "result": full_result
            })

        except Exception as e:
            send_event("error_event", {
                "error": f"Pipeline error: {str(e)}"
            })

        # Signal that we're done
        msg_queue.put(None)

    # Start the pipeline in a background thread
    worker = threading.Thread(
        target=run_pipeline,
        daemon=True
    )
    worker.start()

    def event_stream():
        while True:
            msg = msg_queue.get()
            if msg is None:
                break
            yield msg

    return Response(
        event_stream(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
            'Connection': 'keep-alive',
        }
    )


# ============================================================
# RUN SERVER
# ============================================================

if __name__ == '__main__':
    print("\n" + "=" * 50)
    print("  TRUSTLENS WEB SERVER")
    print("=" * 50)
    print(f"\n  -> http://localhost:5000")
    print(f"  -> Press Ctrl+C to stop\n")

    app.run(
        host='0.0.0.0',
        port=5000,
        debug=False,
        threaded=True
    )
