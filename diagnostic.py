"""
Diagnostic script to find why Amadeus isn't working
Run this: python diagnostic.py
"""

print("=" * 60)
print("AMADEUS DIAGNOSTIC TOOL")
print("=" * 60)

# Step 1: Check .env file
print("\n1. Checking .env file...")
try:
    with open('.env', 'r') as f:
        env_contents = f.read()
        
    if 'AMADEUS_API_KEY' in env_contents:
        print("   ✅ AMADEUS_API_KEY found in .env")
    else:
        print("   ❌ AMADEUS_API_KEY NOT found in .env")
        
    if 'USE_AMADEUS' in env_contents:
        print("   ✅ USE_AMADEUS found in .env")
        # Check value
        for line in env_contents.split('\n'):
            if line.startswith('USE_AMADEUS'):
                print(f"   📝 Value: {line}")
    else:
        print("   ❌ USE_AMADEUS NOT found in .env")
except FileNotFoundError:
    print("   ❌ .env file not found!")

# Step 2: Check config.py
print("\n2. Checking config.py...")
try:
    from config import USE_AMADEUS, AMADEUS_API_KEY, AMADEUS_API_SECRET
    print(f"   USE_AMADEUS = {USE_AMADEUS} (type: {type(USE_AMADEUS).__name__})")
    print(f"   AMADEUS_API_KEY = {AMADEUS_API_KEY[:20]}... (exists: {bool(AMADEUS_API_KEY)})")
    print(f"   AMADEUS_API_SECRET = {AMADEUS_API_SECRET[:20]}... (exists: {bool(AMADEUS_API_SECRET)})")
except ImportError as e:
    print(f"   ❌ Config import failed: {e}")

# Step 3: Check flight_search.py
print("\n3. Checking flight_search.py...")
try:
    import flight_search
    print(f"   AMADEUS_AVAILABLE = {flight_search.AMADEUS_AVAILABLE}")
    
    if hasattr(flight_search, 'search_flights_amadeus'):
        print("   ✅ search_flights_amadeus function exists")
    else:
        print("   ❌ search_flights_amadeus function NOT found")
        
except ImportError as e:
    print(f"   ❌ flight_search import failed: {e}")

# Step 4: Test Amadeus directly
print("\n4. Testing Amadeus API directly...")
try:
    from amadeus_search import search_flights_amadeus
    
    print("   Testing search: ARN → LHR, 2025-12-15 to 2025-12-22")
    flights = search_flights_amadeus(
        origin="ARN",
        destination="LHR",
        date_from="2025-12-15",
        date_to="2025-12-22",
        trip_type="round-trip",
        limit=2,
        direct_only=True
    )
    
    print(f"   ✅ Got {len(flights)} flights")
    if flights:
        print(f"   First flight vendor: {flights[0].get('vendor')}")
        print(f"   First flight link: {flights[0].get('link')[:80]}...")
    
except Exception as e:
    print(f"   ❌ Amadeus test failed: {e}")
    import traceback
    traceback.print_exc()

# Step 5: Check the main search function
print("\n5. Testing main search_flights function...")
try:
    from flight_search import search_flights
    
    flights = search_flights(
        origin_code="ARN",
        destination_code="LHR",
        date_from_str="2025-12-15",
        date_to_str="2025-12-22",
        trip_type="round-trip",
        limit=2,
        direct_only=True
    )
    
    print(f"   ✅ Got {len(flights)} flights")
    if flights:
        print(f"   Vendor: {flights[0].get('vendor')}")
        print(f"   Link: {flights[0].get('link')[:80]}...")
    
except Exception as e:
    print(f"   ❌ Search function failed: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("DIAGNOSIS COMPLETE")
print("=" * 60)
print("\nIf you see errors above, share the output with me!")