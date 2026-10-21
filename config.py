import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    PROJECT_NAME = "MediReference AI"
    VERSION = "2.1.0"
    
    # Provider Settings
    LLM_PROVIDER = os.getenv("LLM_PROVIDER", "groq")
    
    # API Keys
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
    
    # Models
    GROQ_TEXT_MODEL = os.getenv("GROQ_TEXT_MODEL", "qwen/qwen3.8-27b")
    GROQ_VISION_MODEL = os.getenv("GROQ_VISION_MODEL", "qwen/qwen3.8-27b")
    GROQ_MAX_TOKENS = int(os.getenv("GROQ_MAX_TOKENS", "950"))
    OLLAMA_MODEL = "llama3.1"
    OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    
    # Paths
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DATA_PATH = os.path.join(BASE_DIR, "data", "clinical_guidelines.json")
    CHROMA_DB_PATH = os.path.join(BASE_DIR, "chroma_db")
    STORAGE_PATH = os.path.join(BASE_DIR, "data", "app_storage.json")
    
    # Vector DB
    COLLECTION_NAME = "clinical_guidelines"
    EMBEDDING_MODEL = "all-MiniLM-L6-v2"
    
    # RAG Settings
    TOP_K = 5
    CHUNK_SIZE = 512
    CHUNK_OVERLAP = 100
    MIN_RETRIEVAL_SCORE = float(os.getenv("MIN_RETRIEVAL_SCORE", "1.1"))
    MAX_CONTEXTS = int(os.getenv("MAX_CONTEXTS", "4"))
    MAX_IMAGE_SIZE_MB = int(os.getenv("MAX_IMAGE_SIZE_MB", "8"))
    MAX_PDF_SIZE_MB = int(os.getenv("MAX_PDF_SIZE_MB", "12"))
    MAX_PDF_PAGES = int(os.getenv("MAX_PDF_PAGES", "4"))

    # External data sources
    OPENFDA_BASE_URL = os.getenv("OPENFDA_BASE_URL", "https://api.fda.gov/drug/label.json")
    RXNAV_BASE_URL = os.getenv("RXNAV_BASE_URL", "https://rxnav.nlm.nih.gov/REST")
    ENABLE_ONLINE_DRUG_LOOKUP = os.getenv("ENABLE_ONLINE_DRUG_LOOKUP", "true").lower() == "true"
    DEFAULT_LANGUAGE = os.getenv("DEFAULT_LANGUAGE", "English")

config = Config()
