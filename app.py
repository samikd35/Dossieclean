import os
import json
import uuid
from datetime import datetime
from flask import Flask, render_template, request, jsonify, redirect, url_for, send_file, session, flash
from werkzeug.utils import secure_filename
import openai
from io import BytesIO
from urllib.parse import quote_plus
from dotenv import load_dotenv
import PyPDF2
import requests  # For Qdrant API calls
import logging
import urllib.parse
import random
import time
import sys
from PyPDF2 import PdfReader
from flask.json.provider import DefaultJSONProvider
from qdrant_client import QdrantClient
from qdrant_client.http import models as qdrant_models
from azure.storage.blob import BlobServiceClient, ContentSettings
import re
import base64

# Configure logging
logger = logging.getLogger("dossieclean")
logger.setLevel(logging.INFO)
logger.propagate = False

# Configure file handler
file_handler = logging.FileHandler("dossieclean.log")
file_handler.setLevel(logging.INFO)

# Configure console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

# Create formatter
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

# Add handlers to logger once (pytest/imports can load this module multiple times)
if not logger.handlers:
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

# Set Azure storage logging to WARNING level to avoid request/response logs
logging.getLogger('azure').setLevel(logging.WARNING)
logging.getLogger('azure.core.pipeline.policies.http_logging_policy').setLevel(logging.WARNING)

# Define ASCII alternatives for symbols
SUCCESS_SYMBOL = "[SUCCESS]"  # Instead of 
ERROR_SYMBOL = "[ERROR]"      # Instead of 
WARNING_SYMBOL = "[WARNING]"  # Instead of 

# Log startup information
logger.info("=" * 50)
logger.info("Starting DossieClean application")
logger.info("=" * 50)

# Load environment variables from .env file
load_dotenv()

# Custom JSONEncoder to handle MongoDB ObjectId
class CustomJSONEncoder(DefaultJSONProvider):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)

# Initialize Flask app
app = Flask(__name__)

secret_key = os.environ.get("SECRET_KEY")
if not secret_key:
    secret_key = os.urandom(32).hex()
    logger.warning(
        WARNING_SYMBOL
        + " SECRET_KEY is not set. Using an ephemeral key; sessions will reset on restart."
    )

app.config["SECRET_KEY"] = secret_key
app.config["UPLOAD_FOLDER"] = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
try:
    max_upload_size_mb = int(os.environ.get("MAX_UPLOAD_SIZE_MB", "100"))
except ValueError:
    max_upload_size_mb = 100
    logger.warning(
        WARNING_SYMBOL + " MAX_UPLOAD_SIZE_MB is invalid. Falling back to 100 MB."
    )
app.config["MAX_CONTENT_LENGTH"] = max_upload_size_mb * 1024 * 1024

# Configure Flask's logging to hide repetitive API polling logs
class FilterPollRequests(logging.Filter):
    def filter(self, record):
        # Filter out polling requests to batch status and logs endpoints
        if (
            'GET /api/batch_status/' in record.getMessage() or
            'GET /api/batch_logs/' in record.getMessage()
        ):
            return False
        return True

# Apply the filter to the Werkzeug logger
logging.getLogger('werkzeug').addFilter(FilterPollRequests())

app.config["ALLOWED_EXTENSIONS"] = {"pdf"}  # Only allow PDF files
app.config["CHUNK_SIZE"] = int(os.environ.get("CHUNK_SIZE", "512"))
app.config["CHUNK_OVERLAP"] = int(os.environ.get("CHUNK_OVERLAP", "50"))
app.json_encoder = CustomJSONEncoder  # Use our custom encoder

# Function to check if file has allowed extension
def allowed_file(filename):
    """Check if file has an allowed extension"""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in app.config["ALLOWED_EXTENSIONS"]

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

# Set up OpenAI API key
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    print("WARNING: OPENAI_API_KEY not set in environment variables")
else:
    # Updated for OpenAI API >= 1.0.0
    openai.api_key = OPENAI_API_KEY
    os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY

# Define metadata extraction prompt
metadata_prompt = """From the provided PDF content, extract the following metadata and return it as a valid JSON string:
- title: The main title of the document (e.g., from a heading).
- authors: A list of author names in "Last Name, Initial(s)" format (e.g., "Gebrehiwot, G.").
- year: The publication year in YYYY format (e.g., "2011").
- journal_or_university: The institution or journal name (e.g., "Addis Ababa University").
- department: The department, if mentioned.
- volume: The volume number, if applicable.
- issue: The issue number, if applicable.
- pages: The page range (e.g., "120-130"), if applicable.
- doi: The DOI, if present.
- abstract: The abstract text, if present.
- keywords: A list of keywords, if provided or inferred from context.
- document_type: The type of document (e.g., "thesis", "journal article", "report").

If a field is not found, use an empty string "" or empty list [] as appropriate.
Return the result as a JSON object.
"""

# Storage clients are initialized lazily or during startup, depending on environment.
qdrant_client = None
blob_service_client = None
container_client = None
collection_name = os.environ.get("COLLECTION_NAME", "AAU_PDF")

