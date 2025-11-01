from flask import Blueprint, redirect, render_template, request, jsonify, url_for,session
from travel import travel_chatbot
from datetime import datetime
from config import DEBUG_MODE, FEATURED_FLIGHT_LIMIT
import json
from database import db
import traceback


from utils import extract_travel_entities
from flight_search import search_flights
from iata_codes import city_to_iata

from travel import generate_booking_reference  # ✅ import from travel.py
from travel import travel_form_handler

from models import Booking, db
from travel import generate_booking_reference
from models import Booking
from db import save_booking


from config import get_logger
logger = get_logger(__name__)


offers_db = {}
travel_bp = Blueprint("travel", __name__) 

def format_datetime(dt_str):
    try:
        dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
        return dt.strftime("%b %d, %H:%M")
    except Exception:
        return "Not available"
    
    
    
    
@travel_bp.route("/travel-ui", methods=["GET", "POST"])
def travel_ui():
    logger.info("travel_ui route hit")
    logger.debug(f"Request method: {request.method}")
    print("DEBUG_MODE is:", DEBUG_MODE)

    # ✅ Always initialize these to avoid UnboundLocalError
    form_data = {}
    flights = []
    errors = []

    if request.method == "POST":
        limit = request.form.get("limit", FEATURED_FLIGHT_LIMIT, type=int)
    else:
        limit = request.args.get("limit", FEATURED_FLIGHT_LIMIT, type=int)

    if request.method == "POST":
        origin_code = request.form.get("origin_code", "").strip()
        destination_code = request.form.get("destination_code", "").strip()
        date_from_raw = request.form.get("date_from", "").strip()
        date_to_raw = request.form.get("date_to", "").strip()
        passengers_raw = request.form.get("passengers", "1").strip()
        cabin_class = request.form.get("cabin_class", "").strip()
        trip_type = request.form.get("trip_type", "round-trip").strip()
        direct_only = request.form.get("direct_only") == "on"

        errors = []
        if trip_type != "one-way" and not date_to_raw:
            errors.append("Return date is required for round-trip.")

        form_data = request.form.copy()
        form_data["direct_only"] = direct_only

        date_from = date_to = None
        if not origin_code:
            errors.append("Origin airport is required.")
            if DEBUG_MODE:
                print("⚠️ Origin airport is required.")
        if not destination_code:
            errors.append("Destination airport is required.")
            if DEBUG_MODE:
                print("⚠️ Destination airport is required.")
        if not date_from_raw:
            errors.append("Departure date is required.")
        if trip_type != "one-way" and not date_to_raw:
            errors.append("Return date is required for round-trip.")
        if not cabin_class:
            errors.append("Cabin class is required.")

        try:
            date_from = datetime.strptime(date_from_raw, "%Y-%m-%d")
        except ValueError:
            errors.append("Invalid departure date format.")
            if DEBUG_MODE:
                print("⚠️ date_from: Invalid departure date format.")

        if trip_type != "one-way" and date_to_raw:
            try:
                date_to = datetime.strptime(date_to_raw, "%Y-%m-%d")
                if date_from and date_to and date_from > date_to:
                    errors.append("Return date must be after departure date.")
            except ValueError:
                errors.append("Invalid return date format.")

        try:
            passengers = int(passengers_raw)
            if passengers < 1:
                errors.append("Number of passengers must be at least 1.")
        except ValueError:
            errors.append("Invalid number of passengers.")
            passengers = 1

        if errors:
            return render_template("travel_form.html", errors=errors, form_data=form_data)

        if trip_type == "one-way":
            user_input = (
                f"Fly one-way from {origin_code} to {destination_code} on {date_from_raw} "
                f"for {passengers} passengers in {cabin_class} class via {origin_code} to {destination_code}"
            )
        else:
            user_input = (
                f"Fly from {origin_code} to {destination_code} from {date_from_raw} to {date_to_raw} "
                f"for {passengers} passengers in {cabin_class} class via {origin_code} to {destination_code}"
            )

        try:
            result = travel_chatbot(user_input, trip_type=trip_type, limit=limit, direct_only=direct_only)
        except Exception as e:
            error_msg = f"WARNING: Something went wrong while processing your request: {str(e)}"
            return render_template("travel_form.html", errors=[error_msg], form_data=form_data)

        offers_db.clear()
        trip_info = result.get("trip_info", {})
        flights = result.get("flights", [])

        for prepared_flight in flights:
            prepared_flight["origin"] = trip_info.get("origin", origin_code)
            prepared_flight["destination"] = trip_info.get("destination", destination_code)
            prepared_flight["depart_formatted"] = format_datetime(prepared_flight.get("depart", ""))
            prepared_flight["return_formatted"] = format_datetime(prepared_flight.get("return", ""))
            offers_db[prepared_flight["id"]] = prepared_flight

        DISPLAY_LIMIT = 3
        top_offers = flights[:DISPLAY_LIMIT]
        show_more = len(flights) > len(top_offers)

        debug_mode = request.args.get("debug") == "true"
        print("DEBUG MODE:", debug_mode)

        return render_template(
            "travel_results.html",
            top_offers=top_offers,
            flights=flights,
            message=result.get("message"),
            summary=result.get("summary"),
            affiliate_link=result.get("affiliate_link"),
            trip_info=trip_info,
            show_more=show_more,
            debug_payload=result if debug_mode else None,
            direct_only=direct_only
        )

    # ✅ Safe fallback for GET requests
    return render_template("travel_form.html", form_data=form_data, flights=flights, errors=errors)




