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



#=== Helper Functions ===

def extract_iata(value):
    """
    Extracts the IATA code from a string like 'Stockholm Arlanda (ARN)' → 'ARN'
    """
    if "(" in value and ")" in value:
        return value.split("(")[-1].replace(")", "").strip()
    return value.strip()


def build_flight_deeplink(flight, marker):
    """
    Build an Aviasales deeplink for a specific flight result.
    Dates must be formatted as DDMM.
    """
    def format_ddmm(date_str):
        return date_str[8:10] + date_str[5:7]  # YYYY-MM-DD → DDMM

    origin = flight.get("origin")
    destination = flight.get("destination")
    depart_date = flight.get("depart_date")
    return_date = flight.get("return_date")

    deeplink = f"https://www.aviasales.com/search/{origin}{format_ddmm(depart_date)}{destination}"
    if return_date:
        deeplink += format_ddmm(return_date)

    return f"{deeplink}?marker={marker}"