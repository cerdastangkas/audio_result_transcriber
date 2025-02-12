import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Global constants
BASE_DATA_FOLDER = os.getenv('BASE_DATA_FOLDER')
if not BASE_DATA_FOLDER:
    raise ValueError("BASE_DATA_FOLDER environment variable is not set")

# API Keys
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY environment variable is not set")
