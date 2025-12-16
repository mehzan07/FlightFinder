
import logging
import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()

def get_env_var(name):
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"{name} is not set in the environment")
    return value

# === Local Development Settings ===
FLASK_APP = get_env_var("FLASK_APP")
FLASK_ENV = get_env_var("FLASK_ENV")
PORT = int(get_env_var("PORT"))
IS_LOCAL = get_env_var("IS_LOCAL").lower() == "true"
DEBUG_MODE = get_env_var("DEBUG_MODE").lower() == "true"
HOST = get_env_var("HOST")

# === Feature Flags ===
FEATURED_FLIGHT_LIMIT = int(get_env_var("FEATURED_FLIGHT_LIMIT"))

# === Travelpayouts API Credentials ===
API_TOKEN = get_env_var("API_TOKEN")
AFFILIATE_MARKER = get_env_var("AFFILIATE_MARKER")
USER_IP = get_env_var("USER_IP")
USE_REAL_API = get_env_var("USE_REAL_API").lower() == "true"


# Amadeus configuration
AMADEUS_API_KEY = os.getenv("AMADEUS_API_KEY")
AMADEUS_API_SECRET = os.getenv("AMADEUS_API_SECRET")
AMADEUS_BASE_URL = os.getenv("AMADEUS_BASE_URL", "https://test.api.amadeus.com")
USE_AMADEUS = os.getenv("USE_AMADEUS", "False") == "True"


# Function to convert environment strings (e.g., "False", "0") to boolean False
def get_env_boolean(var_name, default=False):
    val = os.getenv(var_name, str(default)).lower()
    return val in ('true', '1', 't')

# Use the function for the boolean variables
FORCE_AMADEUS = get_env_boolean("FORCE_AMADEUS", default=False)




# === Logging Configuration ===
log_level = logging.DEBUG if DEBUG_MODE else logging.INFO

def setup_logging():
    """Configure logging for the application"""
    log_level = logging.DEBUG if DEBUG_MODE else logging.INFO

    logging.basicConfig(
        level=log_level,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        handlers=[
            logging.StreamHandler(),
            # logging.FileHandler('app.log')  # Optional file logging
        ]
    )

def get_logger(name):
    """Get a logger instance for a specific module"""
    return logging.getLogger(name)

# Initialize logging when config is imported
setup_logging()

# At the bottom of config.py, add:
if __name__ == "__main__":
    print("Testing config loading...")
    print(f"AMADEUS_API_KEY: {AMADEUS_API_KEY[:20] if AMADEUS_API_KEY else 'NOT SET'}...")
    print(f"AMADEUS_API_SECRET: {AMADEUS_API_SECRET[:20] if AMADEUS_API_SECRET else 'NOT SET'}...")
    print(f"AMADEUS_BASE_URL: {AMADEUS_BASE_URL}")
    print(f"USE_AMADEUS: {USE_AMADEUS}")