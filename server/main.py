import os
import logging
import re
from typing import List, Dict
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException, Depends, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import chromadb
from chromadb.config import Settings
import google.generativeai as genai
from ocr_utils import extract_text_from_image
from semantic_filter import process_fashion_keywords

# -------------------- Logging --------------------
logging.basicConfig(level=logging.INFO) 
logger = logging.getLogger(__name__)

# -------------------- Load Env --------------------
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    logger.error("GEMINI_API_KEY environment variable not set.")
    raise RuntimeError("GEMINI_API_KEY not set")

# -------------------- Gemini Setup --------------------
genai.configure(api_key=GEMINI_API_KEY)

# -------------------- Custom Gemini Embedder --------------------
class GeminiEmbeddingFunction:
    def __init__(self, model="models/embedding-001", api_key=None):
        self.model = model
        self.api_key = api_key
        genai.configure(api_key=api_key)
        self.__name__ = "gemini-embedding"
        self.name = lambda: "gemini-embedding"

    def __call__(self, input=None, texts=None):
        # Handle both 'input' and 'texts' parameters for ChromaDB compatibility
        if input is not None:
            texts = input
        elif texts is None:
            raise ValueError("Either 'input' or 'texts' parameter must be provided")
            
        if not isinstance(texts, list):
            texts = [texts]
            
        embeddings = []
        for text in texts:
            try:
                res = genai.embed_content(
                    model=self.model,
                    content=text,
                    task_type="retrieval_document"
                )
                embeddings.append(res["embedding"])
            except Exception as e:
                logger.error(f"Embedding failed for: {text}\nError: {e}")
                embeddings.append([0.0] * 768)
        return embeddings
    
# -------------------- FastAPI Init --------------------
app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "API is running"}

# -------------------- CORS --------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------- Request Model --------------------
class PromptRequest(BaseModel):
    prompt: str
    chat_history: List[Dict[str, str]] = []
    session_id: str | None = None

# -------------------- Embedding Function --------------------
embedding_fn = GeminiEmbeddingFunction(
    api_key=GEMINI_API_KEY,
    model="models/embedding-001"
)

# -------------------- ChromaDB Connection --------------------
def get_chroma_collection():
    try:
        logger.info("Initializing ChromaDB client...")
        client = chromadb.PersistentClient(
            path="./chroma_db",
            settings=Settings(anonymized_telemetry=False)
        )

        existing_collections = client.list_collections()
        collection_exists = any(col.name == "Clothes_products" for col in existing_collections)

        if collection_exists:
            collection = client.get_collection("Clothes_products")
            if hasattr(collection, '_embedding_function'):
                if collection._embedding_function.__class__.__name__ != embedding_fn.__class__.__name__:
                    logger.warning("Existing collection uses different embedding function")
            collection._embedding_function = embedding_fn
        else:
            collection = client.create_collection(
                name="Clothes_products",
                embedding_function=embedding_fn
            )
            logger.info("Created new collection")

        return collection

    except Exception as e:
        logger.exception("Failed to initialize ChromaDB")
        raise HTTPException(status_code=500, detail=f"Database initialization failed: {str(e)}")

# -------------------- Extract Chatbot Logic --------------------
async def generate_chatbot_response(request: PromptRequest, collection):
    """
    Generate chatbot response - extracted from /generate-response endpoint
    """
    logger.info("gasitaram")
    logger.info(f"Received request: {request.prompt}")
    try:
        logger.info(f"🤖 Processing chatbot request for session_id: {request.session_id}")

        valid_roles = {"user", "assistant"}
        for msg in request.chat_history:
            if not all(key in msg for key in ["role", "content"]) or msg["role"] not in valid_roles:
                raise HTTPException(status_code=400, detail="Invalid chat_history format")

        limited_history = request.chat_history[-10:]

        try:
            results = collection.query(
                query_texts=[request.prompt],
                n_results=5
            )
            product_ids = results.get("ids", [[]])[0]
            product_names = [meta.get("name", "") for meta in results.get("metadatas", [[]])[0]]
        except Exception as e:
            logger.error(f"ChromaDB query error: {e}")
            product_ids = []
            product_names = []

        product_string = "Available products (suggest only when appropriate):\n"
        for pid, name in zip(product_ids, product_names):
            product_string += f"{pid}. {name}\n"

        chat = []
        for message in limited_history:
            role = "user" if message["role"] == "user" else "model"
            chat.append({"role": role, "parts": [message["content"]]})

        chat.append({
            "role": "user",
            "parts": [
                "You are a fashion assistant for women's clothing. "
                "Follow these rules strictly:\n"
                "1. Only recommend products from the list below\n"
                "2. Always include Product ID in format 'Product ID: 123'\n"
                "3. Recommend max 4 products\n"
                "4. Only suggest women's clothing\n\n"
                f"{product_string}\n\n"
                f"User query: {request.prompt}"
            ]
        })

        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(contents=chat)
        response_text = response.text

        matched_ids = re.findall(r'Product ID:\s*(\d{1,6})', response_text)
        logger.info(f"Matched product IDs: {matched_ids}")

        matched_products = []
        if matched_ids:
            try:
                products_data = collection.get(ids=[str(pid) for pid in matched_ids])
                matched_products = products_data.get("metadatas", [])
            except Exception as e:
                logger.error(f"Failed to fetch matched product metadata: {e}")

        cleaned_response = re.sub(r'\n?Product ID:\s*\d{1,6}', '', response_text).strip()

        return {
            "response": cleaned_response,
            "products": matched_products
        }

    except Exception as e:
        logger.error(f"Chatbot response generation failed: {e}")
        return {
            "response": "I apologize, but I'm having trouble finding products right now. Please try again.",
            "products": []
        }

