from fastapi import FastAPI
from app.routers import upload,match,analyze
from app.utils import supabase_utils # To trigger initialization check early

app = FastAPI(title="Resume Analyzer API")

# Check if Supabase client initialized successfully on startup
try:
    supabase_utils.get_supabase_client() # This will raise RuntimeError if init failed
    print("FastAPI startup: Supabase client confirmed initialized.")
except RuntimeError as e:
    print(f"FastAPI startup FATAL ERROR: {e}")
app.include_router(upload.router)
app.include_router(match.router)
app.include_router(analyze.router)
@app.get("/", tags=["Root"])
async def read_root():
    return {"message": "Welcome to the Resume Analyzer API"}

# --- Optional: Add Embedding/Ranking Endpoints Later ---
# Example placeholder:
# from app.routers import analysis
# app.include_router(analysis.router)
