from fastapi import FastAPI, Response
import logging
import os

# Set up FastAPI app
app = FastAPI()

# Set up structured logging in JSON format
logging.basicConfig(level=logging.INFO, format='{"level": "%(levelname)s", "message": "%(message)s"}')
logger = logging.getLogger(__name__)

# Health check endpoint
@app.get("/health")
def read_health():
    logger.info("Health check endpoint hit.")
    return {"status": "ok"}

# Endpoint to simulate OOM (Out-Of-Memory) error
@app.get("/simulate-oom")
def simulate_oom():
    logger.info("Simulating OOM crash...")
    try:
        # Allocate memory in a non-terminating loop to mimic OOM crash
        data = []
        while True:
            data.append(os.urandom(1024 * 1024))  # allocate ~1MiB continuously
    except MemoryError as e:
        logger.error(f"Container crashed due to OOM: {str(e)}")
        return Response(content="Simulated Out-Of-Memory crash", status_code=500)

# Endpoint to simulate environment variable corruption
@app.get("/corrupt-env")
def corrupt_env():
    logger.info("Simulating critical environment variable corruption...")
    try:
        # Simulate loss of a critical environment variable
        os.environ.pop("DATABASE_URL", None)  # Remove DATABASE_URL if exists
        value = os.environ["DATABASE_URL"]  # Trigger KeyError
    except KeyError as e:
        logger.error(f"Critical environment variable is missing: {str(e)}")
        return Response(content="Simulated environment variable corruption", status_code=500)

    return {"message": "Unexpected behavior"}