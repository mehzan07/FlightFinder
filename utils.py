import re
import hashlib
import logging
from datetime import datetime
from typing import Dict, Any

import dateparser
from word2number import w2n
import spacy

import os
import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)
nlp = spacy.load("en_core_web_sm")


def normalize_passenger_count(text: str) -> int:
    text = text.lower()

    if "me and my" in text or "my partner" in text:
        return 2
    if "family" in text:
        return 4
    if "group" in text:
        return 5

    match = re.search(r"(\d+)\s*(passenger|people|adults|persons)?", text)
    if match:
        return int(match.group(1))

    try:
        return w2n.word_to_num(text)
    except:
        return 1


def parse_date(text: str):
    """
    Parses a natural language date string (e.g. 'Oct 5', 'next Monday') into a datetime object.
    Returns None if parsing fails.
    """
    parsed = dateparser.parse(text)
    if not parsed:
        return None
    return parsed


def extract_travel_entities(user_input: str) -> Dict[str, Any]:
    info = {}
    input_lower = user_input.lower()

    print(f"🔍 Raw input: {user_input}")

    # 📅 Extract travel dates
    date_range_match = re.search(r'from\s+(\d{4}-\d{2}-\d{2})\s+to\s+(\d{4}-\d{2}-\d{2})', input_lower)
    one_way_match = re.search(r'(?:on|departing)\s+(\d{4}-\d{2}-\d{2})', input_lower)

    try:
        if date_range_match:
            info["date_from"] = datetime.strptime(date_range_match.group(1), "%Y-%m-%d")
            info["date_to"] = datetime.strptime(date_range_match.group(2), "%Y-%m-%d")
            info["trip_type"] = "round-trip"
        elif one_way_match:
            info["date_from"] = datetime.strptime(one_way_match.group(1), "%Y-%m-%d")
            info["trip_type"] = "one-way"    
    except ValueError:
        print("⚠️ Invalid date format detected.") 

    print(f"📅 Parsed dates: from={info.get('date_from')} to={info.get('date_to')}")

    # ✈️ Extract origin and destination city names
    origin_match = re.search(r'from\s+([a-zA-Z\s]+?)\s*\(', user_input)
    destination_match = re.search(r'to\s+([a-zA-Z\s]+?)\s*\(', user_input)

    if origin_match:
        info["origin"] = origin_match.group(1).strip()
    if destination_match:
        info["destination"] = destination_match.group(1).strip()

    # ✈️ Extract airport codes from parentheses
    iata_matches = re.findall(r'\(\s*([A-Z]{3})\s*\)', user_input)
    if len(iata_matches) >= 2:
        info["origin_code"] = iata_matches[0].strip().upper()
        info["destination_code"] = iata_matches[1].strip().upper()
    elif len(iata_matches) == 1:
        info["origin_code"] = iata_matches[0].strip().upper()
        info["destination_code"] = ""  # fallback
        
    # 🧠 Optional: fallback if city names weren't matched
    if not info.get("origin") and "origin_code" in info:
        info["origin"] = info["origin_code"]
    if not info.get("destination") and "destination_code" in info:
        info["destination"] = info["destination_code"]

    # 👥 Extract number of passengers
    passengers_match = re.search(r'for\s+(\d+)\s+passengers?', input_lower)
    if passengers_match:
        info["passengers"] = int(passengers_match.group(1))

    print(f"✅ Extracted info: {info}")
    return info


def generate_flight_id(link: str, airline: str, departure: datetime) -> str:
    raw = f"{link}-{airline}-{departure}"
    return hashlib.md5(raw.encode()).hexdigest()


def get_affiliate_link(deeplink):
    """
    Safely wrap the Aviasales deeplink with your affiliate marker.
    """
    marker = os.getenv("AFFILIATE_MARKER")
    return f"{deeplink}?marker={marker}"


# === Helper Functions ===

def extract_iata(value):
    """
    Extracts the IATA code from a string like 'Stockholm Arlanda (ARN)' → 'ARN'
    If already just a code (e.g., 'ARN'), returns as-is.
    """
    if not value:
        return ""
    
    # Check if format is "City Name (CODE)"
    if "(" in value and ")" in value:
        code = value.split("(")[-1].replace(")", "").strip()
        return code.upper()
    
    # If already a 3-letter code
    value = value.strip().upper()
    if len(value) == 3 and value.isalpha():
        return value
    
    return value


def format_ddmm(date_str):
    """
    Convert YYYY-MM-DD to DDMM format for Aviasales deeplink.
    Examples:
      - "2025-12-10" → "1012"
      - "2025-01-05" → "0501"
    """
    try:
        if not date_str:
            return ""
        
        # Handle datetime objects
        if isinstance(date_str, datetime):
            return date_str.strftime("%d%m")
        
        # Handle "YYYY-MM-DD HH:MM" format (extract date part)
        if " " in date_str:
            date_str = date_str.split(" ")[0]
        
        # Parse YYYY-MM-DD
        if len(date_str) == 10 and date_str[4] == "-" and date_str[7] == "-":
            return date_str[8:10] + date_str[5:7]  # DDMM
        
        return ""
    except Exception as e:
        logger.warning(f"Error formatting date {date_str}: {e}")
        return ""


def build_flight_deeplink(flight, marker):
    """
    Build an Aviasales deeplink for a specific flight result.
    
    Flight object can have:
      - depart: "2025-12-10 14:30" (new API format)
      - return: "2025-12-17 18:45" (new API format)
      OR
      - depart_date: "2025-12-10" (old format)
      - return_date: "2025-12-17" (old format)
    
    Returns: https://www.aviasales.com/search/ARN1012LHR1712?marker=...
    """
    try:
        # If flight already has a link, use it
        if flight.get("link"):
            return flight["link"]
        
        if flight.get("deeplink"):
            return flight["deeplink"]
        
        # Get origin and destination
        origin = flight.get("origin", "")
        destination = flight.get("destination", "")
        
        if not origin or not destination:
            logger.warning("Missing origin or destination for deeplink")
            return f"https://www.aviasales.com?marker={marker}"
        
        # Get departure date (try multiple fields)
        depart_date = None
        if flight.get("depart"):
            # Format: "2025-12-10 14:30" or "2025-12-10"
            depart_date = flight["depart"]
        elif flight.get("depart_date"):
            depart_date = flight["depart_date"]
        elif flight.get("departure_date"):
            depart_date = flight["departure_date"]
        
        # Get return date (try multiple fields)
        return_date = None
        if flight.get("return"):
            return_date = flight["return"]
        elif flight.get("return_date"):
            return_date = flight["return_date"]
        
        # Format dates to DDMM
        depart_ddmm = format_ddmm(depart_date)
        return_ddmm = format_ddmm(return_date) if return_date else ""
        
        if not depart_ddmm:
            logger.warning(f"Could not format departure date: {depart_date}")
            return f"https://www.aviasales.com?marker={marker}"
        
        # Build search URL
        search_code = f"{origin}{depart_ddmm}{destination}"
        if return_ddmm:
            search_code += return_ddmm
        
        deeplink = f"https://www.aviasales.com/search/{search_code}"
        
        # Add marker
        if marker:
            deeplink += f"?marker={marker}"
        
        return deeplink
    
    except Exception as e:
        logger.error(f"Error building deeplink: {e}")
        return f"https://www.aviasales.com?marker={marker}"