# Helper function to upload PDF to Azure Blob Storage
def upload_pdf_to_azure(file_path, metadata):
    """
    Upload a PDF file to Azure Blob Storage and return the blob URL
    """
    global container_client, blob_service_client
    
    # Check if container_client is defined, if not try to initialize it
    if 'container_client' not in globals() or container_client is None:
        logger.warning(WARNING_SYMBOL + " [AZURE] container_client is not initialized, attempting to initialize Azure connection")
        try:
            # Get Azure settings
            azure_connection_string = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
            azure_container_name = os.environ.get("AZURE_CONTAINER_NAME")
            
            if not azure_connection_string or not azure_container_name:
                raise Exception("Azure connection string or container name not set in environment variables")
                
            # Initialize the blob service client
            if 'blob_service_client' not in globals() or blob_service_client is None:
                blob_service_client = BlobServiceClient.from_connection_string(azure_connection_string)
            
            # Initialize the container client
            container_client = blob_service_client.get_container_client(azure_container_name)
            logger.info(SUCCESS_SYMBOL + " [AZURE] Successfully initialized container client")
        except Exception as init_error:
            logger.error(ERROR_SYMBOL + f" [AZURE] Failed to initialize container client: {str(init_error)}")
            return {
                "success": False,
                "error": f"Failed to initialize Azure container client: {str(init_error)}"
            }
    try:
        # Format filename: title_authorLastName_year.pdf
        # Get primary author last name (if available)
        author_name = "unknown"
        if metadata.get("authors") and len(metadata["authors"]) > 0:
            # Extract last name from first author
            first_author = metadata["authors"][0]
            if "," in first_author:
                author_name = first_author.split(",")[0].strip().lower()
            else:
                # Just use the whole name if no comma
                author_name = first_author.split()[0].lower()
        
        # Clean title for filename
        title_part = metadata.get("title", "untitled")
        title_part = "".join(c if c.isalnum() or c == " " else "_" for c in title_part)
        title_part = title_part.strip().replace(" ", "_").lower()[:50]  # Limit length
        
        # Get year or use current year
        year_part = metadata.get("year", datetime.now().strftime("%Y"))
        
        # Create standardized filename
        blob_name = f"{title_part}_{author_name}_{year_part}.pdf"
        
        logger.info(f"[AZURE] Preparing to upload file to Azure Blob Storage as: {blob_name}")
        
        # Get file size
        file_size = os.path.getsize(file_path)
        logger.info(f"[AZURE] File size: {file_size} bytes")
        
        # Configuration for upload
        max_retries = 3
        chunk_size = 4 * 1024 * 1024  # 4MB chunks
        timeout = 300  # seconds
        
        # Check if container_client is available
        if container_client is None:
            logger.error(ERROR_SYMBOL + " [AZURE] Container client is not available")
            return {
                "success": False,
                "error": "Azure container client is not properly initialized"
            }
            
        # Upload to Azure
        logger.info(f"[AZURE] Creating blob client for container: {os.environ.get('AZURE_CONTAINER_NAME')}")
        blob_client = container_client.get_blob_client(blob_name)
        content_settings = ContentSettings(content_type="application/pdf")
        
        # For large files (> 10MB), use chunked uploading
        if file_size > 10 * 1024 * 1024:
            logger.info(f"[AZURE] Large file detected ({file_size/1024/1024:.2f} MB). Using chunked upload with {chunk_size/1024/1024:.2f} MB chunks")
            
            retry_count = 0
            success = False
            
            while retry_count < max_retries and not success:
                try:
                    # Use block blob upload pattern for large files
                    block_list = []
                    
                    with open(file_path, "rb") as pdf_file:
                        # Upload chunks as blocks
                        total_chunks = (file_size + chunk_size - 1) // chunk_size
                        chunks_uploaded = 0
                        
                        for i in range(0, file_size, chunk_size):
                            # Create a unique block ID for each chunk
                            block_id = f"{i:032d}"
                            block_id_encoded = block_id.encode("utf-8")
                            block_id_base64 = base64.b64encode(block_id_encoded).decode("utf-8")
                            
                            # Read chunk
                            chunk = pdf_file.read(chunk_size)
                            chunks_uploaded += 1
                            
                            if chunks_uploaded % 5 == 0 or chunks_uploaded == total_chunks:
                                logger.info(f"[AZURE] Uploading chunk {chunks_uploaded}/{total_chunks} ({chunks_uploaded/total_chunks*100:.1f}%)")
                            
                            # Upload the block
                            blob_client.stage_block(
                                block_id=block_id_base64,
                                data=chunk,
                                timeout=timeout
                            )
                            
                            # Add the block ID to our list
                            block_list.append(block_id_base64)
                    
                    # Commit the block list to create the blob
                    logger.info(f"[AZURE] Committing block list with {len(block_list)} blocks")
                    blob_client.commit_block_list(
                        block_list=block_list,
                        content_settings=content_settings,
                        timeout=timeout
                    )
                    
                    success = True
                    logger.info(f"[AZURE] Chunked upload completed successfully after {retry_count + 1} attempts")
                
                except Exception as chunk_error:
                    retry_count += 1
                    if retry_count < max_retries:
                        logger.warning(f"{WARNING_SYMBOL} [AZURE] Chunked upload attempt {retry_count} failed: {str(chunk_error)}. Retrying...")
                        time.sleep(2 ** retry_count)  # Exponential backoff
                    else:
                        raise Exception(f"Failed chunked upload after {max_retries} attempts: {str(chunk_error)}")
        else:
            # For smaller files, use regular upload
            logger.info(f"[AZURE] Uploading PDF content to Azure Blob Storage...")
            
            retry_count = 0
            success = False
            
            while retry_count < max_retries and not success:
                try:
                    with open(file_path, "rb") as pdf_file:
                        pdf_content = pdf_file.read()
                        blob_client.upload_blob(
                            data=pdf_content, 
                            overwrite=True, 
                            content_settings=content_settings,
                            timeout=timeout
                        )
                    success = True
                    logger.info(f"[AZURE] Regular upload completed successfully after {retry_count + 1} attempts")
                
                except Exception as upload_error:
                    retry_count += 1
                    if retry_count < max_retries:
                        logger.warning(f"{WARNING_SYMBOL} [AZURE] Upload attempt {retry_count} failed: {str(upload_error)}. Retrying...")
                        time.sleep(2 ** retry_count)  # Exponential backoff
                    else:
                        raise Exception(f"Failed upload after {max_retries} attempts: {str(upload_error)}")
        
        # Get the URL
        blob_url = blob_client.url
        
        logger.info(SUCCESS_SYMBOL + f" [AZURE] PDF successfully uploaded to Azure Blob Storage")
        logger.info(f"[AZURE] Blob name: {blob_name}")
        logger.info(f"[AZURE] Blob URL: {blob_url}")
        
        return {
            "success": True,
            "blob_url": blob_url,
            "blob_name": blob_name
        }
    
    except Exception as e:
        logger.error(ERROR_SYMBOL + f" [AZURE] Error uploading PDF to Azure Blob Storage: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

# Helper function to save document data to Qdrant
def save_document_metadata(doc_id, metadata):
    """Save document metadata to Qdrant (used for metadata-only operations)"""
    try:
        logger.info(f"[QDRANT] Saving document metadata for {doc_id}")
        
        # Generate a valid UUID for Qdrant point ID
        qdrant_point_id = str(uuid.uuid4())
        
        # Ensure we have a default embedding (zero vector)
        embedding = [0.0] * 1536  # Default dimension for Ada embeddings
        
        # Store document metadata in Qdrant
        result = qdrant_client.upsert(
            collection_name=collection_name,
            points=[
                qdrant_models.PointStruct(
                    id=qdrant_point_id,
                    vector=embedding,
                    payload={
                        "document_id": doc_id,
                        "title": metadata.get("title", "Untitled"),
                        "authors": metadata.get("authors", []),
                        "year": metadata.get("year", ""),
                        "journal_or_university": metadata.get("journal_or_university", ""),
                        "department": metadata.get("department", ""),
                        "abstract": metadata.get("abstract", ""),
                        "keywords": metadata.get("keywords", []),
                        "document_type": metadata.get("document_type", ""),
                        "page_count": metadata.get("page_count", 0),
                        "file_size_kb": metadata.get("file_size_kb", 0),
                        "azure_url": metadata.get("azure_url", ""),
                        "is_chunk": False,
                        "upload_date": metadata.get("upload_date", datetime.now().isoformat())
                    }
                )
            ]
        )
        
        logger.info(f"{SUCCESS_SYMBOL} [QDRANT] Successfully saved document metadata")
        return {"success": True}
    
    except Exception as e:
        logger.error(f"{ERROR_SYMBOL} [QDRANT] Error saving document metadata: {str(e)}")
        return {"success": False, "message": str(e)}

def extract_text_from_pdf(file_path):
    """Extract text from PDF file using PyPDF2, processing page by page to reduce memory usage"""
    text = ""
    try:
        # Don't load the entire file at once
        reader = PyPDF2.PdfReader(file_path)
        total_pages = len(reader.pages)
        
        logger.info(f"[PROCESSING] Extracting text from PDF with {total_pages} pages")
        
        # Process pages in batches to reduce memory usage
        batch_size = 10
        for batch_start in range(0, total_pages, batch_size):
            batch_end = min(batch_start + batch_size, total_pages)
            logger.info(f"[PROCESSING] Extracting text from pages {batch_start+1}-{batch_end} of {total_pages}")
            
            batch_text = ""
            for page_num in range(batch_start, batch_end):
                page = reader.pages[page_num]
                batch_text += page.extract_text() + "\n\n"
            
            # Append batch text to the overall text
            text += batch_text
            
            # Force garbage collection to free memory
            import gc
            gc.collect()
            
        return text
    except Exception as e:
        logger.error(ERROR_SYMBOL + f" Error extracting text from PDF: {e}")
        return ""

def extract_text_from_memory(file_stream):
    """Extract text from PDF file in memory using PyPDF2"""
    text = ""
    try:
        reader = PdfReader(file_stream)
        for page_num in range(len(reader.pages)):
            page = reader.pages[page_num]
            text += page.extract_text() + "\n\n"
        return text
    except Exception as e:
        logger.error(ERROR_SYMBOL + f" Error extracting text from PDF in memory: {e}")
        return ""

def chunk_text(text, max_tokens=4000):
    """Split text into chunks of max_tokens"""
    logger.info(f"Starting text chunking process with max_tokens={max_tokens}")
    
    # Simple chunking by character count (approximate tokens)
    # Assuming 4 chars per token on average
    max_chars = max_tokens * 4
    
    # Split text into paragraphs
    paragraphs = text.split('\n')
    logger.info(f"Text split into {len(paragraphs)} paragraphs")
    
    chunks = []
    current_chunk = ""
    
    for paragraph in paragraphs:
        # If adding this paragraph would exceed the max_chars, start a new chunk
        if len(current_chunk) + len(paragraph) > max_chars and current_chunk:
            chunks.append(current_chunk.strip())
            current_chunk = paragraph
        else:
            if current_chunk:
                current_chunk += "\n" + paragraph
            else:
                current_chunk = paragraph
    
    # Add the last chunk if it's not empty
    if current_chunk:
        chunks.append(current_chunk.strip())
    
    logger.info(f"Chunking complete: Created {len(chunks)} chunks from text")
    return chunks

def count_pages(file_path):
    """Count the number of pages in a PDF file"""
    try:
        with open(file_path, "rb") as file:
            reader = PyPDF2.PdfReader(file)
            return len(reader.pages)
    except Exception as e:
        logger.error(ERROR_SYMBOL + f" Error counting pages: {e}")
        return 0

def get_pdf_page_count_from_memory(file_stream):
    """Count the number of pages in a PDF file in memory"""
    try:
        reader = PdfReader(file_stream)
        return len(reader.pages)
    except Exception as e:
        logger.error(ERROR_SYMBOL + f" Error counting pages from memory: {e}")
        return 0

def extract_metadata_from_pdf(file_path):
    """Extract metadata from a PDF file using OpenAI"""
    try:
        # Extract text from the first few pages for metadata
        text = ""
        try:
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                # Get text from first 5 pages or all pages if less than 5
                max_pages = min(5, len(pdf_reader.pages))
                for i in range(max_pages):
                    page = pdf_reader.pages[i]
                    text += page.extract_text()
                
                # Truncate text if too long
                text = truncate_text(text, max_length=8000)
        except Exception as e:
            logger.error(ERROR_SYMBOL + f" Error extracting text for metadata: {e}")
            text = "Error extracting text from PDF"
        
        # Get file info
        file_stats = os.stat(file_path)
        file_size_kb = file_stats.st_size / 1024
        page_count = count_pages(file_path)
        
        # Use OpenAI to extract metadata - Updated for OpenAI API >= 1.0.0
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": metadata_prompt},
                {"role": "user", "content": text}
            ],
            temperature=0.3,
            max_tokens=1000
        )
        
        # Extract JSON from response
        metadata_text = response.choices[0].message.content.strip()
        
        # Find JSON part in the response
        json_start = metadata_text.find('{')
        json_end = metadata_text.rfind('}') + 1
        
        if json_start >= 0 and json_end > json_start:
            metadata_json = metadata_text[json_start:json_end]
            try:
                metadata = json.loads(metadata_json)
            except json.JSONDecodeError:
                logger.error(ERROR_SYMBOL + f" Error parsing metadata JSON: {metadata_json}")
                metadata = {}
        else:
            logger.error(ERROR_SYMBOL + f" No valid JSON found in response: {metadata_text}")
            metadata = {}
        
        # Add file info to metadata
        metadata["page_count"] = page_count
        metadata["file_size_kb"] = round(file_size_kb, 2)
        metadata["extraction_date"] = datetime.now().strftime("%Y-%m-%d")
        
        return metadata
    except Exception as e:
        logger.error(ERROR_SYMBOL + f" Error extracting metadata from PDF: {str(e)}")
        return {
            "title": os.path.basename(file_path),
            "authors": [],
            "year": "",
            "abstract": "",
            "keywords": [],
            "page_count": 0,
            "extraction_date": datetime.now().strftime("%Y-%m-%d")
        }

def extract_metadata_from_memory(file_stream, extraction_method, filename):
    """Extract metadata from a PDF file in memory using the specified method"""
    logger.info(f"Extracting metadata using method: {extraction_method}")
    
    if extraction_method == "auto":
        # Use the OpenAI-based extraction
        return extract_metadata_from_pdf_in_memory(file_stream, filename)
    elif extraction_method == "filename":
        # Extract metadata from filename (assuming format like "Author - Title (Year).pdf")
        filename = os.path.basename(filename)
        filename = os.path.splitext(filename)[0]  # Remove extension
        
        # Default metadata
        metadata = {
            "title": filename,
            "authors": [],
            "year": "",
            "journal_or_university": "",
            "department": "",
            "document_type": "unknown"
        }
        
        # Try to parse filename patterns
        try:
            # Check for "Author - Title (Year)" pattern
            if " - " in filename and "(" in filename and ")" in filename:
                author, rest = filename.split(" - ", 1)
                title_year = rest.split("(", 1)
                title = title_year[0].strip()
                year = title_year[1].split(")", 1)[0].strip()
                
                metadata["title"] = title
                metadata["authors"] = [author.strip()]
                metadata["year"] = year
            # Check for "Title - Author (Year)" pattern
            elif " - " in filename and "(" in filename and ")" in filename:
                title, rest = filename.split(" - ", 1)
                author_year = rest.split("(", 1)
                author = author_year[0].strip()
                year = author_year[1].split(")", 1)[0].strip()
                
                metadata["title"] = title
                metadata["authors"] = [author]
                metadata["year"] = year
        except Exception as e:
            logger.warning(ERROR_SYMBOL + f" Error parsing filename for metadata: {str(e)}")
        
        return metadata
    else:
        # Default to basic metadata
        logger.warning(ERROR_SYMBOL + f" Unknown extraction method: {extraction_method}. Using basic metadata.")
        filename = os.path.basename(filename)
        return {
            "title": os.path.splitext(filename)[0],
            "authors": [],
            "year": "",
            "journal_or_university": "",
            "department": "",
            "volume": "",
            "issue": "",
            "pages": "",
            "doi": "",
            "abstract": "",
            "keywords": [],
            "document_type": "unknown"
        }

