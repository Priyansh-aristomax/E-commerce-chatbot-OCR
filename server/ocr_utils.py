# from PIL import Image
# import pytesseract
# import os

# pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# def extract_text_from_image(image_path: str) -> str:
#     """Extract text from image files using OCR"""
#     try:
#         return pytesseract.image_to_string(Image.open(image_path))
#     except Exception as e:
#         return f"OCR extraction failed: {e}"

import google.generativeai as genai
from PIL import Image
import os

# Configure Gemini API
genai.configure(api_key=os.getenv('GOOGLE_API_KEY'))

def extract_text_from_image(image_path: str) -> str:
    """Extract text from image files using Gemini Vision API"""
    try:
        # Initialize the model
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        # Open and prepare the image
        image = Image.open(image_path)
        
        # Create prompt for text extraction
        prompt = "Extract all text from this image. Return only the text content without any additional commentary or formatting."
        
        # Generate response
        response = model.generate_content([prompt, image])
        
        return response.text.strip()
        
    except Exception as e:
        return f"OCR extraction failed: {e}"