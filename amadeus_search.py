"""
Amadeus API Integration - REAL, WORKING SOLUTION
✅ Free tier: 2,000 calls/month
...
"""

import requests
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import hashlib
import re 
from utils import parse_iso_duration, format_duration 
from typing import Dict, Optional
import traceback
import json
import os


from config import get_logger
logger = get_logger(__name__) 


# ============================================
# CONFIGURATION - Load from config.py
# ============================================

# ✅ FIX: Added AFFILIATE_MARKER to the import list
from config import AMADEUS_API_KEY, AMADEUS_API_SECRET, AMADEUS_BASE_URL, AFFILIATE_MARKER

# Don't hardcode these - they come from .env via config.py
if not AMADEUS_API_KEY or not AMADEUS_API_SECRET:
    raise ValueError("Amadeus API credentials not configured. Check your .env file!")

# Use the base URL from config (test vs production)
# AMADEUS_BASE_URL is already set from config.py

# Cache for access token (Amadeus requires OAuth)
_access_token = None
_token_expiry = None

TOKEN_FILE = "/home/mehzan07/amadeus_token.json"

def get_access_token():
    """Get OAuth access token from Amadeus"""
    global _access_token, _token_expiry
    
    # 1. Try to load token from a file instead of memory
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, 'r') as f:
            cache = json.load(f)
            expiry = datetime.fromisoformat(cache['expiry'])
            if datetime.now() < expiry:
                return cache['token']
    
    # Check if we have a valid cached token
    if _access_token and _token_expiry and datetime.now() < _token_expiry:
        return _access_token
    
    # Request new token
    token_url = f"{AMADEUS_BASE_URL}/v1/security/oauth2/token"
    
    payload = {
        "grant_type": "client_credentials",
        "client_id": AMADEUS_API_KEY,
        "client_secret": AMADEUS_API_SECRET
    }
    
    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }
    
    try:
        response = requests.post(token_url, data=payload, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            _access_token = data.get("access_token")
            expires_in = data.get("expires_in", 1800)  # Default 30 minutes
            
            _token_expiry = datetime.now() + timedelta(seconds=expires_in - 60)
            
            logger.info("✅ Amadeus token obtained")
            return _access_token
        else:
            logger.error(f"Token request failed: {response.status_code}")
            return None
            
    except Exception as e:
        logger.error(f"Error getting Amadeus token: {e}")
        return None



# Assume logger, AMADEUS_BASE_URL, AFFILIATE_MARKER, get_access_token, 
# map_cabin_class, parse_iso_duration, format_duration, and parse_amadeus_flight 
# are available/imported correctly.

def search_flights_amadeus(
    origin: str,
    destination: str,
    date_from: str,
    date_to: str = None,
    trip_type: str = "round-trip",
    adults: int = 1,
    children: int = 0,
    infants: int = 0,
    cabin_class: str = "economy",
    limit: int = 4,
    direct_only: bool = False
) -> List[Dict]:
    """
    Search flights using Amadeus API, with robust error handling.
    """
    
    # -------------------------------------------------------------
    # 1. SETUP AND AUTHENTICATION
    # -------------------------------------------------------------
    token = get_access_token()
    if not token:
        logger.error("Failed to get Amadeus access token")
        return [] # FIXED: lowercase return
    
    endpoint = f"{AMADEUS_BASE_URL}/v2/shopping/flight-offers"
    
    params = {
        "originLocationCode": origin,
        "destinationLocationCode": destination,
        "departureDate": date_from,
        "adults": adults,
        "children": children,
        "infants": infants,
        "currencyCode": "EUR",
        "max": limit,
        "travelClass": map_cabin_class(cabin_class)
    }
    
    if trip_type == "round-trip" and date_to:
        params["returnDate"] = date_to
    
    if direct_only:
        params["nonStop"] = "true"
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json"
    }
    
    logger.info(f"🔍 Searching Amadeus: {origin} → {destination} (Depart: {date_from})")
    
    # -------------------------------------------------------------
    # 2. API CALL AND ERROR HANDLING
    # -------------------------------------------------------------
    try:
        # --- API CALL ---
        response = requests.get(endpoint, params=params, headers=headers, timeout=10)
        
        # --- HTTP ERROR CHECK ---
        if response.status_code != 200:
            logger.error(f"❌ Amadeus HTTP Error {response.status_code}: {response.text}")
            return []
        
        # --- DATA CHECK ---
        data = response.json()
        offers = data.get("data", [])
        
        if not offers:
            logger.warning("⚠️ No flights found from Amadeus for criteria.")
            return []
            
        # --- 3. SUCCESS/PARSING LOGIC ---
        logger.info(f"✅ Found {len(offers)} raw offers from Amadeus. Starting parsing.")
        
        flights = []
        for offer in offers:
            # Assuming parse_amadeus_flight is correctly defined and available
            parsed = parse_amadeus_flight(offer, trip_type, origin, destination, direct_only) 
            if parsed:
                flights.append(parsed)
                
        # CRITICAL: Return the final list of successfully parsed flights
        logger.info(f"Successfully parsed {len(flights)} flight offers.")
        return flights[:limit] 

    # --- 4. FAILSAFE EXCEPTION CATCHES ---
    except requests.exceptions.RequestException as e:
        logger.error(f"Amadeus API request failed (Network/Timeout): {e}")
        return []
    except Exception as e:
        logger.critical(f"🛑 FATAL EXCEPTION in search_flights_amadeus: {e}")
        traceback.print_exc()
        return []

