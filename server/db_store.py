# import json
# import logging
# import os
# import time
# from typing import List, Dict, Any

# import chromadb
# from chromadb.config import Settings
# from dotenv import load_dotenv

# # Configure logging
# logging.basicConfig(
#     level=logging.INFO,
#     format='%(asctime)s - %(levelname)s - %(message)s'
# )
# logger = logging.getLogger(__name__)

# # Load environment variables
# load_dotenv()

# def load_products(file_path: str) -> List[Dict[str, Any]]:
#     """Load products from a JSON file."""
#     try:
#         with open(file_path, 'r', encoding='utf-8') as f:
#             products = json.load(f)
#         logger.info(f"Loaded {len(products)} products")
#         return products
#     except Exception as e:
#         logger.error(f"Failed to load products: {str(e)}")
#         raise

# def clean_metadata_value(value: Any) -> Any:
#     """Clean a single metadata value to be compatible with ChromaDB."""
#     if value is None:
#         return ""
#     elif isinstance(value, (bool, int, float, str)):
#         return value
#     else:
#         return str(value)

# def clean_metadata(metadata_dict: Dict[str, Any]) -> Dict[str, Any]:
#     """Clean all metadata values to be compatible with ChromaDB."""
#     return {k: clean_metadata_value(v) for k, v in metadata_dict.items()}

# def process_batch(collection: chromadb.Collection, batch: List[Dict[str, Any]]) -> None:
#     """Process a batch of products and add them to the ChromaDB collection."""
#     ids = []
#     documents = []
#     metadatas = []
    
#     for product in batch:
#         try:
#             # Required fields
#             product_id = str(product.get("id", ""))
#             description = product.get("description", "") or ""
            
#             # Prepare metadata
#             metadata = {
#                 "name": product.get("name", ""),
#                 "brand": product.get("brand", ""),
#                 "price": float(product.get("price", 0)) if product.get("price") is not None else 0.0,
#                 "currency": product.get("currency", ""),
#                 "category": product.get("category", ""),
#                 "url": product.get("url", ""),
#                 "image_url": product.get("image_url", ""),
#                 "availability": product.get("availability", ""),
#                 # Add other fields as needed
#             }
            
#             # Clean metadata
#             cleaned_metadata = clean_metadata(metadata)
            
#             ids.append(product_id)
#             documents.append(description)
#             metadatas.append(cleaned_metadata)
            
#         except Exception as e:
#             logger.error(f"Error processing product {product.get('id', 'unknown')}: {str(e)}")
#             logger.error(f"Problematic product data: {product}")
#             raise

#     try:
#         collection.add(
#             ids=ids,
#             documents=documents,
#             metadatas=metadatas
#         )
#     except Exception as e:
#         logger.error(f"Failed to add batch: {str(e)}")
#         logger.error("Batch contents:")
#         for i, (id_, doc, meta) in enumerate(zip(ids, documents, metadatas)):
#             logger.error(f"Item {i}: ID={id_}, Doc={doc[:50]}..., Meta={meta}")
#         raise

# def main():
#     """Main function to load products and store them in ChromaDB."""
#     try:
#         # Load products
#         products = load_products("Fashion_Dataset.json")
        
#         # Initialize ChromaDB client
#         client = chromadb.Client(Settings(
#             chroma_db_impl="duckdb+parquet",
#             persist_directory="chroma_db"
#         ))
        
#         # Create or get collection
#         collection = client.create_collection(
#             name="fashion_products",
#             metadata={"hnsw:space": "cosine"}
#         )
#         logger.info("Created new ChromaDB collection")
        
#         # Process products in batches
#         batch_size = 100
#         total_products = len(products)
#         start_time = time.time()
        
#         for i in range(0, total_products, batch_size):
#             batch = products[i:i + batch_size]
#             try:
#                 process_batch(collection, batch)
#                 elapsed = time.time() - start_time
#                 remaining = (total_products - i) / batch_size * (elapsed / (i / batch_size + 1))
#                 logger.info(
#                     f"Processed {min(i + batch_size, total_products)}/{total_products} products "
#                     f"({(i + batch_size)/total_products:.1%}). "
#                     f"Elapsed: {elapsed:.1f}s, Remaining: {remaining:.1f}s"
#                 )
#             except Exception as e:
#                 logger.error(f"Failed to process batch starting at index {i}")
#                 raise
        
#         # Persist the database
#         client.persist()
#         logger.info("Successfully stored all products in ChromaDB")
        
#     except Exception as e:
#         logger.error(f"Fatal error: {str(e)}")
#         raise

# if __name__ == "__main__":
#     main()

import json
import chromadb
from chromadb.utils.embedding_functions import EmbeddingFunction
import os
from dotenv import load_dotenv
import logging
import google.generativeai as genai

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    logger.error("Error: GEMINI_API_KEY environment variable not set.")
    exit(1)
