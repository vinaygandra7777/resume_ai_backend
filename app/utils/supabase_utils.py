import os
from supabase import create_client, Client, PostgrestAPIResponse
# If storage responses have specific types in v2, import them, otherwise rely on attribute access
# from supabase.lib.storage.storage_response import UploadResponse # Example if needed
import uuid
from dotenv import load_dotenv
import mimetypes
from io import BytesIO
from typing import List, Dict, Any, Optional
import logging # Use logging

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
# IMPORTANT: Use the SERVICE ROLE KEY for operations requiring elevated privileges
# like calling DB functions (if security definer) or bypassing RLS for inserts/updates.
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
SUPABASE_BUCKET_NAME = os.getenv("SUPABASE_BUCKET_NAME")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Supabase URL and Service Key must be set in environment variables (SUPABASE_URL, SUPABASE_SERVICE_KEY)")
if not SUPABASE_BUCKET_NAME:
    raise ValueError("Supabase Bucket Name must be set (SUPABASE_BUCKET_NAME)")

# Ensure this matches your actual table name in Supabase
DB_TABLE_NAME = os.getenv("SUPABASE_TABLE_NAME", "resume-analyser") # Make configurable
# Ensure this matches the DB function you created
DB_MATCH_FUNCTION_NAME = os.getenv("SUPABASE_MATCH_FUNCTION", "match_resumes") # Make configurable

try:
    logger.info("Attempting to initialize Supabase client...")
    logger.info(f"URL: {SUPABASE_URL[:20]}...")
    logger.info(f"Service Key Provided: {'Yes' if SUPABASE_KEY else 'No'}")
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    logger.info("Supabase client initialized successfully.")
except Exception as e:
    logger.error(f"Error initializing Supabase client: {e}", exc_info=True)
    supabase = None # Set to None to indicate failure

def get_supabase_client() -> Client:
    """Returns the initialized Supabase client or raises an error."""
    if not supabase:
        # This error should ideally prevent the app from starting fully
        # (checked in main.py)
        raise RuntimeError("Supabase client is not initialized. Check logs for initialization errors.")
    return supabase

def upload_to_supabase_storage(file: BytesIO, filename: str) -> str:
    """
    Uploads a file stream to Supabase Storage.
    NOTE: This operation is synchronous in supabase-py v2.
    """
    client = get_supabase_client()
    unique_folder = os.getenv("SUPABASE_FOLDER_PATH", "resumes")
    unique_filename = f"{uuid.uuid4()}_{filename}"
    file_path_in_bucket = f"{unique_folder}/{unique_filename}"

    content_type, _ = mimetypes.guess_type(filename)
    if content_type is None:
        content_type = "application/octet-stream"

    logger.info(f"Uploading '{filename}' to Supabase bucket '{SUPABASE_BUCKET_NAME}' as '{file_path_in_bucket}'...")

    try:
        file.seek(0)
        # client.storage.from_().upload() is synchronous in v2
        storage_response = client.storage.from_(SUPABASE_BUCKET_NAME).upload(
            path=file_path_in_bucket,
            file=file.read(),
            file_options={
                "content-type": content_type,
                "x-upsert": "false"
            }
        )
        # Access response attributes directly (v2 pattern)
        # Note: The actual response object might not always have '.path'. Check Supabase docs/debug if needed.
        # Often, success is indicated by lack of exception, and you use the input path for get_public_url.
        logger.info(f"Supabase storage upload API call potentially successful for path: {file_path_in_bucket}. Response: {storage_response}")

    except Exception as e:
        # Catch potential API errors from Supabase storage. Check e.details if available.
        logger.error(f"Error uploading file to Supabase Storage: {e}", exc_info=True)
        # if hasattr(e, 'details'): logger.error(f"Supabase error details: {e.details}")
        raise # Re-raise the exception

    # --- Get Public URL ---
    try:
        # client.storage.from_().get_public_url() is synchronous and returns string directly
        public_url = client.storage.from_(SUPABASE_BUCKET_NAME).get_public_url(file_path_in_bucket)

        if not isinstance(public_url, str) or not public_url.startswith('http'):
             logger.warning(f"Unexpected format for public URL: {public_url}. Check bucket permissions ('{SUPABASE_BUCKET_NAME}') and path ('{file_path_in_bucket}').")
             # Avoid manual construction unless absolutely necessary and verified.
             raise ValueError(f"Failed to get a valid public URL for {file_path_in_bucket}")

        logger.info(f"Successfully retrieved public URL: {public_url}")
        return public_url
    except Exception as e:
        logger.error(f"Error getting public URL from Supabase: {e}", exc_info=True)
        raise


