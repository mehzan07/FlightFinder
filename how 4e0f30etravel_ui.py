[33mf7b3a18[m[33m ([m[1;36mHEAD -> [m[1;32mfeature[m[33m)[m some error correction and documentations
[33m456c90d[m[33m ([m[1;31morigin/feature[m[33m)[m logic of app
[33mb2284fd[m[33m ([m[1;33mtag: v3.0[m[33m, [m[1;31morigin/main[m[33m, [m[1;31morigin/HEAD[m[33m, [m[1;32mmain[m[33m)[m Addng Clear All button to reset the ui, and moving all script from travel_from.html to FlightFinder.js
[33m37f5dbd[m implementing autocomplete and default destination and second date
[33m4e0f30e[m Muti city is implemented
[33ma9e47a9[m fix of  one-way flights in the aviasales
[33mfe15260[m fix of direct flights
[33m0e398d6[m change of default dest date and return date
[33m27b3f87[m implementing both amadeus, and travelpayouts and merging results fallback to travelpayouts
[33m6292866[m modifications
[33m91ec211[m some improvements
[33m71de032[m Integrate Amadeus GDS for primary search & optimize affiliate model, Successfully integrate Amadeus for fast, accurate flight data, , establishing it as the primary data source. Implements a robust fallback to Travelpayouts for reliability
[33m01839fa[m from Search results user can reach to  the Aviasales list and then redirct to  the sales sites
[33mdc57f4f[m until here pilot code help
[33m2a1d42f[m implemented until showing aviasales link and a list of flights to choose
[33md5fdf64[m[33m ([m[1;33mtag: v2.0[m[33m)[m until: shows Aviasales results with a list of possible flights
[33m4fb0119[m with search flights you can see the direct link: https://www.aviasales.com/search/ARN1012LHR17121 and origin, destination, and departure date and destinatination date ,etc and a list of flihts that use can select
[33mba77d20[m seperating js and html creating new js file flightFinder.js
[33m8acdeca[m fix of travel type and return date problem
[33m44dbc10[m some error corrections
[33mc0a26ba[m untill here we are coming to the generic link https://www.aviasales.com/?params=KYA1
[33m018b555[m fixed fot to hide destinaton date when user select one-way then return date is hidden
[33m8815be3[m error fix
[33m44b0497[m modification to redirect to real fliht
[33m7f04e2b[m[33m ([m[1;33mtag: v1.0-demo[m[33m)[m Adding documentation
[33m159a9c6[m call only one time save_booking not more
[33mdcef01b[m implementing View Booking History as a link in the Top Right of browser.
[33mc9ccb43[m fix of some unneccesary buttons and process
[33m4b28fdc[m Back to confirmation is working
[33m9e3d46f[m now we have got booking confrimation with flight info
[33mc06d41b[m moving all routes from app.py to travel_ui.py and working until booking confirmed
[33mf56d4dd[m correction un till booking confirmed
[33m18fac3e[m developed until booking confirmed
[33m9403369[m develpped untill booking confirmation
[33mce3f079[m fix of autocomplete
[33m5acae8e[m Adding loggning, more airport in airports.josn, some fix of @travel_bp.route("/autocomplete-airports") route
[33m7745723[m Implementing direct flights and adding get_logger(name), setup_logging(): to use of import: from config import get_logger logger = get_logger(__name__) and then use logger.info(..)
[33m8951c88[m  one-way trip is implemented
[33m50a1ac7[m All three UIs are optimezed and working fine for trip_type : return but not one-way
[33m85f072b[m UI filed is fixed , only we have depart and return not extra fields like city and ...
[33mf993bce[m Now we can show a limited number of flights sorted by price and it is configurable to set limit on the UI, before pressing to the search flight button.
[33md02b099[m setting default origin and destionan to stockholm to London for easy testing
[33mc542603[m changing Return date to Arrival date
[33mdd4da5c[m just styling
[33m0ccadff[m Now FlightFinder gets all flight information
[33mb187953[m gets correct results from API, but too long flight info and no depart and no arrival date time
[33mc419087[m integrating with flight search api, but not completed yet
[33m853e2df[m update of project_structure
[33macaba65[m Initial commit: FlightFinder cleaned and ready