# ----------------------------------------------------------------------
# 5. parse_amadeus_flight HELPER FUNCTION (PROVIDED BY USER, CLEANED UP)
# ----------------------------------------------------------------------

def parse_amadeus_flight(offer: Dict, trip_type: str, origin: str, destination: str, direct_only: bool) -> Optional[Dict]:
    """
    Parse Amadeus flight offer into our standard format.
    (Body of the function remains the same as provided by the user)
    """
    try:
        # offer_id must be extracted for the unique MD5 ID generation
        offer_id = offer.get("id", "")
        
        # Get itineraries (outbound and return)
        itineraries = offer.get("itineraries", [])
        if not itineraries:
            return None
        
        # Outbound flight
        outbound = itineraries[0]
        outbound_segments = outbound.get("segments", [])
        
        if not outbound_segments:
            return None
        
        first_segment = outbound_segments[0]
        last_segment = outbound_segments[-1]
        
        # Extract raw times (e.g., "2025-12-12T10:30:00+01:00")
        depart_time_raw = first_segment.get("departure", {}).get("at", "")
        arrive_time_raw = last_segment.get("arrival", {}).get("at", "")
        
        # --- CRITICAL FIX: Robust, Standardized Datetime Formatting ---
        def standardize_datetime(raw_iso_time: str) -> str:
            if not raw_iso_time:
                return ""
            try:
                # Replace 'Z' (UTC marker) and ensure consistency for parsing
                iso_time_clean = raw_iso_time.replace('Z', '+00:00')
                # Parse the ISO string (handles T and timezones)
                dt_object = datetime.fromisoformat(iso_time_clean) 
                # Convert back to a standardized, non-timezone-aware string (the target format)
                return dt_object.strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                return ""
            
        depart_formatted = standardize_datetime(depart_time_raw)
        arrive_formatted = standardize_datetime(arrive_time_raw)
        
        # Return flight (for round-trip)
        return_depart_formatted = None
        return_arrive_formatted = None
        
        if trip_type == "round-trip" and len(itineraries) > 1:
            return_flight = itineraries[1]
            return_segments = return_flight.get("segments", [])
            
            if return_segments:
                return_first = return_segments[0]
                return_last = return_segments[-1]
                
                return_depart_formatted = standardize_datetime(
                    return_first.get("departure", {}).get("at", "")
                )
                return_arrive_formatted = standardize_datetime(
                    return_last.get("arrival", {}).get("at", "")
                )

        # Get airline
        carrier_code = first_segment.get("carrierCode", "")
        flight_number = first_segment.get("number", "")
        
        # Calculate stops
        stops = len(outbound_segments) - 1
        
        # Duration
        duration_str = outbound.get("duration", "PT0H0M")
        # NOTE: parse_iso_duration and format_duration must be defined in utils.py
        duration_minutes = parse_iso_duration(duration_str) 
        duration_formatted = format_duration(duration_minutes)
        
        # Price
        price_info = offer.get("price", {})
        price = float(price_info.get("total", 0))
        currency = price_info.get("currency", "EUR")
        
        # --- Build Booking Link (Temporary Aviasales Search Link) ---
        depart_date_only = depart_time_raw[:10] if depart_time_raw else ""
        return_date_only = return_depart_formatted[:10] if return_depart_formatted else None
        
        def date_to_ddmm(date_str):
            if not date_str or len(date_str) < 10:
                return ""
            return date_str[8:10] + date_str[5:7]
        
        depart_ddmm = date_to_ddmm(depart_date_only)
        search_code = f"{origin}{depart_ddmm}{destination}"
        
        if return_date_only:
            return_ddmm = date_to_ddmm(return_date_only)
            search_code += return_ddmm
        
        # Ensure AFFILIATE_MARKER is available in scope
        booking_link = f"https://www.aviasales.com/search/{search_code}"
        booking_link += f"?marker={AFFILIATE_MARKER}&adults=1&currency=eur&with_request=true"
        
        if carrier_code:
            booking_link += f"&airlines={carrier_code}"
        if direct_only:
            booking_link += "&transfers=0"
            booking_link += "&direct=true" 
        
        # Generate unique ID 
        flight_id = hashlib.md5(
            f"{offer_id}_{depart_time_raw}".encode()
        ).hexdigest()
        
        # Build standardized flight object
        return {
            "id": flight_id,
            "airline": carrier_code,
            "flight_number": f"{carrier_code}{flight_number}",
            "depart": depart_formatted, # GUARANTEED YYYY-MM-DD HH:MM:SS
            "return": return_arrive_formatted if trip_type == "round-trip" else arrive_formatted,
            "return_depart": return_depart_formatted,
            "origin": origin,
            "destination": destination,
            "stops": stops,
            "duration": duration_formatted,
            "price": price,
            "currency": currency,
            "link": booking_link, # Default link
            "deeplink": booking_link, # Placeholder for deeplink
            "vendor": "Amadeus (Aviasales Search)",
        }
    
    except Exception as e:
        logger.error(f"Error parsing Amadeus flight: {e}")
        # traceback.print_exc() # Can uncomment if needed for deep debugging
        return None




