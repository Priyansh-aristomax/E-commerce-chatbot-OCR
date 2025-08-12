from PIL import Image
import pytesseract
import os

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

def extract_text_from_image(image_path: str) -> str:
    """Extract text from image files using OCR"""
    try:
        return pytesseract.image_to_string(Image.open(image_path))
    except Exception as e:
        return f"OCR extraction failed: {e}"