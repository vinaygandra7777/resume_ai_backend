import os
from supabase import create_client, Client
import uuid
from dotenv import load_dotenv
import mimetypes
from io import BytesIO

# Load environment variables
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
SUPABASE_BUCKET_NAME = os.getenv("SUPABASE_BUCKET_NAME")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Supabase URL and Key must be set in environment variables (SUPABASE_URL, SUPABASE_SERVICE_KEY)")

try:
    print("Attempting to initialize Supabase client...")
    print(f"URL: {SUPABASE_URL[:20]}...")
    print(f"Service Key Provided: {'Yes' if SUPABASE_KEY else 'No'}")
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    print("Supabase client initialized successfully.")
except Exception as e:
    print(f"Error initializing Supabase client: {e}")
    supabase = None

def get_supabase_client() -> Client:
    """Returns the initialized Supabase client."""
    if not supabase:
        raise RuntimeError("Supabase client is not initialized.")
    return supabase

def upload_to_supabase_storage(file: BytesIO, filename: str) -> str:
    # --- (Keep the existing upload_to_supabase_storage function code here) ---
    # ... (code for upload_to_supabase_storage) ...
    client = get_supabase_client()

    unique_folder = "Resume-analyser"
    unique_filename = f"{uuid.uuid4()}_{filename}"
    file_path_in_bucket = f"{unique_folder}/{unique_filename}"

    content_type, _ = mimetypes.guess_type(filename)
    if content_type is None:
        content_type = "application/octet-stream"

    print(f"Uploading '{filename}' to Supabase bucket '{SUPABASE_BUCKET_NAME}' as '{file_path_in_bucket}'...")

    try:
        file.seek(0)
        response = client.storage.from_(SUPABASE_BUCKET_NAME).upload(
            path=file_path_in_bucket,
            file=file.read(),
            file_options={
                "content-type": content_type,
                "x-upsert": "false"
            }
        )
        print("Supabase storage upload API call completed.")
        # You might want to check response details if needed, but often relies on exceptions

    except Exception as e:
        print(f"Error uploading file to Supabase Storage: {e}")
        raise

    try:
        public_url_response = client.storage.from_(SUPABASE_BUCKET_NAME).get_public_url(file_path_in_bucket)
        public_url = public_url_response
        if not isinstance(public_url, str) or not public_url.startswith('http'):
             print(f"Warning: Unexpected format for public URL: {public_url}. Attempting manual construction.")
             # Fallback URL construction (less ideal)
             public_url = f"{SUPABASE_URL}/storage/v1/object/public/{SUPABASE_BUCKET_NAME}/{file_path_in_bucket}"
             # Consider raising ValueError if even this looks wrong

        print(f"Successfully uploaded. Public URL: {public_url}")
        return public_url
    except Exception as e:
        print(f"Error getting public URL from Supabase: {e}")
        raise


# --- MODIFIED FUNCTION ---
async def add_resume_to_db(filename: str, file_url: str, text_content: str) -> dict:
    """
    Adds resume metadata to the Supabase 'resumes' table.

    Args:
        filename: Original filename.
        file_url: Public URL from Supabase Storage.
        text_content: Extracted text from the resume.

    Returns:
        The data of the inserted row (including the generated id and uploaded_at).

    Raises:
        RuntimeError: If Supabase client is not initialized.
        Exception: If the database insert fails or returns unexpected results.
    """
    client = get_supabase_client()
    print(f"Adding resume metadata to Supabase DB for: {filename}")
    try:
        data_to_insert = {
            "filename": filename,
            "file_url": file_url,
            "text_content": text_content
        }
        # Make the API call
        response = client.table('resume-analyser').insert(data_to_insert).execute()

        # --- More Robust Response Checking ---
        print(f"Supabase DB insert API response received.")
        # Uncomment the line below for detailed debugging ONLY (might print sensitive data)
        # print(f"Raw Supabase DB response: {response}")

        # 1. Check for explicit errors in the response object (common pattern)
        if hasattr(response, 'error') and response.error:
            error_message = f"Supabase DB insert failed with error: {response.error}"
            print(f"Error: {error_message}")
            # You could potentially check response.error details for specific handling
            raise Exception(error_message)

        # 2. Check if data exists and is in the expected list format
        if response.data and isinstance(response.data, list) and len(response.data) > 0:
            inserted_record = response.data[0]
            # 3. Check if the returned record has an ID (essential)
            if 'id' in inserted_record and inserted_record['id'] is not None:
                 print(f"Successfully inserted resume data. ID: {inserted_record.get('id')}")
                 return inserted_record # Return the dictionary of the inserted record
            else:
                 # This case is odd: data exists but no ID? Log and raise.
                 error_message = "Supabase insert returned data but missing 'id'."
                 print(f"Error: {error_message}. Returned data: {inserted_record}")
                 raise Exception(error_message)
        else:
            # This means no error was explicitly reported, but no data came back.
            error_message = "Supabase insert reported success but returned no data or unexpected format."
            print(f"Error: {error_message}. Raw Response: {response}") # Log response for debugging
            raise Exception(error_message)

    except Exception as e:
        # Catch exceptions from the API call itself or our checks/raises
        print(f"Error during Supabase DB insert operation: {e}")
        # Optionally log the data that failed
        # print(f"Failed data: filename={filename}, file_url={file_url}, text_content length={len(text_content)}")
        raise # Re-raise the exception to be caught by the FastAPI endpoint handler