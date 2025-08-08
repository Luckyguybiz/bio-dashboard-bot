from fastapi import FastAPI

from .routes import channels, postwindows

app = FastAPI()


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


app.include_router(channels.router, prefix="/v1")
app.include_router(postwindows.router, prefix="/v1")