# --- MODIFIED FUNCTION ---
async def add_resume_to_db(filename: str, file_url: str, text_content: str, embedding: List[float]) -> dict:
    """
    Adds resume metadata and its embedding to the Supabase database.
    The function is async to fit FastAPI, but the .execute() call is synchronous.
    """
    client = get_supabase_client()
    logger.info(f"Adding resume metadata and embedding to Supabase DB table '{DB_TABLE_NAME}' for: {filename}")
    try:
        data_to_insert = {
            "filename": filename,
            "file_url": file_url,
            "text_content": text_content,
            "embedding": embedding # Ensure embedding column name matches DB
        }

        # .execute() is SYNCHRONOUS in supabase-py v2 - DO NOT use 'await' here
        response: PostgrestAPIResponse = client.table(DB_TABLE_NAME).insert(data_to_insert).execute()

        # --- Robust Response Checking ---
        logger.debug(f"Supabase DB insert API response status: {response.status_code}")
        # logger.debug(f"Supabase DB insert API response data: {response.data}") # Be careful logging potentially large data

        # Check status code for success (usually 201 for Created)
        if response.status_code == 201 and response.data and isinstance(response.data, list) and len(response.data) > 0:
            inserted_record = response.data[0]
            if 'id' in inserted_record and inserted_record['id'] is not None:
                 logger.info(f"Successfully inserted resume data. ID: {inserted_record.get('id')}")
                 return inserted_record
            else:
                 # This case (201 status but missing ID in data) would be unusual
                 error_message = f"Supabase insert returned status 201 but data missing 'id'. Data: {inserted_record}"
                 logger.error(error_message)
                 raise Exception(error_message)
        else:
            # Handle other status codes or unexpected data format
            error_message = f"Supabase insert failed or returned unexpected data. Status: {response.status_code}. Response Data: {response.data}"
            logger.error(error_message)
            # You could check response.error here if the library populates it on failure
            # if hasattr(response, 'error') and response.error:
            #     logger.error(f"Supabase error details: {response.error}")
            raise Exception(error_message)

    except Exception as e:
        # Catch exceptions from the API call itself or our checks/raises
        logger.error(f"Error during Supabase DB insert operation: {e}", exc_info=True)
        # if hasattr(e, 'details'): logger.error(f"Supabase error details: {e.details}")
        raise # Re-raise the exception


# --- UPDATED FUNCTION ---
async def search_resumes_by_vector(
    jd_embedding: List[float],
    match_threshold: float = 0.7,
    match_count: int = 10
) -> List[Dict[str, Any]]:
    """
    Searches resumes via RPC based on vector similarity.
    The function is async, but the .execute() call is synchronous.
    """
    client = get_supabase_client()
    logger.info(f"Searching resumes using RPC function '{DB_MATCH_FUNCTION_NAME}'. Threshold: {match_threshold}, Count: {match_count}")
    try:
        params = {
            'query_embedding': jd_embedding,
            'match_threshold': match_threshold,
            'match_count': match_count
        }
        # .execute() is SYNCHRONOUS in supabase-py v2 - DO NOT use 'await' here
        response: PostgrestAPIResponse = client.rpc(DB_MATCH_FUNCTION_NAME, params).execute()

        logger.debug(f"Supabase RPC call status: {response.status_code}")
        # logger.debug(f"Supabase RPC call data: {response.data}")

        # Check for successful status code (usually 200 for RPC OK)
        if response.status_code == 200 and response.data and isinstance(response.data, list):
            logger.info(f"Found {len(response.data)} matches via RPC.")
            return response.data
        elif response.status_code == 200: # Success status but maybe no data or wrong format
             logger.info(f"RPC call '{DB_MATCH_FUNCTION_NAME}' succeeded but returned no matches or unexpected data format: {type(response.data)}")
             return []
        else:
            # Handle RPC error status codes
            error_message = f"Supabase RPC call '{DB_MATCH_FUNCTION_NAME}' failed. Status: {response.status_code}. Response Data: {response.data}"
            logger.error(error_message)
            # if hasattr(response, 'error') and response.error:
            #     logger.error(f"Supabase error details: {response.error}")
            raise Exception(error_message)

    except Exception as e:
        logger.error(f"Error during Supabase RPC call '{DB_MATCH_FUNCTION_NAME}': {e}", exc_info=True)
        # if hasattr(e, 'details'): logger.error(f"Supabase error details: {e.details}")
        raise # Re-raise the exception


# --- UPDATED FUNCTION ---
async def get_all_resumes_from_db() -> list:
    """
    Fetches all resume metadata (use with caution for large datasets).
    The function is async, but the .execute() call is synchronous.
    """
    client = get_supabase_client()
    logger.warning(f"Fetching all resumes from DB table '{DB_TABLE_NAME}' (consider performance impact)...")
    try:
        # Select specific columns, excluding 'embedding' if not needed here
        select_query = "id, filename, file_url, text_content, uploaded_at"

        # .execute() is SYNCHRONOUS in supabase-py v2 - DO NOT use 'await' here
        response: PostgrestAPIResponse = client.table(DB_TABLE_NAME).select(select_query).execute()

        logger.debug(f"Supabase select all status: {response.status_code}")

        if response.status_code == 200 and response.data and isinstance(response.data, list):
            logger.info(f"Fetched {len(response.data)} resumes.")
            return response.data
        elif response.status_code == 200:
             logger.info(f"Select all from '{DB_TABLE_NAME}' succeeded but returned no data.")
             return []
        else:
             # Handle select error status codes
            error_message = f"Supabase select all from '{DB_TABLE_NAME}' failed. Status: {response.status_code}. Response Data: {response.data}"
            logger.error(error_message)
            # if hasattr(response, 'error') and response.error:
            #     logger.error(f"Supabase error details: {response.error}")
            raise Exception(error_message)

    except Exception as e:
        logger.error(f"Error fetching all resumes: {e}", exc_info=True)
        # if hasattr(e, 'details'): logger.error(f"Supabase error details: {e.details}")
        return [] # Return empty list on failure for this specific function maybe? Or re-raise? Re-raising is often better.
        # raise e # Re-raise to let the caller handle it