# -------------------- Generate Response Endpoint --------------------
@app.post("/generate-response")
async def generate_response(request: PromptRequest, collection=Depends(get_chroma_collection)):
    """
    Original chatbot endpoint - now uses the extracted function
    """
    return await generate_chatbot_response(request, collection)

# -------------------- Upload File Endpoint --------------------
@app.post("/upload-file")
async def upload_file(file: UploadFile = File(...)):
    logger.info("✅ Upload endpoint hit")
    
    # Validate file type
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Only image files are supported")
    
    try:
        # Step 1: Save uploaded image
        upload_dir = "uploaded_files"
        os.makedirs(upload_dir, exist_ok=True)
        file_location = os.path.join(upload_dir, file.filename)

        with open(file_location, "wb") as f:
            f.write(await file.read())

        logger.info(f"📁 Image saved at {file_location}")

        # Step 2: Extract text using OCR
        extracted_text = extract_text_from_image(file_location)
        logger.info(f"📝 Extracted text from {file.filename} (length: {len(extracted_text)})")

        if not extracted_text or extracted_text.startswith("OCR extraction failed"):
            return {
                "success": False,
                "message": "Failed to extract text from image",
                "filename": file.filename,
                "error": extracted_text
            }

        # Step 3: Process fashion keywords using Gemini
        logger.info("🔍 Processing fashion keywords...")
        fashion_result = await process_fashion_keywords(extracted_text)

        # Step 4: Get the generated product description
        product_description = fashion_result.get("product_description", "")
        if not product_description or fashion_result.get("keywords_found", 0) == 0:
            return {
                "success": False,
                "message": "Uploaded image is not related to clothes. Please try again.",
                "filename": file.filename,
                "extracted_text": extracted_text.strip(),
                "fashion_keywords": fashion_result.get("keywords", []),
                "keywords_count": fashion_result.get("keywords_found", 0),
                "generated_description": product_description,
                "chatbot_response": "",
                "recommended_products": [],
                "total_products": 0,
                "keyword_detection_success": False
            }
        
        if not product_description:
            return {
                "success": False,
                "message": "Failed to generate product description from uploaded image",
                "filename": file.filename,
                "error": "No product description generated"
            }

        # Step 5: Send the generated description to chatbot as user message
        logger.info("🤖 Sending generated description to chatbot...")
        logger.info(f"📝 Description being sent: {product_description}")
        
        # Create a PromptRequest with the generated description
        chatbot_request = PromptRequest(
            prompt=product_description,
            chat_history=[],  # Start fresh conversation
            session_id=f"upload_{file.filename}_{hash(file.filename) % 10000}"  # Unique session ID
        )
        
        # Get ChromaDB collection
        collection = get_chroma_collection()
        
        # Call the existing chatbot endpoint logic
        chatbot_response = await generate_chatbot_response(chatbot_request, collection)

        # Step 6: Return combined response
        return {
            "success": True,
            "message": "Image processed and product recommendations generated",
            "filename": file.filename,
            "extracted_text": extracted_text.strip(),
            "fashion_keywords": fashion_result.get("keywords", []),
            "keywords_count": fashion_result.get("keywords_found", 0),
            "generated_description": product_description,
            "chatbot_response": "Here are some product recommendations based on your image",
            "recommended_products": chatbot_response.get("products", []),
            "total_products": len(chatbot_response.get("products", [])),
            "keyword_detection_success": fashion_result.get("success", False)
        }

    except Exception as e:
        logger.error(f"❌ Upload or processing failed: {e}")
        raise HTTPException(status_code=500, detail=f"Image processing failed: {str(e)}")