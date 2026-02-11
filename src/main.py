from fastapi import FastAPI

from .webhook import github, lark

app = FastAPI(title="Webhook Gateway")

# Include routers
app.include_router(github.router, prefix="/webhook")
app.include_router(lark.router, prefix="/webhook")

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "webhook-gateway"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8280)
