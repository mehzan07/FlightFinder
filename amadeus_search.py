"""
Amadeus API Integration - REAL, WORKING SOLUTION
✅ Free tier: 2,000 calls/month
...
"""

import requests
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import hashlib
import re # Needed for parse_iso_duration

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


def get_access_token():
    """Get OAuth access token from Amadeus"""
    global _access_token, _token_expiry
    
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
    Search flights using Amadeus API
    
    Returns flights with booking links to partner sites
    """
    
    # Get access token
    token = get_access_token()
    if not token:
        logger.error("Failed to get Amadeus access token")
        return []
    
    # Build API endpoint
    endpoint = f"{AMADEUS_BASE_URL}/v2/shopping/flight-offers"
    
    # Prepare parameters
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
    
    # Add return date for round-trip
    if trip_type == "round-trip" and date_to:
        params["returnDate"] = date_to
    
    # Filter for direct flights
    if direct_only:
        params["nonStop"] = "true"
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json"
    }
    
    logger.info(f"🔍 Searching Amadeus: {origin} → {destination}")
    
    try:
        response = requests.get(endpoint, params=params, headers=headers, timeout=15)
        
        if response.status_code != 200:
            logger.error(f"Amadeus API error: {response.status_code} - {response.text}")
            return []
        
        data = response.json()
        offers = data.get("data", [])
        
        if not offers:
            logger.warning("No flights found from Amadeus")
            return []
        
        logger.info(f"✅ Found {len(offers)} flights from Amadeus")
        
        # Parse and format flights
        flights = []
        for offer in offers:
            parsed = parse_amadeus_flight(offer, trip_type, origin, destination)
            if parsed:
                flights.append(parsed)
        
        return flights[:limit]
    
    except requests.exceptions.RequestException as e:
        logger.error(f"Amadeus API request failed: {e}")
        return []
    except Exception as e:
        logger.error(f"Error processing Amadeus response: {e}")
        return []


def parse_amadeus_flight(offer: Dict, trip_type: str, origin: str, destination: str) -> Optional[Dict]:
    """Parse Amadeus flight offer into our standard format"""
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
        
        # Extract times
        depart_time = first_segment.get("departure", {}).get("at", "")
        arrive_time = last_segment.get("arrival", {}).get("at", "")
        
        # Format times to "YYYY-MM-DD HH:MM"
        depart_formatted = format_amadeus_datetime(depart_time)
        arrive_formatted = format_amadeus_datetime(arrive_time)
        
        # Return flight (for round-trip)
        return_depart_formatted = None
        return_arrive_formatted = None
        
        if trip_type == "round-trip" and len(itineraries) > 1:
            return_flight = itineraries[1]
            return_segments = return_flight.get("segments", [])
            
            if return_segments:
                return_first = return_segments[0]
                return_last = return_segments[-1]
                
                return_depart_formatted = format_amadeus_datetime(
                    return_first.get("departure", {}).get("at", "")
                )
                return_arrive_formatted = format_amadeus_datetime(
                    return_last.get("arrival", {}).get("at", "")
                )
        
        # Get airline
        carrier_code = first_segment.get("carrierCode", "")
        flight_number = first_segment.get("number", "")
        
        # Calculate stops
        stops = len(outbound_segments) - 1
        
        # Duration
        duration_str = outbound.get("duration", "PT0H0M")
        duration_minutes = parse_iso_duration(duration_str)
        duration_formatted = format_duration(duration_minutes)
        
        # Price
        price_info = offer.get("price", {})
        price = float(price_info.get("total", 0))
        currency = price_info.get("currency", "EUR")
        
        # ✅ FIX: BUILD BOOKING LINK WITH AFFILIATE MARKER
        depart_date_only = depart_time[:10] if depart_time else ""
        return_date_only = return_depart_formatted[:10] if return_depart_formatted else None
        
        # Format dates to DDMM for Aviasales
        def date_to_ddmm(date_str):
            """Convert YYYY-MM-DD to DDMM"""
            if not date_str or len(date_str) < 10:
                return ""
            return date_str[8:10] + date_str[5:7]
        
        depart_ddmm = date_to_ddmm(depart_date_only)
        
        # Build Aviasales search code
        search_code = f"{origin}{depart_ddmm}{destination}"
        
        if return_date_only:
            return_ddmm = date_to_ddmm(return_date_only)
            search_code += return_ddmm
        
        # Build Aviasales URL with flight details
        booking_link = f"https://www.aviasales.com/search/{search_code}"
        # ✅ FIX APPLIED: Added marker={AFFILIATE_MARKER}
        booking_link += f"?marker={AFFILIATE_MARKER}&adults=1&currency=eur&with_request=true"
        
        # Add airline filter to help find the exact flight
        if carrier_code:
            booking_link += f"&airlines={carrier_code}"
        
        # Add direct flights filter if applicable
        if stops == 0:
            booking_link += "&transfers=0"
        
        # Generate unique ID
        flight_id = hashlib.md5(
            f"{offer_id}_{depart_time}".encode()
        ).hexdigest()
        
        # Build standardized flight object
        return {
            "id": flight_id,
            "airline": carrier_code,
            "flight_number": f"{carrier_code}{flight_number}",
            "depart": depart_formatted,
            "return": return_arrive_formatted if trip_type == "round-trip" else arrive_formatted,
            "return_depart": return_depart_formatted,
            "origin": origin,
            "destination": destination,
            "duration": duration_formatted,
            "duration_minutes": duration_minutes,
            "stops": stops,
            "price": int(price),
            "currency": currency,
            "vendor": "Flight Finder",
            "link": booking_link,
            "deeplink": booking_link,
            "trip_type": trip_type,
            "cabin_class": "Economy",
            "offer_id": offer_id  # Store for later booking API call
        }
    
    except Exception as e:
        logger.error(f"Error parsing Amadeus flight: {e}")
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