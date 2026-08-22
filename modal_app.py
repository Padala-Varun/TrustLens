"""
TrustLens — Modal Serverless Backend
Deploys the TrustLens pipeline as a serverless API on Modal.
"""

import modal
import json
import os

# ── Modal App ──────────────────────────────────────────────
app = modal.App("trustlens-api")

# ── Image with dependencies ────────────────────────────────
trustlens_image = (
    modal.Image.debian_slim(python_version="3.10")
    .pip_install(
        "fastapi[standard]",
        "python-whois==0.9.4",
        "requests==2.32.3",
        "beautifulsoup4==4.12.3",
        "lxml>=5.3.0",
        "python-dotenv==1.0.1",
        "mistralai==1.0.3",
        "tavily-python==0.5.0",
        "pygithub==2.4.0",
    )
    .add_local_file("whoislook.py", "/app/whoislook.py", copy=True)
    .add_local_file("websiteScrap.py", "/app/websiteScrap.py", copy=True)
    .add_local_file("github_collector.py", "/app/github_collector.py", copy=True)
    .add_local_file("tavily_collector.py", "/app/tavily_collector.py", copy=True)
    .add_local_file("evidence_normalizer.py", "/app/evidence_normalizer.py", copy=True)
    .add_local_file("mistral_reasoner.py", "/app/mistral_reasoner.py", copy=True)
)

# ── Secret for API keys ───────────────────────────────────
# Create this secret with:
#   modal secret create trustlens-secrets \
#     MISTRAL_API_KEY=... GITHUB_TOKEN=... TAVILY_API_KEY=...
trustlens_secret = modal.Secret.from_name(
    "trustlens-secrets",
    required_keys=["MISTRAL_API_KEY", "GITHUB_TOKEN", "TAVILY_API_KEY"]
)

VERCEL_ORIGIN = "https://trust-lens-gray.vercel.app"


# ============================================================
# HELPER
# ============================================================

def clean_domain(domain):
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
    try:
        json.dumps(obj)
        return obj
    except (TypeError, ValueError):
        pass
    if isinstance(obj, dict):
        return {k: make_json_safe(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [make_json_safe(item) for item in obj]
    else:
        return str(obj)


def cors_headers():
    return {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type",
    }


# ============================================================
# HEALTH CHECK
# ============================================================

@app.function(image=trustlens_image)
@modal.fastapi_endpoint(method="GET", label="trustlens-health")
def health():
    from fastapi.responses import JSONResponse
    return JSONResponse(
        content={"status": "ok", "service": "trustlens-api"},
        headers=cors_headers()
    )


# ============================================================
# SSE STREAMING ANALYSIS ENDPOINT
# ============================================================

@app.function(
    image=trustlens_image,
    secrets=[trustlens_secret],
    timeout=300,
)
@modal.fastapi_endpoint(method="GET", label="trustlens-analyze")
def analyze_stream(domain: str = ""):
    """
    SSE endpoint that runs the full TrustLens pipeline
    and streams progress events.
    """
    import sys
    sys.path.insert(0, "/app")

    import traceback
    from fastapi.responses import StreamingResponse

    domain = clean_domain(domain)

    if not domain:
        def error_gen():
            payload = json.dumps({"error": "No domain provided."})
            yield f"event: error_event\ndata: {payload}\n\n"

        return StreamingResponse(
            error_gen(),
            media_type="text/event-stream",
            headers={
                **cors_headers(),
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            }
        )

    def sse_generator():
        def send_event(event_type, data):
            payload = json.dumps(make_json_safe(data))
            return f"event: {event_type}\ndata: {payload}\n\n"

        try:
            # ── Step 1: WHOIS ──────────────────────────
            yield send_event("step_start", {"step": "whois"})

            try:
                from whoislook import get_domain_info
                whois_result = get_domain_info(domain)
                yield send_event("step_done", {"step": "whois"})
            except Exception as e:
                traceback.print_exc()
                whois_result = {"success": False, "error": str(e)}
                yield send_event("step_error", {
                    "step": "whois", "error": str(e)
                })

            # ── Step 2: Website ────────────────────────
            yield send_event("step_start", {"step": "website"})

            try:
                from websiteScrap import scrape_company_website
                website_result = scrape_company_website(domain)
                yield send_event("step_done", {"step": "website"})
            except Exception as e:
                traceback.print_exc()
                website_result = {"success": False, "error": str(e)}
                yield send_event("step_error", {
                    "step": "website", "error": str(e)
                })

            # ── Step 3: GitHub ─────────────────────────
            yield send_event("step_start", {"step": "github"})

            try:
                from github_collector import collect_github_evidence
                github_result = collect_github_evidence(domain)
                yield send_event("step_done", {"step": "github"})
            except Exception as e:
                traceback.print_exc()
                github_result = {"success": False, "error": str(e)}
                yield send_event("step_error", {
                    "step": "github", "error": str(e)
                })

            # ── Step 4: Tavily ─────────────────────────
            yield send_event("step_start", {"step": "tavily"})

            try:
                from tavily_collector import collect_search_evidence
                tavily_result = collect_search_evidence(domain)
                yield send_event("step_done", {"step": "tavily"})
            except Exception as e:
                traceback.print_exc()
                tavily_result = {"success": False, "error": str(e)}
                yield send_event("step_error", {
                    "step": "tavily", "error": str(e)
                })

            # ── Step 5: Normalize ──────────────────────
            yield send_event("step_start", {"step": "normalize"})

            try:
                from evidence_normalizer import build_evidence_packet
                evidence_packet = build_evidence_packet(
                    domain=domain,
                    whois_data=whois_result,
                    website_data=website_result,
                    github_data=github_result,
                    tavily_data=tavily_result
                )
                yield send_event("step_done", {"step": "normalize"})
            except Exception as e:
                traceback.print_exc()
                evidence_packet = {
                    "company_domain": domain,
                    "evidence": {},
                    "normalization_error": str(e)
                }
                yield send_event("step_error", {
                    "step": "normalize", "error": str(e)
                })

            # ── Step 6: Mistral AI ─────────────────────
            yield send_event("step_start", {"step": "analysis"})

            try:
                from mistral_reasoner import analyze_evidence
                analysis_result = analyze_evidence(evidence_packet)
                yield send_event("step_done", {"step": "analysis"})
            except Exception as e:
                traceback.print_exc()
                analysis_result = {"success": False, "error": str(e)}
                yield send_event("step_error", {
                    "step": "analysis", "error": str(e)
                })

            # ── Complete ───────────────────────────────
            full_result = {
                "company_domain": domain,
                "evidence_packet": evidence_packet,
                "analysis": analysis_result
            }

            yield send_event("complete", {
                "success": True,
                "result": full_result
            })

        except Exception as e:
            traceback.print_exc()
            yield send_event("error_event", {
                "error": f"Pipeline error: {str(e)}"
            })

    return StreamingResponse(
        sse_generator(),
        media_type="text/event-stream",
        headers={
            **cors_headers(),
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        }
    )