@travel_bp.route("/offer/<offer_id>")
def view_offer(offer_id):
    offer = offers_db.get(offer_id)
    if offer is None:
        error_msg = f" Warning No offer found for ID: {offer_id}"
        return render_template("travel_form.html", errors=[error_msg])
    return render_template("travel_offer_details.html", offer=offer)


@travel_bp.route("/autocomplete-airports")
def autocomplete_airports():
    logger.info("Autocomplete route hit!")
    query = request.args.get("query", "").strip().lower()
    logger.debug(f"Query received: '{query}'")

    with open("airports.json", "r", encoding="utf-8") as f:
        airports = json.load(f)

    tokens = query.replace("(", "").replace(")", "").replace("-", "").split()

    matches = [a for a in airports if any(
        is_token_match(token, a) for token in tokens if len(token) >= 1
    )]

    logger.debug(f"Matched airports: {[a['iata'] for a in matches]}")

    results = [{
        "value": f'{a["city"]} ({a["iata"]})',
        "label": f'{a["name"]} — {a["city"]} ({a["iata"]})'
    } for a in matches]

    return jsonify(results)


def is_token_match(token, airport):
    return (
        airport["city"].lower().startswith(token) or
        airport["name"].lower().startswith(token) or
        airport["iata"].lower().startswith(token)
    )
    
    
@travel_bp.route("/book-flight", methods=["POST"])
def book_flight():
    flight = {
        "id": request.form.get("flight_id"),
        "origin": request.form.get("origin"),
        "destination": request.form.get("destination"),
        "departure_date": request.form.get("departure_date"),
        "return_date": request.form.get("return_date"),
        "price": request.form.get("price"),
        "airline": request.form.get("airline"),
        "flight_number": request.form.get("flight_number"),
        "cabin_class": request.form.get("cabin_class"),
        "stops": request.form.get("stops"),
        "duration": request.form.get("duration"),
        "vendor": request.form.get("vendor"),
    }

    logger.info(f"Booking flight: {flight}")
    return render_template("travel_confirm.html", flight=flight)

@travel_bp.route("/enter-passenger-info", methods=["POST"])
def enter_passenger_info():
    flight_data = request.form.get("flight_data")

    try:
        flight = json.loads(flight_data)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to decode flight data: {e}")
        return "Invalid flight data", 400

    # ✅ Just render the passenger form — no passenger data yet
    return render_template("passenger_form.html", flight=flight)



