# ... (existing imports) ...
import os
from supabase import create_client, Client
import uuid
from dotenv import load_dotenv
import mimetypes
from io import BytesIO
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")  # Ensure this is the SERVICE key
SUPABASE_BUCKET_NAME = os.getenv("SUPABASE_BUCKET_NAME")

if not SUPABASE_URL or not SUPABASE_KEY:
    # Use logger instead of print
    logger.critical("Supabase URL and Service Key must be set in environment variables (SUPABASE_URL, SUPABASE_SERVICE_KEY)")
    # Keep the raise to prevent the application from starting without keys
    raise ValueError("Supabase URL and Service Key must be set in environment variables (SUPABASE_URL, SUPABASE_SERVICE_KEY)")
if not SUPABASE_BUCKET_NAME:
     logger.critical("Supabase Bucket Name must be set (SUPABASE_BUCKET_NAME)")
     raise ValueError("Supabase Bucket Name must be set (SUPABASE_BUCKET_NAME)")


DB_TABLE_NAME = os.getenv("SUPABASE_TABLE_NAME", "resume-analyser")  # Make configurable
DB_MATCH_FUNCTION_NAME = os.getenv("SUPABASE_MATCH_FUNCTION", "match_resumes")  # Make configurable

supabase: Optional[Client] = None  # Initialize as None

try:
    logger.info("Attempting to initialize Supabase client...")
    # Avoid logging the full key
    logger.info(f"URL: {SUPABASE_URL[:20]}...")
    logger.info(f"Service Key Provided: {'Yes' if SUPABASE_KEY else 'No'}")
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    # Basic check to see if client is usable
    # await supabase.from_(DB_TABLE_NAME).select("id").limit(0).execute() # Requires async context or sync client
    logger.info("Supabase client initialized successfully.")
except Exception as e:
    logger.critical(f"CRITICAL: Error initializing Supabase client: {e}", exc_info=True)
    # Keep supabase as None to indicate failure. main.py will check this.

def get_supabase_client() -> Client:
    """Returns the initialized Supabase client or raises an error."""
    if supabase is None:
        # This error message is caught and re-raised in main.py and routers
        raise RuntimeError("Supabase client is not initialized. Check logs for critical initialization errors.")
    return supabase

def upload_to_supabase_storage(file: BytesIO, filename: str) -> str:
    """Uploads a file stream to Supabase Storage."""
    client = get_supabase_client()
    unique_folder = os.getenv("SUPABASE_FOLDER_PATH", "resumes")
    unique_filename = f"{uuid.uuid4()}_{filename}"
    file_path_in_bucket = f"{unique_folder}/{unique_filename}"

    content_type, _ = mimetypes.guess_type(filename)
    if content_type is None:
        content_type = "application/octet-stream"

    logger.info(f"Uploading '{filename}' to Supabase bucket '{SUPABASE_BUCKET_NAME}' as '{file_path_in_bucket}'...")

    try:
        file.seek(0) # Ensure file pointer is at the beginning
        upload_response = client.storage.from_(SUPABASE_BUCKET_NAME).upload(
            path=file_path_in_bucket,
            file=file.getvalue(), # Use getvalue() for BytesIO content
            file_options={
                "content-type": content_type,
                "x-upsert": "false"
            }
        )
        logger.info(f"Supabase storage upload API call initiated for path: {file_path_in_bucket}.") # Response object might be complex, simplified log

    except Exception as e:
        logger.error(f"Error uploading file '{filename}' to Supabase Storage: {e}", exc_info=True)
        # Re-raise the exception with context
        raise Exception(f"Failed to upload file to storage: {str(e)}") from e

    try:
        # Supabase storage upload doesn't return the public URL directly.
        # You need to call get_public_url after successful upload.
        public_url = client.storage.from_(SUPABASE_BUCKET_NAME).get_public_url(file_path_in_bucket)

        if not isinstance(public_url, str) or not public_url.startswith('http'):
            logger.error(f"Failed to get a valid public URL for {file_path_in_bucket}. Received: {public_url}. Check bucket permissions.")
            raise ValueError(f"Failed to get a valid public URL for {file_path_in_bucket}")

        logger.info(f"Successfully retrieved public URL: {public_url}")
        return public_url
    except Exception as e:
        logger.error(f"Error getting public URL from Supabase for '{file_path_in_bucket}': {e}", exc_info=True)
        raise Exception(f"Failed to get public URL: {str(e)}") from e