genai.configure(api_key=GEMINI_API_KEY)

# Load products from Fashion_Dataset.json
try:
    with open('Fashion_Dataset.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
        if isinstance(data, dict):
            products = data.get("Sheet1", [])
            logger.info("Loaded products from key 'Sheet1'.")
        elif isinstance(data, list):
            products = data
            logger.info("Loaded products as a list.")
        else:
            logger.error("Unexpected JSON format.")
            exit(1)
except Exception as e:
    logger.error(f"Error loading JSON: {e}")
    exit(1)

# Format each product into searchable doc
def format_product(product):
    brand = product.get("brand", "")
    name = product.get("name", "") or product.get("Title", "")
    price = product.get("price", "") or product.get("Price", "")
    desc = product.get("description", "")
    image = product.get("image", "")
    color = product.get("color", "")
    formatted = (
        f"Product: {name}. URL: {brand}. brand: {price}. "
        f"description: {desc}. Image: {image}. color: {color}."
    )
    if not name:
        logger.warning(f"Product missing name: {product}")
    return formatted.strip()

# Sanitize metadata flat
def sanitize_metadata(data, parent_key='', sep='_'):
    sanitized = {}
    if not isinstance(data, dict):
        return sanitized
    for k, v in data.items():
        key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            sanitized.update(sanitize_metadata(v, key, sep))
        elif isinstance(v, list):
            sanitized[key] = ", ".join(str(item) for item in v if item is not None)
        elif v is None:
            sanitized[key] = ""
        else:
            sanitized[key] = v
    return sanitized

# Define Gemini embedding function
# Define Gemini embedding function
class GeminiEmbeddingFunction(EmbeddingFunction):
    def __init__(self, model_name="models/embedding-001", task_type="RETRIEVAL_DOCUMENT"):
        self.model = model_name
        self.task_type = task_type

    def __call__(self, input_texts):
        try:
            # Handle single string input
            if isinstance(input_texts, str):
                input_texts = [input_texts]
                
            resp = genai.embed_content(
                model=self.model,
                content=input_texts,
                task_type=self.task_type
            )
            # The response contains 'embedding' (singular) not 'embeddings'
            if isinstance(input_texts, list):
                return [embedding for embedding in resp['embedding']]
            return resp['embedding']
        except Exception as e:
            logger.error(f"Gemini embedding error: {e}")
            raise

# Initialize embedding function
embedding_func = GeminiEmbeddingFunction(
    model_name=os.getenv("GEMINI_MODEL_NAME", "models/embedding-001"),
    task_type="RETRIEVAL_DOCUMENT"
)

# Initialize local ChromaDB client
try:
    client = chromadb.PersistentClient(path="./chroma_db")
    logger.info("Initialized local ChromaDB client.")
except Exception as e:
    logger.error(f"Failed to initialize local ChromaDB: {e}")
    exit(1)

# Create or recreate collection
collection_name = "Clothes_products"
try:
    existing = client.list_collections()
    if any(col.name == collection_name for col in existing):
        client.delete_collection(collection_name)
        logger.info(f"Deleted existing collection: {collection_name}")
    # Create collection WITHOUT embedding function
    collection = client.create_collection(collection_name)
    logger.info(f"Created new collection: {collection_name}")
except Exception as e:
    logger.error(f"Collection setup error: {e}")
    exit(1)

# Add products in batches with manual embeddings
batch_size = 100
documents, metadatas, ids = [], [], []
try:
    for i, product in enumerate(products):
        seq_id = i + 1
        doc = format_product(product)
        sanitized = sanitize_metadata(product)
        sanitized["seq_id"] = seq_id
        # Store document in metadata for retrieval
        sanitized["document"] = doc
        
        documents.append(doc)
        metadatas.append(sanitized)
        ids.append(str(seq_id))

        if len(documents) >= batch_size:
            # Manually compute embeddings
            embeddings_list = embedding_func(documents)
            collection.add(
                ids=ids,
                embeddings=embeddings_list,
                metadatas=metadatas
            )
            logger.info(f"Added batch of {len(documents)} products.")
            documents, metadatas, ids = [], [], []

    if documents:
        embeddings_list = embedding_func(documents)
        collection.add(
            ids=ids,
            embeddings=embeddings_list,
            metadatas=metadatas
        )
        logger.info(f"Added final batch of {len(documents)} products.")
    logger.info("All products successfully added!")
except Exception as e:
    logger.exception(f"Error adding products: {e}")  # Detailed traceback
    exit(1)

# List all collections
cols = client.list_collections()
logger.info("Available collections:")
for col in cols:
    logger.info(col.name)