@travel_bp.route("/payment", methods=["POST"])
def payment():
    try:
        # Flight data
        flight_data = request.form.get("flight_data")
        flight = json.loads(flight_data) if flight_data else {}

        # Passenger info
        name = request.form.get("name")
        email = request.form.get("email")
        phone = request.form.get("phone")

        if not all([flight, name, email, phone]):
            raise ValueError("Missing flight or passenger data")

        passenger = {"name": name, "email": email, "phone": phone}

        # Store in session for later use
        session["passenger"] = passenger
        session["flight"] = flight

        return render_template("payment_form.html", flight=flight, passenger=passenger)

    except json.JSONDecodeError as e:
        logger.error(f"Failed to decode flight data: {e}")
        return "Invalid flight data", 400


    except Exception as e:
        logger.error("Error in payment route:\n" + traceback.format_exc())
        return "Something went wrong with the payment process", 500    
    
   
   
@travel_bp.route("/complete-booking", methods=["POST"])
def complete_booking():
    try:
        # Extract form data
        flight_data = request.form.get("flight_data")
        card_number = request.form.get("card_number")
        expiry = request.form.get("expiry")
        cvv = request.form.get("cvv")

        # Fallback to session if form fields are missing
        name = request.form.get("name") or session.get("passenger", {}).get("name")
        email = request.form.get("email") or session.get("passenger", {}).get("email")
        phone = request.form.get("phone") or session.get("passenger", {}).get("phone")

        # Validate required fields
        if not all([flight_data, name, email, phone, card_number, expiry, cvv]):
            raise ValueError("Missing booking or payment data")

        # Decode flight JSON
        flight = json.loads(flight_data)

        # Create passenger dict
        passenger = {"name": name, "email": email, "phone": phone}

        # Store in session for finalize step
        session["passenger"] = passenger
        session["flight"] = flight
        session["card_last4"] = card_number[-4:]
        session["expiry"] = expiry

        # Log booking and payment info
        logger.info(f"✅ Booking prepared for {name} ({email}, {phone}) → {flight}")
        logger.info(f"💳 Payment info: Card ending in {card_number[-4:]}, Exp: {expiry}")

        # ✅ Redirect to finalize route
        return redirect(url_for("travel_bp.finalize_booking"))

    except json.JSONDecodeError as e:
        logger.error(f"Failed to decode flight data: {e}")
        return "Invalid flight data", 400

    except Exception as e:
        import traceback
        logger.error("Error during complete_booking:\n" + traceback.format_exc())
        return "Something went wrong during booking completion", 500




@travel_bp.route("/", methods=["GET"])
def home_page():
    return redirect(url_for("travel.flightfinder"))


# === Primary FlightFinder Route ===


@travel_bp.route("/flightfinder", methods=["GET", "POST"])
def flightfinder():
    print("FlightFinder route triggered", flush=True)

    if request.method == "POST":
        user_input = request.form.get("user_input", "").strip()
        info = extract_travel_entities(user_input)

        origin_code = city_to_iata.get(info["origin"].lower())
        destination_code = city_to_iata.get(info["destination"].lower())

        if not origin_code or not destination_code:
            return render_template("travel_results.html", message="🌍 Unknown city. Try major cities like Paris or Tokyo.")

        if not info["date_from"] or not info["date_to"]:
            return render_template("travel_results.html", message="📅 Invalid dates. Please use YYYY-MM-DD format.")

        info["date_from_str"] = info["date_from"].strftime("%Y-%m-%d")
        info["date_to_str"] = info["date_to"].strftime("%Y-%m-%d")

        # ✅ Extract dynamic values from form
        trip_type = request.form.get("trip_type", "round-trip")
       
        adults = int(request.form.get("passengers", 1))
        children = int(request.form.get("children", 0))
        infants = int(request.form.get("infants", 0))
        cabin_class = request.form.get("cabin_class", "economy").lower()

        # ✅ Store last search in session
        session["last_search"] = {
            "origin": origin_code,
            "destination": destination_code,
            "departure": info["date_from_str"],
            "return": info["date_to_str"],  # ✅ Renamed for clarity
            "trip_type": trip_type,
            "adults": adults,
            "children": children,
            "infants": infants,
            "cabin_class": cabin_class
        }


        # ✅ Call the search function with all required arguments
        flights = search_flights(
            origin_code, destination_code,
            info["date_from_str"], info["date_to_str"],
            trip_type=trip_type,
            adults=adults, children=children, infants=infants,
            cabin_class=cabin_class
        )

        if not flights:
            fallback_message = "😕 No flights found or API error occurred. Try again later or adjust your search."
            return render_template("travel_results.html", message=fallback_message, info=info)

        return render_template("travel_results.html", flights=flights, info=info)

   # return render_template("travel_form.html", mode="chat")
    return render_template("travel_form.html", mode="chat", form_data={})
