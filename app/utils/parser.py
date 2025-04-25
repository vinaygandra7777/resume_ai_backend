#parser.py
import fitz  # PyMuPDF
import docx  # For .docx support
from io import BytesIO
import logging # Use logging for better error messages

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def extract_text_from_file(filename: str, content_bytes: bytes):
    """
    Extracts text content from PDF, DOCX, or TXT files.

    Args:
        filename: The name of the file (used to determine type).
        content_bytes: The file content as bytes.

    Returns:
        The extracted text as a string, or None if the file type is unsupported
        or an error occurs during extraction.
    """
    try:
        if filename.lower().endswith(".pdf"):
            return extract_text_from_pdf(content_bytes)
        elif filename.lower().endswith(".docx"):
            return extract_text_from_docx(content_bytes)
        elif filename.lower().endswith(".txt"):
            # Attempt common encodings, default to utf-8 with error handling
            try:
                return content_bytes.decode("utf-8")
            except UnicodeDecodeError:
                logger.warning(f"UTF-8 decoding failed for {filename}, trying latin-1.")
                try:
                    return content_bytes.decode("latin-1")
                except Exception as decode_err:
                    logger.error(f"Could not decode TXT file {filename}: {decode_err}")
                    return None # Indicate failure
        else:
            logger.warning(f"Unsupported file type for text extraction: {filename}")
            return None # Return None for unsupported types
    except Exception as e:
        logger.error(f"Error extracting text from {filename}: {e}", exc_info=True)
        return None # Return None on any extraction error


def extract_text_from_pdf(content_bytes: bytes) -> str:
    """Extracts text from PDF bytes using PyMuPDF."""
    text = ""
    try:
        with fitz.open(stream=content_bytes, filetype="pdf") as doc:
            for page in doc:
                text += page.get_text() + "\n" # Add newline between pages
    except Exception as e:
        logger.error(f"Failed to process PDF: {e}")
        raise # Re-raise to be caught by the main extractor function
    return text

def extract_text_from_docx(content_bytes: bytes) -> str:
    """Extracts text from DOCX bytes using python-docx."""
    text = ""
    try:
        doc = docx.Document(BytesIO(content_bytes))
        text = "\n".join([para.text for para in doc.paragraphs])
    except Exception as e:
        logger.error(f"Failed to process DOCX: {e}")
        raise # Re-raise
    return text