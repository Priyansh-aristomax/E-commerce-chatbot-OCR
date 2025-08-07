from PIL import Image
import pytesseract
import fitz
import docx
import os

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

def extract_text(file_path: str) -> str:
    ext = os.path.splitext(file_path)[1].lower()
    try:
        if ext in [".jpg", ".jpeg", ".png"]:
            return pytesseract.image_to_string(Image.open(file_path))
        elif ext == ".pdf":
            return "\n".join([page.get_text() for page in fitz.open(file_path)])
        elif ext == ".docx":
            return "\n".join([p.text for p in docx.Document(file_path).paragraphs])
        else:
            return "Unsupported file format"
    except Exception as e:
        return f"OCR extraction failed: {e}"
