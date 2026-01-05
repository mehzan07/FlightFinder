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

def build_flight_deeplink(flight, marker, currency="SEK"):
    # Keep IS_PRODUCTION = False while on localhost
    IS_PRODUCTION = True
    MY_DOMAIN = "flights.softsolutionsahand.com" 
    
    domain = MY_DOMAIN if IS_PRODUCTION else "www.aviasales.com"

    try:
        origin = flight.get("origin", "").upper()
        destination = flight.get("destination", "").upper()
        d_code = format_ddmm(flight.get("depart") or flight.get("depart_date"))
        r_val = flight.get("return") or flight.get("return_date")
        r_code = format_ddmm(r_val) if r_val else ""
        
        # Format: ORG1505DEST1 (The '1' is for 1 Adult)
        search_path = f"{origin}{d_code}{destination}{r_code}1"
        
        # Adding currency ensures the user sees SEK immediately on the next page
        if IS_PRODUCTION:
            return f"https://{domain}/?flightSearch={search_path}&marker={marker}&currency={currency}"
        else:
            return f"https://{domain}/search/{search_path}?marker={marker}&currency={currency}"

    except Exception:
        return f"https://{domain}?marker={marker}"

    

from datetime import timedelta
import re
from typing import Optional

def parse_iso_duration(duration_str: str) -> timedelta:
    """
    Parses an ISO 8601 duration string (e.g., 'PT1H30M', 'P1D') into a timedelta object.
    
    Amadeus provides duration in this format.
    """
    if not duration_str:
        return timedelta()
        
    # Regex to find P, T, H, M, S components
    duration_regex = re.compile(
        r'P(?:(?P<days>\d+)D)?(?:T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?)?'
    )
    match = duration_regex.match(duration_str)
    
    if not match:
        return timedelta()
        
    parts = match.groupdict()
    
    # Convert parts to integers, defaulting to 0 if not present
    return timedelta(
        days=int(parts.get('days') or 0),
        hours=int(parts.get('hours') or 0),
        minutes=int(parts.get('minutes') or 0),
        seconds=int(parts.get('seconds') or 0)
    )

def format_duration(duration_td: timedelta) -> str:
    """
    Formats a timedelta object into a human-readable string (e.g., '1h 30m').
    """
    total_seconds = int(duration_td.total_seconds())
    
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    
    parts = []
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    
    return " ".join(parts) if parts else "0m"


def to_ddmm(date_str: Optional[str]) -> str:
    """
    Converts a YYYY-MM-DD date string to a DDMM format used for Travelpayouts manual links.
    """
    if not date_str or len(date_str) < 10: 
        return ""
    
    # Example: "2025-12-15" -> "1512"
    return date_str[8:10] + date_str[5:7]

def clean_iata(value):
    """Extracts 'ARN' from 'Stockholm (ARN)' or 'ARN'"""
    match = re.search(r'\((\w{3})\)', value)
    return match.group(1).upper() if match else value.strip().upper()[:3]