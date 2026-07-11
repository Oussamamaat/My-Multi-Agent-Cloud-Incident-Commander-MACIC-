from fastapi import FastAPI, Response
from fastapi.responses import PlainTextResponse
import logging
import os
from prometheus_client import generate_latest, Counter

app = FastAPI()

logging.basicConfig(level=logging.INFO, format='{"level": "%(levelname)s", "message": "%(message)s"}')
logger = logging.getLogger(__name__)

REQUEST_COUNT = Counter("request_count", "Total request count")

@app.middleware("http")
async def count_requests(request, call_next):
    response = await call_next(request)
    REQUEST_COUNT.inc()
    return response

@app.get("/health")
def read_health():
    logger.info("Health check endpoint hit.")
    return {"status": "ok"}

@app.get("/metrics", response_class=PlainTextResponse)
def metrics():
    return PlainTextResponse(generate_latest(), media_type="text/plain")

@app.get("/simulate-oom")
def simulate_oom():
    logger.info("Simulating OOM crash...")
    try:
        data = []
        while True:
            data.append(os.urandom(1024 * 1024))
    except MemoryError as e:
        logger.error(f"Container crashed due to OOM: {str(e)}")
        return Response(content="Simulated Out-Of-Memory crash", status_code=500)

@app.get("/corrupt-env")
def corrupt_env():
    logger.info("Simulating critical environment variable corruption...")
    try:
        os.environ.pop("DATABASE_URL", None)
        value = os.environ["DATABASE_URL"]
    except KeyError as e:
        logger.error(f"Critical environment variable is missing: {str(e)}")
        return Response(content="Simulated environment variable corruption", status_code=500)

    return {"message": "Unexpected behavior"}

@app.get("/cpu-spike")
def cpu_spike():
    logger.info("Simulating CPU spike...")
    x = 0
    for i in range(10_000_000):
        x += i * i
    logger.error(f"Excessive CPU usage detected, result={x}")
    return Response(content="Simulated CPU throttling event", status_code=500)

@app.get("/crash-loop")
def crash_loop():
    logger.info("Simulating crash loop...")
    try:
        raise RuntimeError("Application crashed on startup: missing dependency")
    except RuntimeError as e:
        logger.error(f"Crash loop detected: {str(e)}")
        return Response(content="Simulated crash loop", status_code=500)