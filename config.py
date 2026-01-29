import logging
import os
from dotenv import load_dotenv

load_dotenv()

def get_env_var(name, default=None):
    value = os.getenv(name, default)
    if value is None:
        print(f"⚠️ WARNING: {name} is not set in the environment. Using default: {default}")
    return value

def get_env_boolean(var_name, default=False):
    val = os.getenv(var_name, str(default)).lower()
    return val in ('true', '1', 't', 'yes')

PA_USER = get_env_var("PYTHONANYWHERE_USER", "username")


# === Environment Detection ===
# If IS_LOCAL is false, we assume we are on PythonAnywhere
IS_LOCAL = get_env_boolean("IS_LOCAL", default=False)
if IS_LOCAL:
    # Use 127.0.0.1 for local links
    HOST = "http://127.0.0.1:5000"
else:
    HOST = f"https://{PA_USER}.pythonanywhere.com"
    
DEBUG_MODE = get_env_boolean("DEBUG_MODE", default=False)
HOST = get_env_var("HOST", "0.0.0.0")
USER_IP = get_env_var("USER_IP", "127.0.0.1")

# === Server & URL Settings ===
# This dynamically sets your domain so links don't break
#PA_USER = get_env_var("PYTHONANYWHERE_USER", "username")
if IS_LOCAL:
    BASE_URL = "http://127.0.0.1:5000"
    # Local-friendly CDN (Skyscanner)
    LOGO_CDN = "https://logos.skyscnr.com/images/airlines/favicon/"
else:
    BASE_URL = f"https://{PA_USER}.pythonanywhere.com"
    # Production CDN (Aviasales High-Load)
    LOGO_CDN = "https://pics.avs.io/hl/100/40/"

# === Travelpayouts API Credentials ===
API_TOKEN = get_env_var("API_TOKEN")
AFFILIATE_MARKER = get_env_var("AFFILIATE_MARKER")
USE_REAL_API = get_env_boolean("USE_REAL_API", default=True)

# === Amadeus Configuration ===
AMADEUS_API_KEY = get_env_var("AMADEUS_API_KEY")
AMADEUS_API_SECRET = get_env_var("AMADEUS_API_SECRET")
AMADEUS_BASE_URL = get_env_var("AMADEUS_BASE_URL", "https://test.api.amadeus.com")
USE_AMADEUS = get_env_boolean("USE_AMADEUS", default=True)
FORCE_AMADEUS = get_env_boolean("FORCE_AMADEUS", default=False)

# === Other Settings ===
FEATURED_FLIGHT_LIMIT = int(get_env_var("FEATURED_FLIGHT_LIMIT", 4))

# === Logging Configuration ===
def setup_logging():
    log_level = logging.DEBUG if DEBUG_MODE else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        handlers=[logging.StreamHandler()]
    )

setup_logging()
def get_logger(name):
    return logging.getLogger(name)