
from fastapi import APIRouter, UploadFile, File, HTTPException, status
from app.utils.supabase_utils import upload_to_supabase_storage, add_resume_to_db
from app.utils.parser import extract_text_from_file
from io import BytesIO
import traceback # For detailed error logging

router = APIRouter(prefix="/upload", tags=["Upload"])

@router.post("/resume")
async def upload_resume(file: UploadFile = File(...)):
    """
    Uploads a resume file, extracts text, stores file in Supabase Storage,
    and saves metadata in Supabase Database.
    """
    try:
        # Read file content into memory (necessary for parsing and uploading)
        # Use BytesIO to handle the content as a file-like object
        content = await file.read()
        file_content_stream = BytesIO(content)

        # --- Step 1: Extract text ---
        print(f"Extracting text from: {file.filename} ({file.content_type})")
        text = extract_text_from_file(file.filename, content)
        if text is None:
             raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=f"Unsupported file type: {file.filename}. Supported types: PDF, DOCX, TXT."
            )
        if "Error processing" in text or "Error decoding" in text:
             # Handle partial extraction errors if needed, or raise
             print(f"Warning: Text extraction resulted in an error message for {file.filename}")
             # Decide if you want to proceed or raise an error
             # For now, let's raise an error if extraction failed significantly
             raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to extract text reliably from {file.filename}. Error: {text}"
             )

        print(f"Text extracted successfully (length: {len(text)}).")


        # --- Step 2: Upload to Supabase Storage ---
        print("Uploading file to Supabase Storage...")
        # Pass the BytesIO stream to the upload function
        file_url = upload_to_supabase_storage(file_content_stream, file.filename)
        print(f"File uploaded to URL: {file_url}")


        # --- Step 3: Save metadata to Supabase Database ---
        print("Saving metadata to Supabase Database...")
        # Use the asynchronous function to add data
        inserted_data = await add_resume_to_db(
            filename=file.filename,
            file_url=file_url,
            text_content=text
        )
        # print(f"Metadata saved. DB Record ID: {inserted_data.get('id')}")

        # --- Step 4: Final response ---
        return {
            "message": "File uploaded, parsed, and saved successfully",
            "file_url": file_url,
            "resume_id": inserted_data.get("id"), # Get the ID from the response
            "filename": file.filename,
            "text_preview": text[:300] + "..." if len(text) > 300 else text
        }

    except HTTPException as he:
        # Re-raise HTTPExceptions directly
        raise he
    except Exception as e:
        print(f"An error occurred during resume upload: {e}")
        print(traceback.format_exc()) # Log detailed traceback for debugging
        # Generic error for unexpected issues
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {e}"
        )
    finally:
        # Ensure the UploadFile is closed
        await file.close()