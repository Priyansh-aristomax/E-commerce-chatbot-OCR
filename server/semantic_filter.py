import os
import logging
import json
from typing import List, Dict
from dotenv import load_dotenv
import google.generativeai as genai

# Load environment variables
load_dotenv()
logger = logging.getLogger(__name__)

# Configure Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)

async def detect_women_clothing_keywords(ocr_text: str) -> List[str]:
    """
    Use Gemini to detect women's clothing keywords from OCR text
    Returns a flat list of all detected fashion keywords
    """
    try:
        if not ocr_text or not ocr_text.strip():
            logger.warning("Empty OCR text provided")
            return []
        
        # Initialize NEW Gemini model instance for each call
        model = genai.GenerativeModel("gemini-1.5-flash")
        
        # Enhanced prompt with strict validation
        prompt = f"""
        You are a women's fashion expert. Analyze ONLY the following text and determine if it contains women's clothing keywords.

        IMPORTANT: Base your analysis ONLY on the text provided below. Do not use any previous context or examples.

        Text to analyze: "{ocr_text}"

        Instructions:
        1. Read the text above carefully
        2. If the text contains NO women's clothing keywords, return: []
        3. If the text is about non-clothing items (food, electronics, etc.), return: []
        4. If the text is unclear or unreadable, return: []
        5. Only extract keywords if the text clearly mentions women's clothing items
        6. Include: clothing types, colors, materials, styles, fits, patterns
        7. Focus ONLY on CLOTHING items (dresses, tops, pants, skirts, etc.)
        8. Do NOT include accessories like bags, shoes, jewelry
        9. Include EVENT-RELATED keywords like: wedding, party, casual, formal, office, bridal, cocktail, evening, festival, celebration
        10. Return as JSON array format

        Valid clothing keywords examples:
        - Clothing: "dress", "blouse", "jeans", "skirt", "top"
        - Colors: "black", "blue", "red"
        - Materials: "silk", "cotton", "denim"
        - Styles: "casual", "formal", "vintage"
        - Events: "wedding", "party", "bridal", "cocktail", "evening", "office"

        Return ONLY a JSON array of keywords found in the provided text, or [] if none:
        """
        
        # Generate response from Gemini with temperature=0 for consistency
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0,  # Make it deterministic
                top_p=1,
                top_k=1,
                max_output_tokens=500,
            )
        )
        response_text = response.text.strip()
        
        logger.info(f"Gemini raw response: {response_text}")
        
        # Parse JSON response
        try:
            # Clean response text (remove markdown formatting if present)
            if response_text.startswith("```json"):
                response_text = response_text.replace("```json", "").replace("```", "").strip()
            elif response_text.startswith("```"):
                response_text = response_text.replace("```", "").strip()
            
            keywords = json.loads(response_text)
            
            # Ensure it's a list and clean keywords
            if isinstance(keywords, list):
                # Filter out empty strings and clean keywords
                cleaned_keywords = [kw.strip().lower() for kw in keywords if kw and kw.strip()]
                
                if cleaned_keywords:
                    logger.info(f"✅ Detected {len(cleaned_keywords)} fashion keywords")
                    
                    # Print to console for validation
                    print("\n" + "="*50)
                    print("🔍 DETECTED WOMEN'S CLOTHING KEYWORDS:")
                    print("="*50)
                    print(f"Original text: {ocr_text[:100]}...")
                    print(f"Keywords: {json.dumps(cleaned_keywords, indent=2)}")
                    print("="*50 + "\n")
                    
                    return cleaned_keywords
                else:
                    print("\n" + "="*50)
                    print("❌ NO FASHION KEYWORDS DETECTED")
                    print("="*50)
                    print(f"Original text: {ocr_text[:100]}...")
                    print("="*50 + "\n")
                    return []
            else:
                logger.error("Response is not a JSON array")
                return []
                
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.error(f"Raw response: {response_text}")
            return []
            
    except Exception as e:
        logger.error(f"Gemini keyword detection failed: {e}")
        return []

async def generate_product_description(keywords: List[str]) -> str:
    """
    Generate product description from fashion keywords using Gemini
    """
    try:
        if not keywords:
            logger.warning("No keywords provided for description generation")
            return ""
        
        # Initialize NEW Gemini model instance
        model = genai.GenerativeModel("gemini-1.5-flash")
        
        # Create prompt for product description generation
        keywords_text = ", ".join(keywords)
        
        prompt = f"""
        Create a product description for women's clothing based on these keywords: {keywords_text}

        Instructions:
        1. Create ONE natural product description (1-2 sentences)
        2. Use appealing words like "Beautiful", "Elegant", "Stunning"
        3. Focus on women's clothing
        4. Incorporate the keywords naturally
        5. If event keywords are present (wedding, party, etc.), mention the occasion
        6. Keep it professional

        Return ONLY the description:
        """
        
        # Generate description
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.3,
                max_output_tokens=100,
            )
        )
        description = response.text.strip().strip('"\'')
        
        logger.info(f"Generated product description: {description}")
        
        print("\n" + "="*60)
        print("GENERATED PRODUCT DESCRIPTION:")
        print("="*60)
        print(f"Keywords: {keywords}")
        print(f"Description: {description}")
        print("="*60 + "\n")
        
        return description
        
    except Exception as e:
        logger.error(f"Product description generation failed: {e}")
        return ""

async def process_fashion_keywords(ocr_text: str) -> Dict:
    """
    Main function to process OCR text, extract keywords, and generate product description
    """
    try:
        # Step 1: Detect keywords using Gemini
        keywords = await detect_women_clothing_keywords(ocr_text)
        
        # Step 2: Only generate description if keywords found
        description = ""
        if keywords and len(keywords) > 0:
            description = await generate_product_description(keywords)
        
        # Determine success based on keywords found
        success = len(keywords) > 0 and description != ""
        
        result = {
            "success": success,
            "keywords_found": len(keywords),
            "keywords": keywords,
            "product_description": description,
            "processed_text_length": len(ocr_text) if ocr_text else 0
        }
        
        return result
        
    except Exception as e:
        logger.error(f"Fashion keyword processing failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "keywords_found": 0,
            "keywords": [],
            "product_description": "",
            "processed_text_length": 0
        }