def extract_metadata_from_pdf_in_memory(file_stream, filename):
    """Extract metadata from a PDF file in memory using OpenAI"""
    try:
        # Extract text from the first few pages for metadata
        text = ""
        try:
            reader = PdfReader(file_stream)
            # Get text from first 5 pages or all pages if less than 5
            max_pages = min(5, len(reader.pages))
            for i in range(max_pages):
                page = reader.pages[i]
                text += page.extract_text()
            
            # Truncate text if too long
            text = truncate_text(text, max_length=8000)
        except Exception as e:
            logger.error(ERROR_SYMBOL + f" Error extracting text for metadata: {e}")
            text = "Error extracting text from PDF"
        
        # Get file info
        file_stream.seek(0, os.SEEK_END)
        file_size_kb = file_stream.tell() / 1024
        file_stream.seek(0)  # Reset stream position
        page_count = get_pdf_page_count_from_memory(file_stream)
        
        # Use OpenAI to extract metadata - Updated for OpenAI API >= 1.0.0
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": metadata_prompt},
                {"role": "user", "content": text}
            ],
            temperature=0.3,
            max_tokens=1000
        )
        
        # Extract JSON from response
        metadata_text = response.choices[0].message.content.strip()
        
        # Find JSON part in the response
        json_start = metadata_text.find('{')
        json_end = metadata_text.rfind('}') + 1
        
        if json_start >= 0 and json_end > json_start:
            metadata_json = metadata_text[json_start:json_end]
            try:
                metadata = json.loads(metadata_json)
            except json.JSONDecodeError:
                logger.error(ERROR_SYMBOL + f" Error parsing metadata JSON: {metadata_json}")
                metadata = {}
        else:
            logger.error(ERROR_SYMBOL + f" No valid JSON found in response: {metadata_text}")
            metadata = {}
        
        # Add file info to metadata
        metadata["page_count"] = page_count
        metadata["file_size_kb"] = round(file_size_kb, 2)
        metadata["extraction_date"] = datetime.now().strftime("%Y-%m-%d")
        
        return metadata
    except Exception as e:
        logger.error(ERROR_SYMBOL + f" Error extracting metadata: {str(e)}")
        # Return basic metadata with file info only
        page_count = get_pdf_page_count_from_memory(file_stream)
        file_stream.seek(0, os.SEEK_END)
        file_size_kb = file_stream.tell() / 1024
        
        return {
            "title": "",
            "authors": [],
            "year": "",
            "journal_or_university": "",
            "department": "",
            "volume": "",
            "issue": "",
            "pages": "",
            "doi": "",
            "abstract": "",
            "keywords": [],
            "document_type": "",
            "page_count": page_count,
            "file_size_kb": round(file_size_kb, 2),
            "extraction_date": datetime.now().strftime("%Y-%m-%d")
        }

def generate_embedding(text, max_tokens=8000):
    """Generate an embedding for the given text, with chunking for large documents."""
    try:
        # Estimate token count (roughly 4 chars per token)
        estimated_tokens = len(text) // 4
        
        if estimated_tokens > max_tokens:
            logger.warning(f"[EMBEDDING] Text too large ({estimated_tokens} estimated tokens), truncating to {max_tokens} tokens")
            # Truncate text to approximately the max token limit
            text = text[:max_tokens * 4]
            
        logger.info(f"[EMBEDDING] Generating embedding for text of length {len(text)} characters (~{len(text)//4} tokens)")
        
        # Using the newer OpenAI API format (v1.0.0+)
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        response = client.embeddings.create(
            input=text,
            model="text-embedding-3-small"
        )
        
        embedding = response.data[0].embedding
        logger.info(f"{SUCCESS_SYMBOL} [EMBEDDING] Successfully generated embedding of dimension {len(embedding)}")
        return embedding
    except Exception as e:
        logger.error(f"{ERROR_SYMBOL} [EMBEDDING] Error generating embedding: {e}")
        # Return a zero vector as fallback
        return [0.0] * 1536  # OpenAI ada embeddings are 1536 dimensions

def truncate_text(text, max_length=8000):
    """Truncate text to a maximum length while trying to preserve meaningful content."""
    if len(text) <= max_length:
        return text
    
    # Simply truncate to the max length
    truncated = text[:max_length]
    logger.info(f"[PROCESSING] Truncated text from {len(text)} to {len(truncated)} characters")
    return truncated

def save_pdf_to_db(file_path, metadata):
    """Process and save PDF document to Azure and Qdrant"""
    try:
        doc_id = metadata.get("document_id", str(uuid.uuid4()))
        
        # Ensure doc_id is a valid UUID for Qdrant
        # Store original doc_id in metadata but use a valid UUID for Qdrant point ID
        original_doc_id = doc_id
        qdrant_point_id = str(uuid.uuid4())
        
        # 1. Upload PDF to Azure Blob Storage first
        logger.info(f"[AZURE] Uploading PDF to Azure Blob Storage: {os.path.basename(file_path)}")
        azure_upload_result = upload_pdf_to_azure(file_path, metadata)
        
        if not azure_upload_result.get("success", False):
            return {
                "success": False,
                "message": f"Failed to upload PDF to Azure: {azure_upload_result.get('error')}"
            }
        
        logger.info(f"{SUCCESS_SYMBOL} [AZURE] PDF successfully uploaded to Azure Blob Storage")
        
        # 2. Extract text and metadata from PDF
        logger.info(f"[PROCESSING] Extracting text from PDF file: {os.path.basename(file_path)}")
        full_text = extract_text_from_pdf(file_path)
        
        # Get page count
        page_count = count_pages(file_path)
        logger.info(f"[PROCESSING] PDF has {page_count} pages")
        
        # 3. Add Azure blob URL to metadata
        metadata["azure_url"] = azure_upload_result.get("blob_url", "")
        metadata["page_count"] = page_count
        metadata["upload_date"] = datetime.now().isoformat()
        
        # 4. Split text into chunks for embedding
        logger.info("[PROCESSING] Splitting text into chunks...")
        chunk_size = int(os.environ.get("CHUNK_SIZE", 4000))
        logger.info(f"[PROCESSING] Using chunk size: {chunk_size}")
        
        chunks = chunk_text(full_text, chunk_size)
        logger.info(f"[PROCESSING] Created {len(chunks)} chunks")
        
        # 5. Process each chunk: Generate embedding and store in Qdrant
        logger.info(f"[PROCESSING] Processing {len(chunks)} chunks for vector storage...")
        chunk_count = 0
        
        for i, chunk in enumerate(chunks):
            try:
                logger.info(f"[EMBEDDING] Generating embedding for chunk {i+1}/{len(chunks)}")
                chunk_embedding = generate_embedding(chunk)
                
                # Store chunk embedding in Qdrant with document reference and metadata
                qdrant_client.upsert(
                    collection_name=collection_name,
                    points=[
                        qdrant_models.PointStruct(
                            id=str(uuid.uuid4()),
                            vector=chunk_embedding,
                            payload={
                                "page_content": chunk,  # Use page_content as the standard field for text
                                "document_id": original_doc_id,
                                "chunk_index": i,
                                "metadata": {
                                    "title": metadata.get("title", "Untitled"),
                                    "authors": metadata.get("authors", []),
                                    "year": metadata.get("year", ""),
                                    "journal_or_university": metadata.get("journal_or_university", ""),
                                    "department": metadata.get("department", ""),
                                    "azure_url": metadata.get("azure_url", ""),
                                    "is_chunk": True,
                                    "created_at": datetime.now().isoformat()
                                }
                            }
                        )
                    ]
                )
                logger.info(f"[QDRANT] Successfully stored embedding for chunk {i+1}")
                chunk_count += 1
            except Exception as e:
                logger.error(f"{ERROR_SYMBOL} [QDRANT] Error storing chunk embedding: {str(e)}")
        
        # 6. Also store document-level metadata with the first chunk's embedding for document retrieval
        try:
            # Use first chunk for document-level embedding if available
            doc_embedding = None
            if chunks:
                logger.info("[EMBEDDING] Generating embedding for document: " + os.path.basename(file_path))
                doc_embedding = generate_embedding(chunks[0])
                logger.info(f"{SUCCESS_SYMBOL} [EMBEDDING] Successfully generated embedding for document")
                
            # Store document metadata in Qdrant
            logger.info(f"[QDRANT] Saving document metadata with document ID: {original_doc_id}")
            
            # If no embedding could be generated, use zero vector
            if not doc_embedding:
                doc_embedding = [0.0] * 1536  # Default embedding dimension for OpenAI
                
            # Store document metadata with embedding
            qdrant_client.upsert(
                collection_name=collection_name,
                points=[
                    qdrant_models.PointStruct(
                        id=qdrant_point_id,
                        vector=doc_embedding,
                        payload={
                            "page_content": chunks[0] if chunks else "",  # Store first chunk as document content
                            "document_id": original_doc_id,
                            "metadata": {
                                "title": metadata.get("title", "Untitled"),
                                "authors": metadata.get("authors", []),
                                "year": metadata.get("year", ""),
                                "journal_or_university": metadata.get("journal_or_university", ""),
                                "department": metadata.get("department", ""),
                                "abstract": metadata.get("abstract", ""),
                                "keywords": metadata.get("keywords", []),
                                "document_type": metadata.get("document_type", ""),
                                "page_count": metadata.get("page_count", 0),
                                "file_size_kb": metadata.get("file_size_kb", 0),
                                "azure_url": metadata.get("azure_url", ""),
                                "is_chunk": False,  # Mark as document (not chunk)
                                "upload_date": metadata.get("upload_date", datetime.now().isoformat())
                            }
                        }
                    )
                ]
            )
            
            logger.info(f"{SUCCESS_SYMBOL} [QDRANT] Successfully saved document metadata")
        except Exception as e:
            logger.error(f"{ERROR_SYMBOL} [QDRANT] Error saving document metadata: {str(e)}")
            # Continue processing even if document metadata storage fails
                
        logger.info(f"[SUCCESS] Successfully stored {chunk_count} chunk embeddings in vector database")
        logger.info(f"{SUCCESS_SYMBOL} Successfully processed {os.path.basename(file_path)}")
        return {"success": True, "document_id": original_doc_id}
    
    except Exception as e:
        logger.error(f"{ERROR_SYMBOL} Error saving PDF to database: {str(e)}")
        return {"success": False, "message": str(e)}

