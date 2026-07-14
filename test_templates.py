#!/usr/bin/env python3
"""Quick diagnostic: test TemplateResponse compatibility.

Run this on your Pi to verify the template rendering fix works:
    cd ~/skydex
    python3 test_templates.py

This starts a minimal server on port 8765 and prints whether the
TemplateResponse wrapper works with your installed Starlette version.
"""

import sys
import threading
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request
import uvicorn

BASE_DIR = Path(__file__).parent.resolve()

app = FastAPI(title="SkyDex Template Test")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")

# -- Same detection as api.py --
def _detect_template_api():
    try:
        from unittest.mock import MagicMock
        dummy_req = MagicMock(spec=Request)
        templates.TemplateResponse(dummy_req, "_nonexistent.html")
    except TypeError as e:
        msg = str(e).lower()
        if "takes" in msg or "positional" in msg or "request" in msg:
            return "old"
    except Exception:
        pass
    return "new"

_TEMPLATE_API = _detect_template_api()
print(f"Detected Starlette TemplateResponse API: {_TEMPLATE_API}")


def _template_response(request: Request, name: str, context: dict | None = None, **kwargs):
    ctx = context or {}
    if _TEMPLATE_API == "new":
        return templates.TemplateResponse(request, name, ctx, **kwargs)
    else:
        ctx["request"] = request
        return templates.TemplateResponse(name, ctx, **kwargs)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    try:
        return _template_response(request, "index.html")
    except Exception as e:
        return HTMLResponse(f"<h1>Template Error</h1><pre>{type(e).__name__}: {e}</pre>", status_code=500)

@app.get("/dex/{hex_code}", response_class=HTMLResponse)
async def dex_page(request: Request, hex_code: str):
    try:
        return _template_response(request, "dex.html", {"hex": hex_code})
    except Exception as e:
        return HTMLResponse(f"<h1>Template Error</h1><pre>{type(e).__name__}: {e}</pre>", status_code=500)


def run_test():
    server = threading.Thread(
        target=lambda: uvicorn.run(app, host="127.0.0.1", port=8765, log_level="error"),
        daemon=True,
    )
    server.start()
    time.sleep(2)

    results = []

    print("\n[Test 1] GET http://127.0.0.1:8765/")
    try:
        with urllib.request.urlopen("http://127.0.0.1:8765/", timeout=10) as resp:
            body = resp.read().decode()
            if "pokedex-device" in body:
                print("  PASS: Index page rendered successfully")
                results.append(True)
            elif "Template Error" in body:
                print(f"  FAIL: Template rendering error")
                print(f"  Response snippet: {body[:500]}")
                results.append(False)
            else:
                print(f"  UNEXPECTED: Response doesn't contain expected content")
                print(f"  Snippet: {body[:300]}")
                results.append(False)
    except Exception as e:
        print(f"  FAIL: {type(e).__name__}: {e}")
        results.append(False)

    print("\n[Test 2] GET http://127.0.0.1:8765/dex/AABBCC")
    try:
        with urllib.request.urlopen("http://127.0.0.1:8765/dex/AABBCC", timeout=10) as resp:
            body = resp.read().decode()
            if "pokedex-device" in body and "Dex Entry" in body:
                print("  PASS: Dex page rendered successfully")
                results.append(True)
            elif "Template Error" in body:
                print(f"  FAIL: Template rendering error")
                print(f"  Response snippet: {body[:500]}")
                results.append(False)
            else:
                print(f"  UNEXPECTED: Response doesn't contain expected content")
                print(f"  Snippet: {body[:300]}")
                results.append(False)
    except Exception as e:
        print(f"  FAIL: {type(e).__name__}: {e}")
        results.append(False)

    print("\n" + "=" * 50)
    if all(results):
        print("ALL TESTS PASSED - Template rendering is working!")
        print("You can now run:  python3 main.py")
    else:
        print("SOME TESTS FAILED - Check the errors above.")
    print("=" * 50)


if __name__ == "__main__":
    run_test()