# === Travel Results & Confirmation ===

@travel_bp.route("/results", methods=["POST"])
def results():
    destination = request.form['destination']
    departure_date = request.form['departure_date']
    return_date = request.form['return_date']
    result = travel_form_handler(destination, departure_date, return_date)
    return render_template("travel_results.html", **result)


@travel_bp.route("/confirm-booking", methods=["POST"])
def confirm_booking():
    try:
        # Extract passenger info
        name = request.form.get("name")
        email = request.form.get("email")
        phone = request.form.get("phone")

        # Extract flight info
        flight_json = request.form.get("flight_data")
        flight = json.loads(flight_json) if flight_json else {}

        if not all([name, email, phone, flight]):
            raise ValueError("Missing passenger or flight data")

        passenger = {"name": name, "email": email, "phone": phone}

        # Store in session for later use
        session["passenger"] = passenger
        session["flight"] = flight

        return render_template("travel_confirm.html", flight=flight, passenger=passenger)

    except Exception as e:
        import traceback
        logger.error("Error during confirm_booking:\n" + traceback.format_exc())
        return "Something went wrong during booking confirmation", 
    
    
    
       

@travel_bp.route("/finalize-booking", methods=["POST"])
def finalize_booking():
    try:
        # Get form data
        flight_json = request.form.get("flight_data")
        passenger_json = request.form.get("passenger_data")

        # Debug: log raw form data
        print("Raw flight_data:", flight_json)
        print("Raw passenger_data:", passenger_json)

        # Parse JSON strings
        flight = json.loads(flight_json) if flight_json else {}
        passenger = json.loads(passenger_json) if passenger_json else {}

        # Debug: log parsed data
        print("Parsed flight:", flight)
        print("Parsed passenger:", passenger)

        # Validate passenger fields
        required_fields = ["name", "email", "phone"]
        for field in required_fields:
            if field not in passenger or not passenger[field]:
                raise ValueError(f"Missing passenger field: {field}")

        # Generate booking reference
        reference = generate_booking_reference()

        # Save to database
        save_booking(reference, passenger, flight_json)

        # Render confirmation page
        return render_template(
            "booking_success.html",
            reference=reference,
            passenger=passenger,
            flight=flight
        )

    except Exception as e:
        print(f"Booking error: {e}")
        return f"Internal Server Error: {e}", 
    
    
    
    
    
@travel_bp.route("/booking-history", methods=["GET"]) 
def booking_history():
    try:
        bookings = Booking.query.order_by(Booking.timestamp.desc()).all()
    except Exception as e:
        logger.error(f"Error loading booking history: {e}")
        bookings = []
    return render_template("booking_history.html", bookings=bookings)


# === Health Check ===
@travel_bp.route("/health", methods=["GET"])
def health():
    return jsonify({'status': 'ok', 'timestamp': datetime.utcnow().isoformat()})