# Function to initialize storage connections (Azure and Qdrant)
def initialize_storage():
    """Initialize Azure Blob Storage and Qdrant connections"""
    global qdrant_client, collection_name, blob_service_client, container_client
    
    logger.info("=" * 30)
    logger.info("[STORAGE] INITIALIZING STORAGE CONNECTIONS")
    logger.info("=" * 30)
    
    # Initialize variables to avoid undefined references
    qdrant_client = None
    blob_service_client = None
    container_client = None
    collection_name = os.environ.get("COLLECTION_NAME", "AAU_PDF")
    
    try:
        # Set up Qdrant client for vector storage
        qdrant_url = os.environ.get("QDRANT_URL")
        qdrant_api_key = os.environ.get("QDRANT_API_KEY")
        
        if qdrant_url:
            logger.info("[QDRANT] Connecting to Qdrant cloud instance")
            try:
                qdrant_client = QdrantClient(
                    url=qdrant_url,
                    api_key=qdrant_api_key,
                    timeout=60  # Increased timeout for better reliability
                )
                
                # Create collection if it doesn't exist
                vector_size = 1536  # OpenAI embedding dimension
                try:
                    qdrant_client.get_collection(collection_name)
                    logger.info(f"[QDRANT] Collection '{collection_name}' already exists")
                except Exception as collection_error:
                    logger.info(f"[QDRANT] Creating collection '{collection_name}'")
                    try:
                        qdrant_client.create_collection(
                            collection_name=collection_name,
                            vectors_config=qdrant_models.VectorParams(
                                size=vector_size,
                                distance=qdrant_models.Distance.COSINE
                            )
                        )
                    except Exception as create_error:
                        logger.error(ERROR_SYMBOL + f" [QDRANT] Error creating collection: {str(create_error)}")
                        raise
                
                logger.info(SUCCESS_SYMBOL + " [QDRANT] Successfully connected to Qdrant")
            except Exception as qdrant_error:
                logger.error(ERROR_SYMBOL + f" [QDRANT] Error connecting to Qdrant: {str(qdrant_error)}")
                raise
        else:
            logger.error(ERROR_SYMBOL + " [QDRANT] Qdrant URL not found in environment variables")
        
        # Set up Azure Blob Storage
        azure_connection_string = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
        azure_container_name = os.environ.get("AZURE_CONTAINER_NAME")
        
        if azure_connection_string and azure_container_name:
            try:
                logger.info("[AZURE] Connecting to Azure Blob Storage")
                blob_service_client = BlobServiceClient.from_connection_string(azure_connection_string)
                
                # Check if container exists, create if it doesn't
                container_client = blob_service_client.get_container_client(azure_container_name)
                
                try:
                    container_exists = container_client.exists()
                    if not container_exists:
                        logger.info(f"[AZURE] Creating Azure Blob container: {azure_container_name}")
                        container_client.create_container()
                except Exception as container_error:
                    logger.error(ERROR_SYMBOL + f" [AZURE] Container error: {str(container_error)}")
                    # Continue anyway - container might already exist
                
                logger.info(SUCCESS_SYMBOL + " [AZURE] Successfully connected to Azure Blob Storage")
            except Exception as azure_error:
                logger.error(ERROR_SYMBOL + f" [AZURE] Error connecting to Azure Blob Storage: {str(azure_error)}")
                raise
        else:
            logger.error(ERROR_SYMBOL + " [AZURE] Azure Blob Storage connection string or container name not found")
            
    except Exception as e:
        logger.error(ERROR_SYMBOL + f" [STORAGE] Error initializing storage connections: {str(e)}")
        # Don't re-raise the exception to allow the application to continue

# Initialize Azure and Qdrant connections at startup
should_init_storage = os.environ.get("DOSSIECLEAN_INIT_STORAGE", "true").strip().lower()
if should_init_storage not in {"0", "false", "no"}:
    with app.app_context():
        initialize_storage()
else:
    logger.info("[STORAGE] Skipping startup storage initialization (DOSSIECLEAN_INIT_STORAGE=false)")

@app.route("/choose_processing", methods=["GET"])
def choose_processing():
    return render_template("choose_processing.html")

@app.route("/process_files", methods=["POST"])
def process_files():
    processing_option = request.form.get("processing_option")
    if processing_option == "preview":
        return redirect(url_for("upload_file"))
    elif processing_option == "batch":
        return redirect(url_for("batch_upload"))
    else:
        return "Invalid option selected.", 400

@app.route("/batch_upload_form")
def batch_upload_form():
    """Display the batch upload form"""
    return render_template("batch_upload.html")

@app.route("/batch_upload", methods=["POST"])
def batch_upload():
    """First step of batch upload - store files and show batch process screen"""
    if "pdf_files" not in request.files:
        return jsonify({"error": "No files uploaded"}), 400
    
    files = request.files.getlist("pdf_files")
    
    # Initialize batch files data
    batch_files = []
    batch_id = str(uuid.uuid4())
    
    # Create batch status directory if it doesn't exist
    batch_status_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "batch_status")
    os.makedirs(batch_status_dir, exist_ok=True)
    
    # Create uploads directory if it doesn't exist
    uploads_dir = app.config["UPLOAD_FOLDER"]
    os.makedirs(uploads_dir, exist_ok=True)
    
    # Log batch information
    logger.info(f"[BATCH] Processing upload request with {len(files)} files")
    
    for file in files:
        if file.filename == "" or not file.filename.lower().endswith('.pdf'):
            continue
        
        filename = secure_filename(file.filename)
        temp_id = str(uuid.uuid4())
        file_path = os.path.join(uploads_dir, f"{temp_id}_{filename}")
        file.save(file_path)
        
        # Store file info in batch list
        batch_files.append({
            "temp_id": temp_id,
            "original_name": filename,
            "path": file_path
        })
    
    # If no valid files were uploaded, return an error
    if not batch_files:
        return jsonify({"error": "No valid PDF files were uploaded"}), 400
    
    # Store batch manifest in a file instead of session
    batch_manifest = {
        "batch_id": batch_id,
        "created_at": datetime.now().isoformat(),
        "file_count": len(batch_files),
        "files": batch_files
    }
    
    # Save batch manifest to file
    manifest_path = os.path.join(batch_status_dir, f"manifest_{batch_id}.json")
    with open(manifest_path, 'w') as f:
        json.dump(batch_manifest, f)
    
    # Store only the batch ID in session
    session["current_batch_id"] = batch_id
    
    logger.info(f"[BATCH] Created batch manifest with ID {batch_id} containing {len(batch_files)} files")
    
    # Return JSON response for AJAX requests instead of redirecting
    # This allows the upload page to show the progress directly
    return jsonify({
        "success": True,
        "message": f"Uploaded {len(batch_files)} files successfully",
        "batch_id": batch_id,
        "file_count": len(batch_files),
        "files": batch_files
    })

# Initialize log storage for batch processing
batch_logs = {}

@app.route("/api/batch_logs/<batch_id>", methods=["GET"])
def api_batch_logs(batch_id):
    """Get log entries for a batch processing job"""
    try:
        last_entry = int(request.args.get("last_entry", 0))
        
        # Get logs for the batch
        if batch_id not in batch_logs:
            return jsonify({"logs": []})
            
        # Filter logs that are newer than last_entry
        logs = [log for log in batch_logs[batch_id] if log["id"] > last_entry]
        
        return jsonify({"logs": logs})
    except Exception as e:
        logger.error(f"Error getting batch logs: {str(e)}")
        return jsonify({"error": str(e)}), 500

# Helper function to add a log entry for a batch
def add_batch_log(batch_id, message, level="info"):
    """Add a log entry for a batch processing job"""
    if batch_id not in batch_logs:
        batch_logs[batch_id] = []
    
    # Get next log ID
    log_id = len(batch_logs[batch_id]) + 1
    
    # Add log entry
    batch_logs[batch_id].append({
        "id": log_id,
        "timestamp": datetime.now().isoformat(),
        "message": message,
        "level": level
    })
    
    # Log to server log as well
    if level == "info":
        logger.info(f"[BATCH:{batch_id}] {message}")
    elif level == "error":
        logger.error(f"[BATCH:{batch_id}] {message}")
    elif level == "warning":
        logger.warning(f"[BATCH:{batch_id}] {message}")
    else:
        logger.info(f"[BATCH:{batch_id}] {message}")
    
    # Limit log size (keep last 1000 entries)
    if len(batch_logs[batch_id]) > 1000:
        batch_logs[batch_id] = batch_logs[batch_id][-1000:]
    
    return log_id

