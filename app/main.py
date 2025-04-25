from fastapi import FastAPI
from app.routers import upload, match, analyze
from app.utils import supabase_utils # To trigger initialization check early
import logging
import sys
import os # To potentially read log level from environment

# --- Logging Configuration ---
log_level_str = os.getenv("LOG_LEVEL", "INFO").upper()
log_level = getattr(logging, log_level_str, logging.INFO)

# Get the root logger
logger = logging.getLogger()
logger.setLevel(log_level) # Set the desired log level

# Configure handler if not already configured (e.g., by uvicorn)
# This basic setup ensures logs go to console. For production, consider JSON logging, file logging etc.
if not logger.hasHandlers():
    handler = logging.StreamHandler(sys.stdout)
    # More detailed formatter example
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s:%(lineno)d - %(levelname)s - %(message)s'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

# --- FastAPI App Initialization ---
logger.info("Initializing FastAPI application...")
app = FastAPI(
    title="Resume Analyzer API",
    description="API for uploading, matching, and analyzing resumes against job descriptions using semantic search.",
    version="1.0.0" # Add versioning
)

# --- Supabase Initialization Check ---
try:
    supabase_utils.get_supabase_client() # This will raise RuntimeError if init failed
    logger.info("FastAPI startup: Supabase client confirmed initialized.")
except RuntimeError as e:
    logger.critical(f"FastAPI startup FATAL ERROR: Supabase client failed to initialize: {e}")
    # Depending on your deployment, you might want the app to exit or prevent startup here
    # For now, it will log critically but continue setup.

# --- Include Routers ---
logger.info("Including API routers...")
app.include_router(upload.router)
app.include_router(match.router)
app.include_router(analyze.router)
logger.info("Routers included successfully.")

# --- Root Endpoint ---
@app.get("/", tags=["Root"])
async def read_root():
    """Provides a simple welcome message for the API root."""
    logger.info("Root endpoint '/' accessed.")
    return {
        "message": "Welcome to the Resume Analyzer API v1.0",
        "documentation": "/docs"
        }

# --- Optional Startup/Shutdown Events ---
@app.on_event("startup")
async def startup_event():
    logger.info("Application startup complete.")
    # You could add other startup tasks here, like loading models if not done globally

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Application shutting down.")
    # Add cleanup tasks here if needed

# --- Main execution block (for running directly with uvicorn command) ---
# Typically, you run FastAPI with: uvicorn app.main:app --reload
# This block is usually not needed when deploying with standard tools.
# if __name__ == "__main__":
#     import uvicorn
#     logger.info("Starting Uvicorn server directly...")
#     uvicorn.run(app, host="0.0.0.0", port=8000)