"""FastAPI application for webhook-gateway.

Aggregates GitHub and Lark webhook handlers into a single service.
"""
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from .config import PORT
from .github_webhook import router as github_router
from .lark_webhook import router as lark_router

app = FastAPI(
    title="webhook-gateway",
    description="Webhook gateway for CI/CD notifications and Lark card callbacks",
    version="1.0.0",
)

app.include_router(github_router)
app.include_router(lark_router)


@app.get("/health")
async def health():
    """Health check endpoint."""
    return JSONResponse(content={"status": "ok"})


def main():
    """Run the server with uvicorn."""
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=PORT)


if __name__ == "__main__":
    main()