@app.route("/batch_upload_execute", methods=["POST"])
def batch_upload_execute():
    """Process multiple PDF files from the batch manifest"""
    logger.info("=" * 30)
    logger.info("[BATCH] BATCH DOCUMENT PROCESSING STARTED")
    logger.info("=" * 30)
    
    # Get batch ID from request or fallback to session
    try:
        data = request.get_json(silent=True) or {}
        logger.info(f"[BATCH] Received data: {data}")
        batch_id = data.get("batch_id") or session.get("current_batch_id")
        logger.info(f"[BATCH] Using batch ID: {batch_id}")
    except Exception as e:
        logger.error(f"[BATCH] Error parsing request data: {str(e)}")
        data = {}
        batch_id = session.get("current_batch_id")
    if not batch_id:
        logger.warning(WARNING_SYMBOL + " [BATCH] No batch ID found in session")
        return jsonify({
            "success": False, 
            "message": "No batch ID found. Please upload files first.",
            "total": 0,
            "success": 0,
            "failed": 0,
            "skipped": 0,
            "details": []
        }), 400
        
    # Load batch manifest from file
    batch_status_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "batch_status")
    manifest_path = os.path.join(batch_status_dir, f"manifest_{batch_id}.json")
    
    if not os.path.exists(manifest_path):
        logger.warning(WARNING_SYMBOL + " [BATCH] Batch manifest file not found")
        return jsonify({
            "success": False, 
            "message": "Batch manifest not found.",
            "total": 0,
            "success": 0,
            "failed": 0,
            "skipped": 0,
            "details": []
        }), 400
    
    # Load batch files from manifest
    with open(manifest_path, 'r') as f:
        batch_manifest = json.load(f)
        batch_files = batch_manifest.get("files", [])
    
    if not batch_files:
        logger.warning(WARNING_SYMBOL + " [BATCH] No files found in batch manifest")
        return jsonify({
            "success": False, 
            "message": "No files to process in batch manifest.",
            "total": 0,
            "success": 0,
            "failed": 0,
            "skipped": 0,
            "details": []
        }), 400
    
    # Log the batch files for debugging
    logger.info(f"[BATCH] Found {len(batch_files)} files to process in batch {batch_id}")
    add_batch_log(batch_id, f"Found {len(batch_files)} files to process")
    
    for idx, file_info in enumerate(batch_files):
        file_name = file_info.get('original_name', 'unknown')
        file_path = file_info.get('path', 'unknown path')
        logger.info(f"[BATCH] File {idx+1}: {file_name} at {file_path}")
        
        # Only log the first 10 files to avoid cluttering the log
        if idx < 10:
            add_batch_log(batch_id, f"File {idx+1}: {file_name}")
        elif idx == 10:
            add_batch_log(batch_id, f"...and {len(batch_files) - 10} more files")
    
    # Create batch status directory if it doesn't exist
    batch_status_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "batch_status")
    os.makedirs(batch_status_dir, exist_ok=True)
    
    # Prepare files with status information for monitoring
    status_files = []
    for file_info in batch_files:
        original_name = file_info.get("original_name", "unknown")
        file_path = file_info.get("path", "")
        
        status_files.append({
            "name": original_name,
            "path": file_path,
            "status": "pending",
            "message": "Queued for processing"
        })
    
    # Create batch status information
    batch_status = {
        "batch_id": batch_id,
        "start_time": datetime.now().isoformat(),
        "total": len(batch_files),  # Using 'total' consistently throughout the app
        "total_files": len(batch_files),  # Keep for backward compatibility
        "processed": 0,
        "succeeded": 0,
        "failed": 0,
        "skipped": 0,
        "current_file": "",  # Track the currently processing file
        "files": status_files
    }
    
    # Save batch status to file
    batch_status_path = os.path.join(batch_status_dir, f"batch_{batch_id}.json")
    with open(batch_status_path, 'w') as f:
        json.dump(batch_status, f)
        
    results = {
        "total": len(batch_files), 
        "success": 0, 
        "failed": 0, 
        "skipped": 0, 
        "details": [],
        "batch_id": batch_id
    }
    
    # Load the current batch status
    with open(batch_status_path, 'r') as f:
        batch_status = json.load(f)
    
    file_count = 0
    for file_info in batch_files:
        file_count += 1
        file_path = file_info.get("path")
        original_filename = file_info.get("original_name")
        doc_id = str(uuid.uuid4())
        
        logger.info(f"[BATCH] [{file_count}/{len(batch_files)}] Processing file: {original_filename}")
        
        # Update status to processing (in memory only, don't write to file yet)
        for status_file in batch_status["files"]:
            if status_file["name"] == original_filename:
                status_file["status"] = "processing"
                status_file["start_time"] = datetime.now().isoformat()
                status_file["message"] = "Processing document..."
                break
        
        # Update current file in memory
        batch_status["current_file"] = original_filename
        
        # Add log entry for server logging only (not sent to UI)
        file_index = batch_status["processed"] + 1
        total_files = batch_status["total"]
        # Only log to server, don't add to batch_logs that get sent to UI
        logger.info(f"[BATCH] [{file_index}/{total_files}] Processing file: {original_filename}")
        
        # Check if file exists
        if not file_path or not os.path.exists(file_path):
            logger.warning(WARNING_SYMBOL + f" [BATCH] File not found or path invalid: {file_path}")
            results["skipped"] += 1
            results["details"].append({
                "filename": original_filename,
                "status": "skipped",
                "error": "File not found"
            })
            continue
            
        try:
            # Extract text and metadata
            logger.info(f"[BATCH] Extracting text and metadata from {original_filename}")
            metadata = extract_metadata_from_pdf(file_path)
            
            # Make metadata JSON compatible
            if isinstance(metadata, str):
                try:
                    metadata = json.loads(metadata)
                except:
                    metadata = {}
            
            # Ensure required fields exist
            required_fields = ["title", "authors", "keywords", "abstract", "year"]
            for field in required_fields:
                if field not in metadata:
                    metadata[field] = "" if field != "authors" and field != "keywords" else []
            
            # Update metadata with essential information
            metadata["document_id"] = doc_id
            metadata["original_filename"] = original_filename
            
            # Get file stats for metadata
            file_stats = os.stat(file_path)
            file_size_kb = file_stats.st_size / 1024
            metadata["file_size_kb"] = round(file_size_kb, 2)
            
            # Process the full document using the save_pdf_to_db function
            logger.info(f"[BATCH] Processing complete document: {original_filename}")
            process_result = save_pdf_to_db(file_path, metadata)
            
            # Check the result
            if not process_result.get("success", False):
                logger.error(ERROR_SYMBOL + f" [BATCH] Failed to process document: {process_result.get('message', 'Unknown error')}")
                results["failed"] += 1
                results["details"].append({
                    "filename": original_filename,
                    "status": "failed",
                    "error": f"Document processing failed: {process_result.get('message', 'Unknown error')}"
                })
                
                # Update status to failed
                for status_file in batch_status["files"]:
                    if status_file["name"] == original_filename:
                        status_file["status"] = "failed"
                        status_file["end_time"] = datetime.now().isoformat()
                        status_file["message"] = f"Failed: {process_result.get('message', 'Unknown error')}"
                        break
                        
                # Update batch stats
                batch_status["processed"] += 1
                batch_status["failed"] += 1
                
                # Save updated status
                with open(batch_status_path, 'w') as f:
                    json.dump(batch_status, f)
                    
                # Add log entry with progress counter
                file_index = batch_status["processed"]
                total_files = batch_status["total"]
                error_msg = process_result.get('message', 'Unknown error')
                add_batch_log(batch_id, f"[{file_index}/{total_files}] Failed to process file: {original_filename} - {error_msg}", "error")
                logger.error(f"[BATCH] [{file_index}/{total_files}] Failed to process file: {original_filename} - {error_msg}")
                
                # Clear current file in status
                batch_status["current_file"] = ""
            else:
                # Success - file was processed successfully
                logger.info(SUCCESS_SYMBOL + f" [BATCH] Successfully processed {original_filename}")
                results["success"] += 1
                results["details"].append({
                    "filename": original_filename,
                    "status": "success",
                    "title": metadata.get("title", "Unknown"),
                    "doc_id": doc_id
                })
                
                # Update status to success
                for status_file in batch_status["files"]:
                    if status_file["name"] == original_filename:
                        status_file["status"] = "success"
                        status_file["end_time"] = datetime.now().isoformat()
                        status_file["message"] = "Successfully processed"
                        break

                # Update batch stats
                batch_status["processed"] += 1
                batch_status["succeeded"] += 1

                # Clear current file in status
                batch_status["current_file"] = ""

                # Now that file is fully processed, update status file
                with open(batch_status_path, 'w') as f:
                    json.dump(batch_status, f)

                # Add log entry with progress counter - now we add to batch_logs since processing is complete
                file_index = batch_status["processed"]
                total_files = batch_status["total"]
                add_batch_log(batch_id, f"[{file_index}/{total_files}] Successfully processed file: {original_filename}", "success")
                logger.info(f"[BATCH] [{file_index}/{total_files}] Successfully processed file: {original_filename}")

            # Clean up the temporary file after processing
            try:
                os.remove(file_path)
                logger.info(f"[BATCH] Removed temporary file: {file_path}")
            except Exception as e:
                logger.warning(f"[BATCH] Could not remove temporary file {file_path}: {e}")
            
        except Exception as e:
            logger.error(ERROR_SYMBOL + f" [BATCH] Error processing {original_filename}: {str(e)}")
            results["failed"] += 1
            results["details"].append({
                "filename": original_filename,
                "status": "failed",
                "error": str(e)
            })
            
            # Update status to failed
            for status_file in batch_status["files"]:
                if status_file["name"] == original_filename:
                    status_file["status"] = "failed"
                    status_file["end_time"] = datetime.now().isoformat()
                    status_file["message"] = f"Error: {str(e)}"
                    break
                    
            # Update batch stats
            batch_status["processed"] += 1
            batch_status["failed"] += 1
            
            # Clear current file in status
            batch_status["current_file"] = ""
            
            # Now that error handling is complete, save the updated status - only one file write
            with open(batch_status_path, 'w') as f:
                json.dump(batch_status, f)
                
            # Add log entry with progress counter
            file_index = batch_status["processed"]
            total_files = batch_status["total"]
            error_msg = str(e)
            add_batch_log(batch_id, f"[{file_index}/{total_files}] Error processing file: {original_filename} - {error_msg}", "error")
            logger.error(f"[BATCH] [{file_index}/{total_files}] Error processing file: {original_filename} - {error_msg}")
    
    # Clear the batch ID from session after processing all files
    session.pop("current_batch_id", None)
    
    # Remove the manifest file as it's no longer needed
    try:
        os.remove(manifest_path)
    except Exception as e:
        logger.warning(f"[BATCH] Could not remove manifest file: {str(e)}")
    
    logger.info("=" * 30)
    logger.info(f"[BATCH] BATCH PROCESS COMPLETED: {results['success']} succeeded, {results['failed']} failed, {results['skipped']} skipped")
    logger.info("=" * 30)
    
    # Final update to batch status
    batch_status["end_time"] = datetime.now().isoformat()
    with open(batch_status_path, 'w') as f:
        json.dump(batch_status, f)
        
    # Add final log entry
    add_batch_log(batch_id, f"Batch processing completed: {results['success']} succeeded, {results['failed']} failed, {results['skipped']} skipped", "info")
    
    # Return JSON response with batch ID for status page redirect
    return render_template(
        "batch_results.html",
        batch_id=batch_id,
        success=results["success"],
        failed=results["failed"],
        skipped=results["skipped"],
        total=results["total"],
        details=results["details"]
    )

