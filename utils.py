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
from config import AFFILIATE_MARKER
marker = AFFILIATE_MARKER or os.getenv("AFFILIATE_MARKER", "")

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


def extract_iata(text):
    if not text: return ""
    # Look for 3 capital letters inside parentheses: (LHR)
    match = re.search(r'\(([A-Z]{3})\)', text)
    if match:
        return match.group(1)
    # If no parentheses, look for any 3 capital letters at the end or start
    match = re.search(r'\b([A-Z]{3})\b', text)
    if match:
        return match.group(1)
    # Fallback: just take the last 3 chars if they look like a code
    clean = text.strip()
    if len(clean) >= 3:
        return clean[-3:]
    return text




def format_ddmm(date_val):
    if not date_val: 
        return ""
    
    # 1. Handle if it's already a datetime object
    if isinstance(date_val, datetime):
        return date_val.strftime("%d%m")
    
    try:
        # 2. Clean the string: Remove time (T00:00) and extra spaces
        # Works for "2025-12-10T10:30" or "2025-12-10 10:30"
        date_str = str(date_val).split('T')[0].split(' ')[0].strip()
        
        # 3. Handle YYYY-MM-DD format
        if '-' in date_str:
            parts = date_str.split('-')
            if len(parts) == 3:
                day = parts[2].zfill(2)   # Ensures "5" becomes "05"
                month = parts[1].zfill(2) # Ensures "1" becomes "01"
                return f"{day}{month}"
        
        # 4. Fallback: Try a generic parse if format is weird (e.g., "12/10/2025")
        parsed = dateparser.parse(date_str)
        if parsed:
            return parsed.strftime("%d%m")
            
    except Exception as e:
        logger.warning(f"Could not format date '{date_val}': {e}")
        
    return ""
    
    
from utils import extract_iata # Ensure this is imported


def build_flight_deeplink(flight, marker, currency="SEK"):
    """
    Reconstructed 'Golden Version' link builder.
    Uses the exact path-based logic that worked in version 4e0f30e.
    """
    try:
        trip_type = flight.get("trip_type", "round-trip")
        adults_count = str(flight.get("adults") or flight.get("passengers") or "1")
        
        # 1. Start with the basics (Leg 1)
        origin1 = clean_iata(str(flight.get("origin_code") or flight.get("origin", "")))
        dest1 = clean_iata(str(flight.get("destination_code") or flight.get("destination", "")))
        
        # Extract date and convert to DDMM (e.g., 2025-12-15 -> 1512)
        raw_date1 = flight.get("depart_date") or flight.get("depart")
        date1 = format_ddmm(raw_date1)

        # Base path: ORIGIN + DATE + DEST
        search_path = f"{origin1}{date1}{dest1}"

        # 2. Handle Multi-city (The "Chain" Logic from old flight_search.py)
        if trip_type == "multi-city":
            # The old code just appends DATE2 + DEST2 to the end
            raw_date2 = flight.get("depart_date_2") or flight.get("date_2")
            dest2_raw = flight.get("destination_code_2") or flight.get("destination_2")
            
            if raw_date2 and dest2_raw:
                date2 = format_ddmm(raw_date2)
                dest2 = clean_iata(str(dest2_raw))
                # Result: ARN1203LHR + 1503 + CDG = ARN1203LHR1503CDG
                search_path += f"{date2}{dest2}"

        # 3. Handle Round-trip
        elif trip_type == "round-trip":
            raw_date_to = flight.get("return_date") or flight.get("return")
            if raw_date_to:
                search_path += format_ddmm(raw_date_to)

        # 4. Final Search Code (Path + Adult Digit)
        # In the old code, the adult count is the LAST character
        search_code = f"{search_path}{adults_count}"

        # 5. Build Final Link
        # Note: We use the HOST from config if available, or default to aviasales.com
        from config import HOST
        base_host = HOST if 'HOST' in locals() else "www.aviasales.com"
        
        return f"https://{base_host}/search/{search_code}?marker={marker}&currency={currency}"

    except Exception as e:
        logger.error(f"Error building deeplink: {e}")
        return f"https://www.aviasales.com/?marker={marker}"





    
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

# A dictionary of common airport codes for quick lookup
AIRPORT_MAPPING = {
    # Nordic / Scandinavia
    "ARN": "Stockholm (ARN)",
    "BMA": "Stockholm (BMA)",
    "GOT": "Gothenburg (GOT)",
    "CPH": "Copenhagen (CPH)",
    "OSL": "Oslo (OSL)",
    "HEL": "Helsinki (HEL)",
    "KEF": "Reykjavik (KEF)",

    # Europe
    "LHR": "London (LHR)",
    "LGW": "London (LGW)",
    "STN": "London (STN)",
    "CDG": "Paris (CDG)",
    "ORY": "Paris (ORY)",
    "FRA": "Frankfurt (FRA)",
    "MUC": "Munich (MUC)",
    "AMS": "Amsterdam (AMS)",
    "MAD": "Madrid (MAD)",
    "BCN": "Barcelona (BCN)",
    "FCO": "Rome (FCO)",
    "ZRH": "Zurich (ZRH)",
    "VIE": "Vienna (VIE)",
    "IST": "Istanbul (IST)",
    "ATH": "Athens (ATH)",
    "DUB": "Dublin (DUB)",

    # North America
    "JFK": "New York (JFK)",
    "EWR": "Newark (EWR)",
    "LAX": "Los Angeles (LAX)",
    "ORD": "Chicago (ORD)",
    "SFO": "San Francisco (SFO)",
    "MIA": "Miami (MIA)",
    "YYZ": "Toronto (YYZ)",

    # Middle East & Asia
    "DXB": "Dubai (DXB)",
    "DOH": "Doha (DOH)",
    "SIN": "Singapore (SIN)",
    "HND": "Tokyo (HND)",
    "NRT": "Tokyo (NRT)",
    "HKG": "Hong Kong (HKG)",
    "BKK": "Bangkok (BKK)",
    "SYD": "Sydney (SYD)",
}

def get_city_name(iata_code):
    """Returns 'City (IATA)' if found, otherwise just the IATA code."""
    if not iata_code:
        return ""
    # Normalize to uppercase and strip whitespace
    code = str(iata_code).upper().strip()
    return AIRPORT_MAPPING.get(code, code)