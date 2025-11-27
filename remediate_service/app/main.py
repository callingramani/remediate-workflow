from fastapi import FastAPI
from .api import router as api_router

app = FastAPI(title="Remediation Service")
app.include_router(api_router, prefix="")

@app.get("/health")
def health():
    return {"status": "ok"}
