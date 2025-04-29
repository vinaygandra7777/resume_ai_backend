from fastapi import FastAPI
from app.routers import upload, match, analyze
from app.utils import supabase_utils # To trigger initialization check early
import logging
import sys
import os

# --- Logging Configuration ---
# Get the root logger
logger = logging.getLogger()

# Only configure handlers if none exist (prevents duplicate logs when run by uvicorn)
if not logger.handlers:
    log_level_str = os.getenv("LOG_LEVEL", "INFO").upper()
    log_level = getattr(logging, log_level_str, logging.INFO)
    logger.setLevel(log_level)

    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s:%(lineno)d - %(levelname)s - %(message)s'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.info(f"Logging configured to level: {logging.getLevelName(logger.getEffectiveLevel())}")
else:
    logger.info("Logging handlers already configured.")


# --- FastAPI App Initialization ---
logger.info("Initializing FastAPI application...")
app = FastAPI(
    title="Resume Analyzer API",
    description="API for uploading, matching, and analyzing resumes against job descriptions using semantic search and AI feedback.",
    version="1.0.0" # Add versioning
)

# --- Supabase Initialization Check ---
# This call is important to ensure the supabase_utils module runs its initialization logic
# and logs any critical errors early in the startup process.
try:
    # No need to assign the result, just call the getter to trigger potential errors
    supabase_utils.get_supabase_client()
    logger.info("FastAPI startup: Supabase client connectivity check passed (initialization attempted).")
except RuntimeError as e:
    # This error is raised if Supabase client creation failed in supabase_utils
    logger.critical(f"FastAPI startup FATAL ERROR: Supabase client failed to initialize. Application may not function correctly: {e}")
    # Depending on requirements, you might exit here: sys.exit(1)
except Exception as e:
     # Catch any other unexpected errors during this check
     logger.critical(f"FastAPI startup FATAL ERROR: Unexpected error during Supabase client check: {e}", exc_info=True)


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
        "documentation": "/docs",
        "endpoints": ["/upload/resume", "/match/jd", "/analyze/resumes"]
        }

# --- Optional Startup/Shutdown Events ---
@app.on_event("startup")
async def startup_event():
    logger.info("Application startup complete.")
    # You could add other startup tasks here

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