@app.route("/", methods=["GET"])
def index():
    """Landing page with upload form"""
    return render_template("index.html")

@app.route("/dashboard", methods=["GET"])
def dashboard():
    """Dashboard with document statistics"""
    stats = get_document_stats()
    return render_template("dashboard.html", stats=stats)

@app.route("/upload", methods=["GET", "POST"])
def upload_file():
    """Handle file upload and metadata extraction"""
    if request.method == "POST":
        # Check if the post request has the file part
        if "file" not in request.files:
            return render_template("index.html", error="No file part")
        
        files = request.files.getlist("file")
        
        # Check if multiple files were selected
        if len(files) > 1:
            # For multiple files, save them to temporary directory and store paths in session
            temp_paths = []
            for file in files:
                if file and file.filename and allowed_file(file.filename):
                    # Generate a consistent document ID for this file
                    doc_id = str(uuid.uuid4())
                    
                    # Generate a secure filename with a UUID prefix
                    filename = f"{doc_id}_{secure_filename(file.filename)}"
                    file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
                    
                    # Ensure upload directory exists
                    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
                    
                    # Save the file
                    file.save(file_path)
                    
                    # Add to temp paths
                    temp_paths.append({
                        "path": file_path,
                        "original_name": file.filename,
                        "doc_id": doc_id
                    })
            
            # Store paths in session
            session["batch_files"] = temp_paths
            
            # Redirect to batch processing page
            return redirect(url_for("batch_upload_process"))
        
        file = files[0]
        # If user does not select file, browser also submits an empty part without filename
        if file.filename == "":
            return render_template("index.html", error="No selected file")
        
        if file and allowed_file(file.filename):
            # Generate a consistent document ID
            doc_id = str(uuid.uuid4())
            
            # Generate a secure filename with the document ID as prefix
            filename = f"{doc_id}_{secure_filename(file.filename)}"
            file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            
            # Ensure upload directory exists
            os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
            
            # Save the file
            file.save(file_path)
            
            # Count pages
            page_count = count_pages(file_path)
            
            # Extract text and metadata
            full_text = extract_text_from_pdf(file_path)
            metadata = extract_metadata_from_pdf(file_path)
            
            # Make metadata and JSON compatible
            if isinstance(metadata, str):
                try:
                    metadata = json.loads(metadata)
                except:
                    metadata = {"title": "Unknown", "authors": [], "keywords": [], "abstract": "", "year": ""}
            
            # Add document ID to metadata for consistency
            metadata["document_id"] = doc_id
            
            # Format authors as a string for display
            authors_str = ", ".join(metadata.get("authors", []))
            
            # Save file path and document ID in session for later processing
            session["file_path"] = file_path
            session["doc_id"] = doc_id
            
            return render_template(
                "metadata_review.html",
                metadata=metadata,
                file_path=file_path,
                filename=os.path.basename(file_path),
                authors=authors_str,
                page_count=page_count,
                file_size=os.path.getsize(file_path),
                text_preview=full_text[:1000] + "..." if len(full_text) > 1000 else full_text,
                doc_id=doc_id
            )
    
    return render_template("index.html")

@app.route("/batch_upload_process")
def batch_upload_process():
    """Page for batch processing multiple PDFs"""
    batch_files = session.get("batch_files", [])
    
    if not batch_files:
        return redirect(url_for("index", error="No files selected for batch processing"))
    
    return render_template("batch_process.html", count=len(batch_files), files=batch_files)

@app.route("/document/<doc_id>")
def view_document(doc_id):
    """View document details"""
    try:
        # Find document by ID
        points = qdrant_client.retrieve(
            collection_name=collection_name,
            ids=[doc_id],
            with_payload=True,
            with_vectors=False
        )
        
        if not points:
            flash("Document not found", "error")
            return redirect(url_for("dashboard"))
        
        # Get the document payload
        doc = points[0].payload
        
        # Format dates for display
        if "upload_date" in doc:
            try:
                upload_datetime = datetime.fromisoformat(doc["upload_date"])
                doc["upload_date_formatted"] = upload_datetime.strftime("%Y-%m-%d")
            except:
                doc["upload_date_formatted"] = doc.get("upload_date", "")
        
        return render_template(
            "document.html", 
            document=doc,
            metadata=doc.get("metadata", {}),
            filename=doc.get("azure_blob_name", "Unknown")
        )
    except Exception as e:
        logger.error(f"Error viewing document: {str(e)}")
        flash(f"Error viewing document: {str(e)}", "error")
        return redirect(url_for("dashboard"))

@app.route("/document/<document_id>/details")
def document_details(document_id):
    """Display detailed information for a specific document"""
    try:
        # Find document by ID
        points = qdrant_client.retrieve(
            collection_name=collection_name,
            ids=[document_id],
            with_payload=True,
            with_vectors=False
        )
        
        if not points:
            flash("Document not found", "error")
            return redirect(url_for("dashboard"))
        
        # Get the document payload
        doc = points[0].payload
        
        # Format dates for display
        if "upload_date" in doc:
            try:
                upload_datetime = datetime.fromisoformat(doc["upload_date"])
                doc["upload_date_formatted"] = upload_datetime.strftime("%Y-%m-%d")
            except:
                doc["upload_date_formatted"] = doc.get("upload_date", "")
        
        # Get document chunks from Qdrant
        # Generate a dummy embedding for search (we'll just use it to get all chunks for this document)
        dummy_embedding = [0.0] * 1536  # OpenAI embeddings are 1536 dimensions
        
        logger.info(f"Searching for chunks with document_id: {document_id}")
        
        # Search in Qdrant with a filter for this document_id
        try:
            search_results = qdrant_client.search(
                collection_name=collection_name,
                query_vector=dummy_embedding,
                query_filter=qdrant_models.Filter(
                    must=[
                        qdrant_models.FieldCondition(
                            key="document_id",
                            match=qdrant_models.MatchValue(value=document_id)
                        )
                    ]
                ),
                limit=100,  # Get up to 100 chunks
                with_payload=True,
                score_threshold=0.0  # Get all results regardless of score
            )
            
            logger.info(f"Found {len(search_results)} chunks for document {document_id}")
            
            # Extract chunks from search results
            chunks = []
            for result in search_results:
                chunks.append({
                    "chunk_index": result.payload.get("chunk_index", 0),
                    "created_at": result.payload.get("created_at", "")
                })
        except Exception as e:
            logger.error(f"Error searching Qdrant: {str(e)}")
            chunks = []
        
        # Sort chunks by index
        chunks = sorted(chunks, key=lambda x: x["chunk_index"])
        
        # Get the PDF file for display
        try:
            blob_name = doc.get("azure_blob_name", "Unknown")
        except Exception as e:
            logger.error(f"Error retrieving file from Azure Blob Storage: {str(e)}")
            blob_name = "Unknown"
        
        return render_template(
            "document_details.html",
            document=doc,
            metadata=doc.get("metadata", {}),
            chunks=chunks,
            filename=blob_name
        )
    except Exception as e:
        logger.error(f"Error viewing document details: {str(e)}")
        flash(f"Error viewing document details: {str(e)}", "error")
        return redirect(url_for("dashboard"))

@app.route("/download/<file_id>")
def download_pdf(file_id):
    """Download a PDF file from Azure Blob Storage"""
    try:
        # Retrieve document metadata from Qdrant
        logger.info(f"[QDRANT] Retrieving document metadata for download, document ID: {file_id}")
        points = qdrant_client.retrieve(
            collection_name=collection_name,
            ids=[file_id],
            with_payload=True,
            with_vectors=False
        )
        
        if not points:
            logger.error(ERROR_SYMBOL + f" [QDRANT] Document not found for download: {file_id}")
            return jsonify({"error": "Document not found"}), 404
        
        # Get the document payload
        doc = points[0].payload
        logger.info(f"[QDRANT] Retrieved document metadata for: {doc.get('title', 'Unknown document')}")
        
        # Check if we have Azure blob info
        if "azure_blob_url" not in doc:
            logger.error(ERROR_SYMBOL + f" [AZURE] No Azure Blob URL found for document: {file_id}")
            return jsonify({"error": "Document PDF URL not found"}), 404
        
        # For security, redirect to the Azure blob URL rather than proxying the file
        logger.info(f"[AZURE] Redirecting to Azure Blob URL for download: {doc.get('azure_blob_name', 'unknown')}")
        return redirect(doc["azure_blob_url"])
    except Exception as e:
        logger.error(ERROR_SYMBOL + f" [AZURE] Error downloading document {file_id}: {str(e)}")
        return jsonify({"error": f"Error downloading document: {str(e)}"}), 500

@app.route("/settings", methods=["GET", "POST"])
def settings():
    """Application settings page"""
    if request.method == "POST":
        # Update settings
        chunk_size = request.form.get("chunk_size", "512")
        chunk_overlap = request.form.get("chunk_overlap", "50")
        
        try:
            app.config["CHUNK_SIZE"] = int(chunk_size)
            app.config["CHUNK_OVERLAP"] = int(chunk_overlap)
            return render_template("settings.html", success="Settings updated successfully")
        except ValueError:
            return render_template("settings.html", error="Invalid settings values")
    
    return render_template(
        "settings.html", 
        chunk_size=app.config["CHUNK_SIZE"],
        chunk_overlap=app.config["CHUNK_OVERLAP"]
    )

@app.template_filter('json_pretty')
def json_pretty(value):
    """Template filter to pretty-print JSON"""
    if isinstance(value, dict):
        return json.dumps(value, indent=2)
    return value

