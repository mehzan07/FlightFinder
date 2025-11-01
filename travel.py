# travel.py — core travel chatbot logic and form handler

from utils import extract_travel_entities
from flight_search import search_flights
from iata_codes import city_to_iata
from mock_data import AIRLINE_NAMES  # ✅ Added import
from datetime import date, datetime
from flask import request

import random
import string
from datetime import datetime
from database import db

from config import AFFILIATE_MARKER

from config import get_logger
logger = get_logger(__name__)


def generate_affiliate_link(origin, destination, date_from, date_to, passengers):
    base_url = "https://www.aviasales.com/search"
    search_code = f"{origin.upper()}{date_from.strftime('%d%m')}{destination.upper()}{date_to.strftime('%d%m')}"
    return f"{base_url}/{search_code}?adults={passengers}&utm_source={AFFILIATE_MARKER}"


def travel_chatbot(user_input: str, trip_type: str = "round-trip", limit=None, direct_only=False) -> dict:
    info = extract_travel_entities(user_input)
    print("Extracted info:", info)
    logger.info(f"Extracted info: {info}")

    if not info:
        return {
            "flights": [],
            "message": "🛫 I couldn't extract any travel details. Try something like: 'Fly from Berlin to Madrid on September 10.'",
            "summary": None,
            "affiliate_link": None,
            "trip_info": {}
        }

    missing_fields = []

    if not info.get("origin"):
        missing_fields.append("origin city")
    if not info.get("destination"):
        missing_fields.append("destination city")
    if "date_from" not in info or not isinstance(info["date_from"], (datetime, date)):
        missing_fields.append("departure date")
    
        
    if trip_type != "one-way":
        if "date_to" not in info or not isinstance(info["date_to"], (datetime, date)):
            missing_fields.append("return date")

    if missing_fields:
        return {
            "flights": [],
            "message": f"🧳 I need a bit more info. Please include your {' and '.join(missing_fields)}.",
            "summary": None,
            "affiliate_link": None,
            "trip_info": {}
        }

    if trip_type != "one-way" and info["date_from"] > info["date_to"]:
        return {
            "flights": [],
            "message": "⏳ Your return date must be after your departure date.",
            "summary": None,
            "affiliate_link": None,
            "trip_info": {}
        }
      # this is for demo:
    # origin_code = city_to_iata.get(info["origin"].lower())
    # destination_code = city_to_iata.get(info["destination"].lower())
    # logger.info(f"Origin IATA: {origin_code}, Destination IATA: {destination_code}")
    
    # in real api call:
    origin_code = info["origin_code"].upper()
    destination_code = info["destination_code"].upper()
    logger.info(f"origin_code: {origin_code}, destination_code: {destination_code}")

    if not origin_code or not destination_code:
        sample_cities = ", ".join(list(city_to_iata.keys())[:5])
        return {
            "flights": [],
            "message": f"🌍 I couldn't recognize one of the cities. Try using major cities like: {sample_cities}.",
            "summary": None,
            "affiliate_link": None,
            "trip_info": {}
        }

    trip_type = info.get("trip_type")
    if trip_type not in ["one-way", "round-trip"]:
        trip_type = "one-way"  # safer default

    date_from_str = info["date_from"].strftime("%Y-%m-%d") if info.get("date_from") else ""
    date_to_str = info["date_to"].strftime("%Y-%m-%d") if info.get("date_to") else ""
    passengers = info.get("passengers", 1)
    
    adults = int(request.form.get("passengers", 1))
    cabin_class = request.form.get("cabin_class", "economy")
    children = 0  # You can add a form field later if needed
    infants = 0   # Same here 
          

    flights = search_flights(
    origin_code,
    destination_code,
    date_from_str,
    date_to_str,
    trip_type,
    adults=adults,
    children=children,
    infants=infants,
    cabin_class=cabin_class,
    limit=limit,
    direct_only=direct_only
    )

    if not flights:
        if direct_only:
            message = "😕 No direct flights found. Please try a different search with change of depart or/and Return date"
            logger.info(message)
            return {
                "flights": [],
                "message": message,
                "summary": None,
                "affiliate_link": None,
                "trip_info": {}
            }

        else:
            return {
                "flights": [],
                "message": "😕 No flights found for Returen. Please try a different search with depart and Return date ",
                "summary": None,
                "affiliate_link": None,
                "trip_info": {}
            }
    else:
        nr = len(flights)
        # print("{} Flights found.".format(nr))
        logger.info("{} Flights found for your search limit= {}".format(nr, limit))

    # ✅ Prepare flight data for template
    prepared_flights = []
    sorted_flights = sorted(flights, key=lambda x: x["price"])
    
    for flight in sorted_flights:
        airline_code = flight.get("airline", "Unknown")
        airline_name = AIRLINE_NAMES.get(airline_code, airline_code)

        trip_type = flight.get("trip_type", "round-trip")  # fallback if missing


        prepared_flights.append({
            "id": flight["id"],
            "price": flight.get("price"),
            "depart": flight.get("depart"),
            "return": flight.get("return"),
            "airline": airline_name,
            "flight_number": flight.get("flight_number", "N/A"),
            "duration": flight.get("duration", "N/A"),
            "stops": flight.get("stops", 0),
            "cabin_class": flight.get("cabin_class", "Economy"),
            "vendor": flight.get("vendor", "Unknown"),
            "origin": flight.get("origin", "Unknown"),
            "destination": flight.get("destination", "Unknown"),
            "link": flight.get("link"),
            "trip_type": trip_type
        })

    # Debug print
    print("Prepared flight IDs:", [f.get("id") for f in prepared_flights])

    affiliate_link = (
        prepared_flights[0]["link"]
        if prepared_flights and prepared_flights[0].get("link")
        else generate_affiliate_link(origin_code, destination_code, info["date_from"], info["date_to"], passengers)
    )

    trip_info = {
    "origin": info["origin_code"],
    "destination": info["destination_code"],
    "departure_date": info["date_from"].strftime('%Y-%m-%d') if info.get("date_from") else "",
    "passengers": passengers,
    "trip_type": trip_type
}
    errors = []
    if trip_type == "round-trip":
        trip_info["return_date"] = info["date_to"].strftime('%Y-%m-%d') if info.get("date_to") else ""

    if trip_type == "one-way":
        summary = (
        f"You're taking a one-way trip from {info['origin']} to {info['destination']} "
        f"on {info['date_from'].strftime('%B %d, %Y')} with {passengers} passenger(s)."
       )
    else:
        if trip_type == "round-trip" and not info.get("date_to"):
            errors.append("Return date is required for round-trip.")
        summary = (
            f"You're taking a round-trip from {info['origin']} to {info['destination']} "
            f"from {info['date_from'].strftime('%B %d, %Y')} to {info['date_to'].strftime('%B %d, %Y')} "
            f"with {passengers} passenger(s)."
            )
 

    return {
        "flights": prepared_flights,
        "message": None,
        "summary": summary,
        "affiliate_link": affiliate_link,
        "trip_info": trip_info
    }


def travel_form_handler(form_data):
    origin = form_data.get("origin", "").strip()
    destination = form_data.get("destination", "").strip()
    departure_date = form_data.get("departure_date", "")
    return_date = form_data.get("return_date", "")
    passengers = int(form_data.get("passengers", 1))
    # budget = float(form_data.get("budget", 0))s

    # Mock result — replace with real API call or logic
    results = {
        "origin": origin,
        "destination": destination,
        "departure_date": departure_date,
        "return_date": return_date,
        "passengers": passengers,
        "flights": [
            {
                "airline": "SkyFly",
                "price": 320,
                "duration": "6h 45m",
                "stops": "Non-stop"
            },
            {
                "airline": "JetNova",
                "price": 280,
                "duration": "8h 10m",
                "stops": "1 stop"
            }
        ]
    }

    return results



def generate_booking_reference():
    prefix = "FF"
    date_str = datetime.now().strftime("%Y%m%d")
    random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
    return f"{prefix}-{date_str}-{random_str}"