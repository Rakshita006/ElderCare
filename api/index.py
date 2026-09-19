"""
Nobi Interpreter — Vercel Python Serverless Entry Point
Handles all /api/* routes via vercel.json builds+routes.

IMPORTANT: Vercel requires 'app', 'handler', or 'application' to be defined
at the TOP LEVEL of this file (not inside try/except blocks).
We define app unconditionally first, then replace it with the real app.
"""
import os
import sys

# ── Step 1: Add project root so server.py can be imported ──────────────────
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

# ── Step 2: Define app unconditionally (required by Vercel static check) ────
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Nobi API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Step 3: Replace with real app from server.py ────────────────────────────
_import_error = None
try:
    import server as _server_module
    app = _server_module.app         # Replace placeholder with real FastAPI app
except Exception as _e:
    import traceback
    _import_error = traceback.format_exc()
    print(f"[Nobi Vercel] STARTUP ERROR — falling back to error reporter:\n{_import_error}")

    # Add error route to the placeholder app so we can see what failed
    @app.api_route(
        "/{path_name:path}",
        methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD", "PATCH"]
    )
    async def startup_error(path_name: str):
        return JSONResponse(
            status_code=500,
            content={
                "detail": "Vercel serverless startup failed — see traceback",
                "error": str(_e),
                "traceback": _import_error,
            }
        )

# ── Step 4: Export all names Vercel Python runtime may look for ─────────────
handler = app
application = app