@app.route("/api/extract", methods=["POST"])
def api_extract():
    """API endpoint for metadata extraction"""
    if "pdf_file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    
    file = request.files["pdf_file"]
    filename = secure_filename(file.filename)
    file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(file_path)
    
    metadata = extract_metadata_from_pdf(file_path)
    
    # Clean up
    if os.path.exists(file_path):
        os.remove(file_path)
        
    return jsonify(metadata)

@app.route("/api/save", methods=["POST"])
def api_save():
    """API endpoint for saving document with metadata"""
    if "pdf_file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    
    file = request.files["pdf_file"]
    metadata_json = request.form.get("metadata", "{}")
    
    try:
        metadata = json.loads(metadata_json)
    except json.JSONDecodeError:
        return jsonify({"error": "Invalid metadata JSON"}), 400
    
    filename = secure_filename(file.filename)
    file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(file_path)

    try:
        result = save_pdf_to_db(file_path, metadata)

        if result and result.get("success", False):
            document_id = result.get("document_id") or metadata.get("document_id")
            return jsonify(
                {
                    "status": "success",
                    "message": "Document saved successfully",
                    "document_id": document_id,
                }
            )

        return jsonify({"status": "error", "message": "Failed to save document"}), 500
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)

def get_document_stats():
    """Get document statistics for the dashboard from Azure and Qdrant"""
    try:
        # Step 1: Efficiently count PDFs in Azure Blob Storage
        logger.info("[STATS] Getting PDF count from Azure Blob Storage")
        total_documents = 0
        total_pages = 0
        total_chunks = 0
        
        try:
            # Count blobs directly in Azure (much more efficient)
            blobs = list(container_client.list_blobs())
            pdf_count = len(blobs)
            logger.info(f"[STATS] Found {pdf_count} PDFs in Azure Blob Storage")
            total_documents = pdf_count
        except Exception as azure_error:
            logger.error(f"[ERROR] Error counting Azure blobs: {str(azure_error)}")
            # Fall back to 0 if we can't get Azure count
            total_documents = 0
        
        # Step 2: Get a sample of recent documents and chunk count (limit to avoid timeout)
        try:
            # Use Qdrant's count API to get total chunks efficiently
            chunk_count_response = qdrant_client.count(
                collection_name=collection_name,
                count_filter=qdrant_models.Filter(
                    must=[
                        qdrant_models.FieldCondition(
                            key="page_content",
                            match=qdrant_models.MatchValue(
                                value="",
                                text_match_type=qdrant_models.TextMatchType.TEXT_MATCH_TYPE_NOT_EMPTY
                            )
                        )
                    ]
                )
            )
            # Get estimated chunk count
            total_chunks = chunk_count_response.count
            logger.info(f"[STATS] Estimated {total_chunks} chunks in Qdrant")
        except Exception as chunk_error:
            logger.error(f"[ERROR] Error getting chunk count: {str(chunk_error)}")
            total_chunks = 0
        
        # Step 3: Get estimated page count (approximation based on sample)
        # This avoids loading all documents which causes timeout
        try:
            # Sample a few recent documents to estimate page count
            sample_docs = qdrant_client.scroll(
                collection_name=collection_name,
                limit=20,  # Only sample a few docs to avoid timeout
                with_payload=True,
                with_vectors=False,
                # Sort by upload date if available
                sort_by=["upload_date"] if "upload_date" in qdrant_client.get_collection(
                    collection_name=collection_name
                ).payload_schema else None
            )
            
            # Calculate pages from the sample
            page_sample = 0
            sample_count = 0
            
            for point in sample_docs[0]:
                payload = point.payload
                # Check for new structure
                if "metadata" in payload and payload["metadata"].get("page_count"):
                    page_sample += payload["metadata"].get("page_count", 0)
                    sample_count += 1
                # Fallback for old structure
                elif payload.get("page_count"):
                    page_sample += payload.get("page_count", 0)
                    sample_count += 1
            
            # Estimate total pages based on sample average
            if sample_count > 0:
                avg_pages = page_sample / sample_count
                total_pages = int(avg_pages * total_documents)
                logger.info(f"[STATS] Estimated {total_pages} total pages based on sample average of {avg_pages} pages per document")
            else:
                total_pages = 0
        except Exception as page_error:
            logger.error(f"[ERROR] Error estimating page count: {str(page_error)}")
            total_pages = 0
            
        # Step 4: Get a few recent documents for display (limited to avoid timeout)
        recent_documents = []
        
        try:
            # Get only the most recent documents for display
            recent_query = qdrant_client.scroll(
                collection_name=collection_name,
                limit=10,  # Only the most recent 10
                with_payload=True,
                with_vectors=False,
                # Try to sort by upload date descending if schema has it
                sort_by=["upload_date"] if "upload_date" in qdrant_client.get_collection(
                    collection_name=collection_name
                ).payload_schema else None
            )
            
            # Process only these few documents for display
            for point in recent_query[0]:
                payload = point.payload
                display_doc = {}
                
                # Handle new structure with metadata subdictionary
                if "metadata" in payload:
                    metadata = payload["metadata"]
                    # Copy document-level fields
                    display_doc["document_id"] = payload.get("document_id", "")
                    display_doc["page_content"] = payload.get("page_content", "")
                    
                    # Copy metadata fields
                    display_doc["title"] = metadata.get("title", "Untitled")
                    display_doc["authors"] = metadata.get("authors", [])
                    display_doc["year"] = metadata.get("year", "")
                    display_doc["abstract"] = metadata.get("abstract", "")
                    display_doc["keywords"] = metadata.get("keywords", [])
                    display_doc["page_count"] = metadata.get("page_count", 0)
                    display_doc["upload_date"] = metadata.get("upload_date", "")
                    display_doc["azure_url"] = metadata.get("azure_url", "")
                    
                    # Format upload date for display
                    if "upload_date" in metadata:
                        try:
                            upload_datetime = datetime.fromisoformat(metadata["upload_date"])
                            display_doc["upload_date_formatted"] = upload_datetime.strftime("%Y-%m-%d")
                        except:
                            display_doc["upload_date_formatted"] = metadata.get("upload_date", "")
                else:
                    # Fallback for old structure - directly copy payload
                    display_doc = payload.copy()
                    
                    # Format upload date for display (old structure)
                    if "upload_date" in payload:
                        try:
                            upload_datetime = datetime.fromisoformat(payload["upload_date"])
                            display_doc["upload_date_formatted"] = upload_datetime.strftime("%Y-%m-%d")
                        except:
                            display_doc["upload_date_formatted"] = payload.get("upload_date", "")
                
                # Add the document to recent documents
                recent_documents.append(display_doc)
            
            # Sort recent documents by upload date (newest first)
            recent_documents.sort(
                key=lambda x: x.get("upload_date", ""),
                reverse=True
            )
        except Exception as doc_error:
            logger.error(f"[ERROR] Error getting recent documents: {str(doc_error)}")
            # Empty list if we fail
            recent_documents = []
        
        # Limit to 10 most recent
        recent_documents = recent_documents[:10]
        
        # Format for display in template
        for doc in recent_documents:
            # Ensure document has _id for view_document URL
            if "document_id" in doc and "_id" not in doc:
                doc["_id"] = doc["document_id"]
        
        # Return statistics
        return {
            "total_documents": total_documents,
            "total_chunks": total_chunks,
            "total_pages": total_pages,
            "recent_documents": recent_documents
        }
    except Exception as e:
        logger.error(ERROR_SYMBOL + f" Error getting document statistics: {str(e)}")
        # Return empty stats on error
        return {
            "total_documents": 0,
            "total_chunks": 0,
            "total_pages": 0,
            "recent_documents": []
        }

# View metadata functionality has been removed

@app.route("/view_document/<doc_id>")
def view_document_details(doc_id):
    """View a single document and its details from Qdrant"""
    try:
        # Retrieve document metadata from Qdrant
        points = qdrant_client.retrieve(
            collection_name=collection_name,
            ids=[doc_id],
            with_payload=True,
            with_vectors=False
        )
        
        if not points:
            return render_template("error.html", error=f"Document not found: {doc_id}")
        
        # Get the document payload
        doc = points[0].payload
        
        # Format dates for display
        if "upload_date" in doc:
            try:
                upload_datetime = datetime.fromisoformat(doc["upload_date"])
                doc["upload_date_formatted"] = upload_datetime.strftime("%Y-%m-%d %H:%M")
            except:
                doc["upload_date_formatted"] = doc.get("upload_date", "")
        
        return render_template("document_view.html", document=doc)
    except Exception as e:
        logger.error(ERROR_SYMBOL + f" Error viewing document {doc_id}: {str(e)}")
        return render_template("error.html", error=f"Error retrieving document: {str(e)}")

@app.route("/download_document/<doc_id>")
def download_document(doc_id):
    """Download the PDF file from Azure Blob Storage"""
    try:
        # Retrieve document metadata from Qdrant
        logger.info(f"[QDRANT] Retrieving document metadata for download, document ID: {doc_id}")
        points = qdrant_client.retrieve(
            collection_name=collection_name,
            ids=[doc_id],
            with_payload=True,
            with_vectors=False
        )
        
        if not points:
            logger.error(ERROR_SYMBOL + f" [QDRANT] Document not found for download: {doc_id}")
            return jsonify({"error": "Document not found"}), 404
        
        # Get the document payload
        doc = points[0].payload
        logger.info(f"[QDRANT] Retrieved document metadata for: {doc.get('title', 'Unknown document')}")
        
        # Check if we have Azure blob info
        if "azure_blob_url" not in doc:
            logger.error(ERROR_SYMBOL + f" [AZURE] No Azure Blob URL found for document: {doc_id}")
            return jsonify({"error": "Document PDF URL not found"}), 404
        
        # For security, redirect to the Azure blob URL rather than proxying the file
        logger.info(f"[AZURE] Redirecting to Azure Blob URL for download: {doc.get('azure_blob_name', 'unknown')}")
        return redirect(doc["azure_blob_url"])
    except Exception as e:
        logger.error(ERROR_SYMBOL + f" [AZURE] Error downloading document {doc_id}: {str(e)}")
        return jsonify({"error": f"Error downloading document: {str(e)}"}), 500

