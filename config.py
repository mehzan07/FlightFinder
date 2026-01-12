
import logging
import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()

def get_env_var(name, default=None):
    """
    Modified to be 'softer'. 
    It returns a default value instead of crashing if a variable is missing.
    """
    value = os.getenv(name, default)
    if value is None:
        # We log a warning to the console so you can see it in your PythonAnywhere logs
        print(f"⚠️ WARNING: {name} is not set in the environment. Using default: {default}")
    return value

# === Local Development & Server Settings ===
FLASK_APP = get_env_var("FLASK_APP", "app.py")
FLASK_ENV = get_env_var("FLASK_ENV", "production")
# Defaulting to 10000 but PythonAnywhere will ignore this and use its own port
PORT = int(get_env_var("PORT", 10000))
IS_LOCAL = get_env_var("IS_LOCAL", "false").lower() == "true"
DEBUG_MODE = get_env_var("DEBUG_MODE", "False").lower() == "true"
HOST = get_env_var("HOST", "0.0.0.0")

# === Feature Flags ===
FEATURED_FLIGHT_LIMIT = int(get_env_var("FEATURED_FLIGHT_LIMIT", 5))

# === Travelpayouts API Credentials ===
API_TOKEN = get_env_var("API_TOKEN")
AFFILIATE_MARKER = get_env_var("AFFILIATE_MARKER")
USER_IP = get_env_var("USER_IP", "127.0.0.1")
USE_REAL_API = get_env_var("USE_REAL_API", "true").lower() == "true"

# === Amadeus configuration ===
AMADEUS_API_KEY = os.getenv("AMADEUS_API_KEY")
AMADEUS_API_SECRET = os.getenv("AMADEUS_API_SECRET")
AMADEUS_BASE_URL = os.getenv("AMADEUS_BASE_URL", "https://test.api.amadeus.com")
USE_AMADEUS = os.getenv("USE_AMADEUS", "False") == "True"

# Helper function for boolean variables
def get_env_boolean(var_name, default=False):
    val = os.getenv(var_name, str(default)).lower()
    return val in ('true', '1', 't')

FORCE_AMADEUS = get_env_boolean("FORCE_AMADEUS", default=False)

# === Logging Configuration ===
def setup_logging():
    """Configure logging for the application"""
    log_level = logging.DEBUG if DEBUG_MODE else logging.INFO

    logging.basicConfig(
        level=log_level,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        handlers=[
            logging.StreamHandler(),
        ]
    )

def get_logger(name):
    """Get a logger instance for a specific module"""
    return logging.getLogger(name)

# Initialize logging
setup_logging()

if __name__ == "__main__":
    print("Testing config loading...")
    print(f"DATABASE: Removed (Running in Database-Free mode)")