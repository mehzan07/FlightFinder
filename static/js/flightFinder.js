function buildAviasalesSearchLink(
  origin,
  destination,
  dateFrom,
  dateTo = null,
) {
  const [yearFrom, monthFrom, dayFrom] = dateFrom.split("-");
  let searchPath = `${origin}${dayFrom}${monthFrom}${destination}`;

  if (dateTo) {
    const [yearTo, monthTo, dayTo] = dateTo.split("-");
    searchPath += `${dayTo}${monthTo}`;
  }

  return `https://www.aviasales.com/search/${searchPath}`;
}
$(document).ready(function () {
  console.log("flightFinder.js loaded");

  // ✈️ Autocomplete setup
  function setupAirportAutocomplete(inputId) {
    $("#" + inputId).on("input", function () {
      const query = $(this).val().trim().toLowerCase();
      if (query.length < 1) {
        $("#" + inputId + "-list").html("");
        return;
      }
      $.getJSON("/autocomplete-airports", { query: query })
        .done(function (data) {
          let options = "";
          data.forEach((item) => {
            options += `<option value="${item.value}">${item.label}</option>`;
          });
          $("#" + inputId + "-list").html(options);
        })
        .fail(function (xhr, status, error) {
          console.error("Autocomplete failed:", status, error);
        });
    });
  }

  setupAirportAutocomplete("origin_code");
  setupAirportAutocomplete("destination_code");
  setupAirportAutocomplete("destination_code_2");

  // 📅 Date logic
  const dateFrom = document.getElementById("date_from");
  const dateTo = document.getElementById("date_to");
  const dateFrom2 = document.getElementById("date_from_2");

  if (dateFrom) {
    const today = new Date().toISOString().split("T")[0];
    dateFrom.min = today;

    dateFrom.addEventListener("change", () => {
      // 1. Update Return Date min (for Round-trip)
      if (dateTo) {
          dateTo.min = dateFrom.value;
      }
      // 2. Update Leg 2 Date min (for Multi-city)
      if (dateFrom2) {
          dateFrom2.min = dateFrom.value;
          // If Leg 2 is now before Leg 1, reset it to match Leg 1
          if (dateFrom2.value < dateFrom.value) {
              dateFrom2.value = dateFrom.value;
          }
      }
    });
  }


  // ✅ Unified form submit handler
  const form = document.getElementById("searchForm");
  const loading = document.getElementById("loading");

  const extractIATA = (value) => {
    // 1. Try to find the 3-letter code inside parentheses (e.g., "City (XXX)")
    const matchParentheses = value.match(/\((\w{3})\)$/);
    if (matchParentheses) {
      return matchParentheses[1];
    }

    // 2. Check if the raw value is a 3-letter code (e.g., "JFK")
    const trimmedValue = value.trim().toUpperCase();
    if (trimmedValue.length === 3 && /^[A-Z]{3}$/.test(trimmedValue)) {
      return trimmedValue;
    }

    // 3. Fallback (should ideally be a 3-letter code)
    return trimmedValue;
  };

  if (form) {
    form.addEventListener("submit", (e) => {
      e.preventDefault();

      const origin = extractIATA(document.getElementById("origin_code").value);
      const destination = extractIATA(
        document.getElementById("destination_code").value,
      );

      const dateFrom = document.getElementById("date_from").value;
      const dateTo = document.getElementById("date_to").value;

      const deepLink = buildAviasalesSearchLink(
        origin,
        destination,
        dateFrom,
        dateTo,
      );
      console.log("Form submitted");
      console.log("Generated deep link:", deepLink);

      if (loading) {
        loading.style.display = "block";
      }

      // We allow the form to submit to the Python backend to perform the search
      form.submit(); // <-- Use this to submit the data to Flask endpoint /search-flights
    });
  }
});

// ... (renderFlightResults function remains the same) ...

function renderFlightResults(data) {
  const container = document.getElementById("results");
  container.innerHTML = "<p>✅ Rendering started</p>";

  if (!data || !data.data || data.data.length === 0) {
    container.innerHTML += "<p>😕 No flights found.</p>";
    return;
  }

  console.table(data.data); // ✅ Easier to inspect in DevTools

  data.data.forEach((flight) => {
    const card = document.createElement("div");
    card.className = "flight-card p-3 mb-3 border rounded";

    card.innerHTML = `
      <h5>Destination: ${flight.destination || "Unknown"}</h5>
      <p>🛫 Depart: ${flight.depart_date || "N/A"}</p>
      <p>⏱ Duration: ${flight.duration || "?"} mins</p>
      <p>📏 Distance: ${flight.distance || "?"} km</p>
      <p>✅ Actual: ${flight.actual ? "Yes" : "No"}</p>
    `;

    container.appendChild(card);
  });
}