@app.route("/delete_document/<doc_id>", methods=["POST"])
def delete_document(doc_id):
    """Delete a document from Qdrant and Azure Blob Storage"""
    try:
        # First get the document to find the Azure blob name
        logger.info(f"[QDRANT] Retrieving document metadata for deletion, document ID: {doc_id}")
        points = qdrant_client.retrieve(
            collection_name=collection_name,
            ids=[doc_id],
            with_payload=True,
            with_vectors=False
        )
        
        if not points:
            logger.error(ERROR_SYMBOL + f" [QDRANT] Document not found for deletion: {doc_id}")
            return jsonify({"error": "Document not found"}), 404
        
        # Get the document payload
        doc = points[0].payload
        logger.info(f"[QDRANT] Retrieved document for deletion: {doc.get('title', 'Unknown document')}")
        
        # Delete from Qdrant first
        logger.info(f"[QDRANT] Deleting document from Qdrant, document ID: {doc_id}")
        qdrant_client.delete(
            collection_name=collection_name,
            points_selector=qdrant_models.PointIdsList(
                points=[doc_id]
            )
        )
        logger.info(SUCCESS_SYMBOL + f" [QDRANT] Successfully deleted document from Qdrant")
        
        # If we have the Azure blob name, delete from Azure
        if "azure_blob_name" in doc:
            try:
                blob_name = doc["azure_blob_name"]
                logger.info(f"[AZURE] Deleting blob from Azure Storage: {blob_name}")
                blob_client = container_client.get_blob_client(blob_name)
                blob_client.delete_blob()
                logger.info(SUCCESS_SYMBOL + f" [AZURE] Successfully deleted blob from Azure Storage: {blob_name}")
            except Exception as azure_error:
                logger.error(ERROR_SYMBOL + f" [AZURE] Error deleting Azure blob: {str(azure_error)}")
                # Continue even if Azure deletion fails
        
        return jsonify({"success": True, "message": "Document deleted successfully"})
    except Exception as e:
        logger.error(ERROR_SYMBOL + f" Error deleting document {doc_id}: {str(e)}")
        return jsonify({"error": f"Error deleting document: {str(e)}"}), 500

@app.route('/process_document', methods=['POST'])
def process_document():
    try:
        if 'file' not in request.files:
            flash("No file uploaded")
            return redirect(url_for('dashboard'))
        
        file = request.files['file']
        if file.filename == '':
            flash("No file selected")
            return redirect(url_for('dashboard'))
        
        # Check if file is a PDF
        if not file.filename.lower().endswith('.pdf'):
            flash("Only PDF files are supported")
            return redirect(url_for('dashboard'))
        
        # Save file temporarily
        temp_dir = "temp_uploads"
        os.makedirs(temp_dir, exist_ok=True)
        
        file_path = os.path.join(temp_dir, secure_filename(file.filename))
        file.save(file_path)
        
        # Get file info
        file_stats = os.stat(file_path)
        file_size_kb = file_stats.st_size / 1024
        page_count = count_pages(file_path)
        
        # Extract metadata including title, authors, etc.
        logger.info(f"[PROCESSING] Extracting metadata from {file.filename}")
        metadata = extract_metadata_from_pdf(file_path)
        
        # Generate unique document ID
        doc_id = str(uuid.uuid4())
        metadata["document_id"] = doc_id
        metadata["original_filename"] = file.filename
        metadata["file_size_kb"] = round(file_size_kb, 2)
        
        logger.info(f"[PROCESSING] Processing document: {file.filename}")
        
        # Process the full document using the same function used for single uploads
        logger.info(f"[BATCH] Processing complete document: {file.filename}")
        process_result = save_pdf_to_db(file_path, metadata)
        
        # Delete temporary file
        try:
            os.remove(file_path)
            logger.info(f"[CLEANUP] Removed temporary file: {file_path}")
        except Exception as e:
            logger.warning(f"[CLEANUP] Could not remove temporary file: {str(e)}")
        
        if process_result.get("success", False):
            flash("Document successfully processed and saved!")
        else:
            flash(f"Error processing document: {process_result.get('message', 'Unknown error')}")
        
        return redirect(url_for('dashboard'))
        
    except Exception as e:
        logger.error(f"{ERROR_SYMBOL} Error processing document: {str(e)}")
        flash(f"Error processing document: {str(e)}")
        return redirect(url_for('dashboard'))

# API endpoints for batch status monitoring
@app.route("/api/batch_status/<batch_id>", methods=["GET"])
def api_batch_status(batch_id):
    """Get status for a batch processing job"""
    try:
        # Get batch status file path
        batch_status_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "batch_status")
        
        # Create batch status directory if it doesn't exist
        if not os.path.exists(batch_status_dir):
            os.makedirs(batch_status_dir)
            logger.info(f"Created batch status directory: {batch_status_dir}")
        
        # Check different possible filenames (with and without prefix)
        possible_filenames = [f"{batch_id}.json", f"batch_{batch_id}.json"]
        batch_status_path = None
        
        for filename in possible_filenames:
            path = os.path.join(batch_status_dir, filename)
            if os.path.exists(path):
                batch_status_path = path
                break
        
        # If no status file exists, return a default empty status
        if not batch_status_path:
            logger.warning(f"Batch status file not found for ID: {batch_id}")
            return jsonify({
                "batch_id": batch_id,
                "total": 0,
                "processed": 0,
                "succeeded": 0,
                "failed": 0,
                "skipped": 0,
                "files": [],
                "is_complete": False,
                "status": "not_found"
            })
            
        # Read batch status file
        with open(batch_status_path, 'r') as f:
            batch_status = json.load(f)
            
        # Add is_complete flag
        batch_status["is_complete"] = (batch_status.get("processed", 0) == batch_status.get("total", 0)) \
                                    or (batch_status.get("end_time") is not None)
        
        return jsonify(batch_status)
    except Exception as e:
        logger.error(f"Error getting batch status: {str(e)}")
        return jsonify({
            "batch_id": batch_id,
            "error": str(e),
            "status": "error",
            "is_complete": False,
            "total": 0,
            "processed": 0,
            "succeeded": 0,
            "failed": 0
        }), 500
        
@app.route("/api/batch_status/<batch_id>/files", methods=["GET"])
def api_batch_status_files(batch_id):
    """Get file-level status for a batch processing job"""
    try:
        # Get batch status file path
        batch_status_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "batch_status")
        
        # Create batch status directory if it doesn't exist
        if not os.path.exists(batch_status_dir):
            os.makedirs(batch_status_dir)
            logger.info(f"Created batch status directory: {batch_status_dir}")
        
        # Check different possible filenames (with and without prefix)
        possible_filenames = [f"{batch_id}.json", f"batch_{batch_id}.json"]
        batch_status_path = None
        
        for filename in possible_filenames:
            path = os.path.join(batch_status_dir, filename)
            if os.path.exists(path):
                batch_status_path = path
                break
        
        # If no status file exists, return a default empty status
        if not batch_status_path:
            logger.warning(f"Batch file status not found for ID: {batch_id}")
            return jsonify({
                "batch_id": batch_id,
                "total": 0,
                "processed": 0,
                "succeeded": 0,
                "failed": 0,
                "files": [],
                "is_complete": False,
                "status": "not_found"
            })
            
        # Read batch status file
        with open(batch_status_path, 'r') as f:
            batch_status = json.load(f)
        
        # Extract just the files portion and relevant stats
        response = {
            "batch_id": batch_id,
            "files": batch_status.get("files", []),
            "total": batch_status.get("total", 0),
            "processed": batch_status.get("processed", 0),
            "succeeded": batch_status.get("succeeded", 0),
            "failed": batch_status.get("failed", 0),
            "skipped": batch_status.get("skipped", 0),
            "is_complete": (batch_status.get("processed", 0) == batch_status.get("total", 0)) \
                          or (batch_status.get("end_time") is not None),
            "start_time": batch_status.get("start_time"),
            "end_time": batch_status.get("end_time")
        }
        
        return jsonify(response)
    except Exception as e:
        logger.error(f"Error getting batch file status: {str(e)}")
        return jsonify({
            "batch_id": batch_id,
            "error": str(e),
            "status": "error",
            "is_complete": False,
            "total": 0,
            "processed": 0,
            "succeeded": 0,
            "failed": 0,
            "files": []
        }), 500

@app.route("/api/retry_failed/<batch_id>", methods=["POST"])
def api_retry_failed(batch_id):
    """Retry failed tasks in a batch"""
    try:
        # Check if batch status file exists
        batch_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"batch_{batch_id}.json")
        
        if not os.path.exists(batch_file_path):
            # Check if we can find it in a batch status directory
            batch_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "batch_status")
            if os.path.exists(batch_dir):
                batch_file_path = os.path.join(batch_dir, f"batch_{batch_id}.json")
                if not os.path.exists(batch_file_path):
                    return jsonify({"success": False, "message": "Batch not found"}), 404
            else:
                return jsonify({"success": False, "message": "Batch not found"}), 404
        
        with open(batch_file_path, 'r') as f:
            batch_info = json.load(f)
        
        failed_count = 0
        # Reset status of failed tasks
        for file in batch_info['files']:
            if file.get('status') == 'failed':
                file['status'] = 'pending'
                file['message'] = 'Queued for retry'
                file.pop('start_time', None)
                file.pop('end_time', None)
                failed_count += 1
        
        # Update batch info with new pending tasks
        batch_info['failed'] -= failed_count
        batch_info['processed'] -= failed_count
        
        # Save updated info back to file
        with open(batch_file_path, 'w') as f:
            json.dump(batch_info, f)
        
        # In a real implementation with Celery, you would requeue the tasks here
        # For example: 
        # for task_id in batch_info.get('task_ids', []):
        #     result = AsyncResult(task_id)
        #     if result.status == 'FAILURE':
        #         task.retry()
        
        return jsonify({"success": True, "message": f"Requeued {failed_count} failed tasks for processing"})
    
    except Exception as e:
        logger.error(f"Error retrying failed tasks: {str(e)}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/batch_status/<batch_id>", methods=["GET"])
def batch_status(batch_id):
    """Display the batch status page"""
    return render_template("batch_status.html", batch_id=batch_id)

if __name__ == "__main__":
    app.run(
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "5000")),
        debug=os.environ.get("FLASK_DEBUG", "false").strip().lower() == "true",
    )
