from fastapi import APIRouter, UploadFile, File, HTTPException, status
from app.utils.supabase_utils import upload_to_supabase_storage, add_resume_to_db
from app.utils.parser import extract_text_from_file
from app.utils.embedding_utils import get_embedding # Import embedding function
from io import BytesIO
import traceback # For detailed error logging
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/upload", tags=["Upload"])

@router.post("/resume")
async def upload_resume(file: UploadFile = File(...)):
    """
    Uploads a resume file:
    1. Extracts text content.
    2. Generates a vector embedding for the text.
    3. Uploads the original file to Supabase Storage.
    4. Saves metadata (filename, URL, text, embedding) to Supabase DB.
    """
    file_content_stream = None
    try:
        # Read file content into memory
        content = await file.read()
        file_content_stream = BytesIO(content) # Use BytesIO for seeking and re-reading

        # --- Step 1: Extract text ---
        logger.info(f"Extracting text from: {file.filename} ({file.content_type})")
        text = extract_text_from_file(file.filename, content)

        if text is None:
             # Parser now returns None for unsupported types or errors
             raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=f"Unsupported file type or error extracting text from {file.filename}. Supported types: PDF, DOCX, TXT."
            )
        if not text.strip():
            logger.warning(f"Extracted text is empty for {file.filename}.")
            # Decide if empty text is an error or just a warning
            # raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Extracted text content is empty.")

        logger.info(f"Text extracted successfully (length: {len(text)}).")

        # --- Step 2: Generate Embedding ---
        logger.info(f"Generating embedding for: {file.filename}")
        embedding = get_embedding(text)
        logger.info(f"Embedding generated (dimension: {len(embedding)}).")


        # --- Step 3: Upload to Supabase Storage ---
        logger.info("Uploading file to Supabase Storage...")
        # Pass the BytesIO stream, ensures it can be re-read if needed
        file_content_stream.seek(0) # Reset stream position before upload
        file_url = upload_to_supabase_storage(file_content_stream, file.filename)
        logger.info(f"File uploaded to URL: {file_url}")


        # --- Step 4: Save metadata & embedding to Supabase Database ---
        logger.info("Saving metadata and embedding to Supabase Database...")
        inserted_data = await add_resume_to_db(
            filename=file.filename,
            file_url=file_url,
            text_content=text,
            embedding=embedding # Pass the generated embedding
        )
        # logger.info(f"Metadata saved. DB Record ID: {inserted_data.get('id')}")

        # --- Step 5: Final response ---
        return {
            "message": "File uploaded, parsed, embedded, and saved successfully",
            "file_url": file_url,
            "resume_id": inserted_data.get("id"),
            "filename": file.filename,
            # "text_preview": text[:200] + "..." if len(text) > 200 else text # Optional: might remove later
        }

    except HTTPException as he:
        # Re-raise HTTPExceptions directly
        logger.error(f"HTTP Exception during upload: {he.detail}")
        raise he
    except Exception as e:
        logger.error(f"An unexpected error occurred during resume upload: {e}", exc_info=True)
        # print(traceback.format_exc()) # logger.error with exc_info=True does this
        # Generic error for unexpected issues
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred during processing: {e}"
        )
    finally:
        # Ensure the UploadFile resources are released
        if file:
            await file.close()
        # Close BytesIO stream if it was created
        if file_content_stream:
            file_content_stream.close()