# db.py

from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from dotenv import load_dotenv
import os
from sqlalchemy.exc import SQLAlchemyError

from database import db
from models import Booking
import json


# === Load environment variables ===
load_dotenv()

# === Ensure DATABASE_URL is set ===
if not os.getenv("DATABASE_URL"):
    raise ValueError("DATABASE_URL environment variable is not set.")

# --------------------------
# Booking Helper Functions
# --------------------------

def get_booking_history():
    return Booking.query.order_by(Booking.timestamp.desc()).all()

def save_booking(reference, passenger, flight_json):

    try:
        # Check for existing booking
        existing = Booking.query.filter_by(
            passenger_name=passenger.get("name"),
            passenger_email=passenger.get("email"),
            passenger_phone=passenger.get("phone"),
            flight_data=flight_json
        ).first()

        if existing:
            print("Booking already exists. Skipping insert.", flush=True)
            return

        # Create new booking
        new_booking = Booking(
            reference=reference,
            passenger_name=passenger.get("name"),
            passenger_email=passenger.get("email"),
            passenger_phone=passenger.get("phone"),
            flight_data=flight_json,
            timestamp=datetime.utcnow()
        )
        db.session.add(new_booking)
        db.session.commit()

    except Exception as e:
        db.session.rollback()
        print(f"Error saving booking: {e}")
        raise e
    finally:
        db.session.close()
        
        

def get_booking_history():
    from models import Booking
    try:
        return Booking.query.order_by(Booking.timestamp.desc()).all()
    except SQLAlchemyError as e:
        print(f"Error fetching booking history: {e}")
        return []