def format_amadeus_datetime(dt_str: str) -> str:
    # ... (rest of the helper function code is unchanged)
    try:
        if not dt_str:
            return ""
        
        # Parse ISO format
        dt = datetime.fromisoformat(dt_str.replace("Z", ""))
        return dt.strftime("%Y-%m-%d %H:%M")
    
    except Exception as e:
        logger.warning(f"Error formatting datetime {dt_str}: {e}")
        return dt_str


def parse_iso_duration(duration_str: str) -> int:
    """
    Parse ISO 8601 duration to minutes
    Example: "PT5H30M" -> 330 minutes
    """
    # import re is moved to the top of the file
    
    try:
        hours = 0
        minutes = 0
        
        hour_match = re.search(r'(\d+)H', duration_str)
        if hour_match:
            hours = int(hour_match.group(1))
        
        minute_match = re.search(r'(\d+)M', duration_str)
        if minute_match:
            minutes = int(minute_match.group(1))
        
        return hours * 60 + minutes
    
    except Exception:
        return 0


def format_duration(minutes: int) -> str:
    # ... (rest of the helper function code is unchanged)
    if not minutes:
        return "N/A"
    
    hours = minutes // 60
    mins = minutes % 60
    
    if hours > 0 and mins > 0:
        return f"{hours}h {mins}m"
    elif hours > 0:
        return f"{hours}h"
    else:
        return f"{mins}m"


def map_cabin_class(cabin_class: str) -> str:
    # ... (rest of the helper function code is unchanged)
    mapping = {
        "economy": "ECONOMY",
        "business": "BUSINESS",
        "first": "FIRST"
    }
    return mapping.get(cabin_class.lower(), "ECONOMY")


def build_google_flights_link(origin: str, destination: str, depart_date: str, return_date: str = None) -> str:
    # ... (rest of the helper function code is unchanged)
    import urllib.parse
    
    # Base URL
    base = "https://www.google.com/travel/flights"
    
    # Format dates for Google (remove hyphens)
    depart_formatted = depart_date.replace("-", "")  # 2025-12-10 -> 20251210
    
    if return_date:
        # Round-trip
        return_formatted = return_date.replace("-", "")
        
        # Build the search query
        # Google Flights uses a complex query format
        search_params = {
            "tfs": f"CBwQAhonag0IAxIJL20vMDVxdGoSA{origin}GgIIAhIDe{destination}GgIIAXACggELCP___________wFAAUgBmAEB"
        }
        
        # Simpler approach: Just use basic search format
        url = f"{base}?hl=en&curr=EUR"
        url += f"#flt={origin}.{destination}.{depart_formatted}"
        
        if return_date:
            url += f"*{destination}.{origin}.{return_formatted}"
        
        return url
    else:
        # One-way
        url = f"{base}?hl=en&curr=EUR"
        url += f"#flt={origin}.{destination}.{depart_formatted}"
        return url


# ============================================
# BOOKING API (Advanced - Optional)
# ============================================

def create_flight_order(offer_id: str, passenger_info: Dict) -> Dict:
# ... (rest of the function is unchanged)
    """
    Create actual booking using Amadeus Flight Create Orders API
    
    This is advanced - requires full passenger details
    Returns booking confirmation
    """
    token = get_access_token()
    if not token:
        return {"success": False, "error": "No access token"}
    
    endpoint = f"{AMADEUS_BASE_URL}/v1/booking/flight-orders"
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "data": {
            "type": "flight-order",
            "flightOffers": [{"id": offer_id}],
            "travelers": [passenger_info]
        }
    }
    
    try:
        response = requests.post(endpoint, json=payload, headers=headers, timeout=15)
        
        if response.status_code == 201:
            data = response.json()
            return {
                "success": True,
                "booking_reference": data.get("data", {}).get("associatedRecords", [{}])[0].get("reference", ""),
                "data": data
            }
        else:
            logger.error(f"Booking failed: {response.status_code} - {response.text}")
            return {"success": False, "error": response.text}
    
    except Exception as e:
        logger.error(f"Booking error: {e}")
        return {"success": False, "error": str(e)}