async def add_resume_to_db(filename: str, file_url: str, text_content: str, embedding: List[float]) -> dict:
    """Adds resume metadata and its embedding to the Supabase database."""
    client = get_supabase_client()
    logger.info(f"Adding resume metadata and embedding to Supabase DB table '{DB_TABLE_NAME}' for: {filename}")
    try:
        data_to_insert = {
            "filename": filename,
            "file_url": file_url,
            # Store the extracted text, even if empty, for potential future use
            "text_content": text_content if text_content is not None else "",
            "embedding": embedding
        }
        # Using upsert might be better if filename could be a unique constraint,
        # but insert is fine for now as we generate unique IDs.
        # execute() is part of the postgrest client used by supabase-py
        # .select() is needed to return the inserted row data
        response_data = client.table(DB_TABLE_NAME).insert(data_to_insert).select("*").execute()

        # Check for errors in the response structure
        if response_data.data is None:
             error_detail = f"Supabase insert operation failed or returned empty data. Status: {response_data.status_code}, Error: {response_data.error}"
             logger.error(error_detail)
             raise Exception(f"Database insert failed: {error_detail}")

        if isinstance(response_data.data, list) and len(response_data.data) > 0:
            inserted_record = response_data.data[0]
            if 'id' in inserted_record and inserted_record['id'] is not None:
                logger.info(f"Successfully inserted resume data. ID: {inserted_record.get('id')}")
                return inserted_record
            else:
                error_message = f"Supabase insert succeeded but returned data missing 'id'. Data: {inserted_record}"
                logger.error(error_message)
                raise Exception(error_message)
        else:
            # This case should ideally not happen if data is not None and insert was successful
            error_message = f"Supabase insert returned unexpected data format. Expected list with record, got: {response_data.data}"
            logger.error(error_message)
            raise Exception(error_message)

    except Exception as e:
        logger.error(f"Error during Supabase DB insert operation for '{filename}': {e}", exc_info=True)
        # Re-raise the exception with context
        raise Exception(f"Database insert failed: {str(e)}") from e


async def search_resumes_by_vector(
    jd_embedding: List[float],
    match_threshold: float = 0.7,
    match_count: int = 10
) -> List[Dict[str, Any]]:
    """
    Searches resumes via RPC based on vector similarity.

    IMPORTANT: The Supabase RPC function '{DB_MATCH_FUNCTION_NAME}' MUST return
    the 'text_content' column along with id, filename, file_url, and similarity
    for the RAG analysis to work correctly.
    """
    client = get_supabase_client()
    logger.info(f"Searching resumes using RPC function '{DB_MATCH_FUNCTION_NAME}'. Threshold: {match_threshold}, Count: {match_count}")
    try:
        params = {
            'query_embedding': jd_embedding,
            'match_threshold': match_threshold,
            'match_count': match_count
        }
        # Call the RPC function
        response_data = client.rpc(DB_MATCH_FUNCTION_NAME, params).execute()

        # Check for errors in the response structure
        if response_data.data is None:
             error_detail = f"Supabase RPC call '{DB_MATCH_FUNCTION_NAME}' failed or returned empty data. Status: {response_data.status_code}, Error: {response_data.error}"
             logger.error(error_detail)
             raise Exception(f"Database RPC search failed: {error_detail}")

        if isinstance(response_data.data, list):
            logger.info(f"Found {len(response_data.data)} matches via RPC.")
            # Expecting list of dicts like: {'id': '...', 'filename': '...', 'file_url': '...', 'text_content': '...', 'similarity': ...}
            # Verify that text_content is present in at least the first result if list is not empty
            if response_data.data and 'text_content' not in response_data.data[0]:
                 logger.warning(f"Supabase RPC '{DB_MATCH_FUNCTION_NAME}' did not return 'text_content'. RAG feedback will not be possible.")

            return response_data.data
        else:
            # This case should ideally not happen if data is not None and RPC was successful
            logger.warning(f"RPC call '{DB_MATCH_FUNCTION_NAME}' executed but returned unexpected data format. Returning empty list. Data: {response_data.data}")
            return []

    except Exception as e:
        logger.error(f"Error during Supabase RPC call '{DB_MATCH_FUNCTION_NAME}': {e}", exc_info=True)
        # Re-raise the exception with context
        raise Exception(f"Database RPC search failed: {str(e)}") from e

async def get_all_resumes_from_db() -> list:
    """Fetches all resume metadata."""
    # This function is still useful for administrative purposes but less so for core analysis loop
    client = get_supabase_client()
    logger.warning(f"Fetching all resumes from DB table '{DB_TABLE_NAME}' (consider performance impact)...")
    try:
        # Explicitly select columns needed, including text_content if needed elsewhere, but maybe not always
        # For just listing, 'text_content' is usually not needed
        select_query = "id, filename, file_url, uploaded_at" # Don't fetch text_content unless needed
        response_data = client.table(DB_TABLE_NAME).select(select_query).execute()

        # Check for errors
        if response_data.data is None:
             error_detail = f"Supabase select all operation failed or returned empty data. Status: {response_data.status_code}, Error: {response_data.error}"
             logger.error(error_detail)
             raise Exception(f"Database select all failed: {error_detail}")


        if isinstance(response_data.data, list):
            logger.info(f"Fetched {len(response_data.data)} resumes metadata.")
            return response_data.data
        else:
            logger.warning(f"Select all from '{DB_TABLE_NAME}' executed but returned unexpected data format. Returning empty list. Data: {response_data.data}")
            return []

    except Exception as e:
        logger.error(f"Error fetching all resumes from '{DB_TABLE_NAME}': {e}", exc_info=True)
        raise Exception(f"Database select all failed: {str(e)}") from e