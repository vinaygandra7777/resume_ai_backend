#parser.py
import fitz  # PyMuPDF
import docx  # For .docx support

def extract_text_from_file(filename, content_bytes):
    if filename.endswith(".pdf"):
        return extract_text_from_pdf(content_bytes)
    elif filename.endswith(".docx"):
        return extract_text_from_docx(content_bytes)
    elif filename.endswith(".txt"):
        return content_bytes.decode("utf-8")
    else:
        return "Unsupported file type."

def extract_text_from_pdf(content_bytes):
    text = ""
    with fitz.open("pdf", content_bytes) as doc:
        for page in doc:
            text += page.get_text()
    return text

def extract_text_from_docx(content_bytes):
    from io import BytesIO
    doc = docx.Document(BytesIO(content_bytes))
    text = "\n".join([para.text for para in doc.paragraphs])
    return text

