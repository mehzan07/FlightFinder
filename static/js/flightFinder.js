/**
 * Helper to build a direct search link (mainly for console logging)
 */
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

  // --- 1. UI ELEMENT SELECTORS ---
  const $tripType = $("#trip_type");
  const $returnDateGroup = $("#returnDateGroup");
  const $returnDateInput = $("#date_to");
  const $multiCityGroup = $("#multiCityGroup");
  const $dest2Input = $("#destination_code_2");
  const $date2Input = $("#date_from_2");
  const $dateFrom = $("#date_from");

  // --- 2. TRIP TYPE TOGGLE LOGIC ---
  function toggleTripFields() {
    const selected = $tripType.val();

    // Reset visibility and requirements
    $returnDateGroup.hide();
    $multiCityGroup.hide();
    $returnDateInput.prop("required", false);
    $dest2Input.prop("required", false);
    $date2Input.prop("required", false);

    if (selected === "round-trip") {
      $returnDateGroup.show();
      $returnDateInput.prop("required", true);
    } else if (selected === "multi-city") {
      $multiCityGroup.show();
      $dest2Input.prop("required", true);
      $date2Input.prop("required", true);

      // Set defaults if empty
      if ($dest2Input.val() === "") $dest2Input.val("Paris (CDG)");
      if ($date2Input.val() === "") $date2Input.val("2026-03-15");
    }
  }

  // Initialize and Listen for changes
  toggleTripFields();
  $tripType.on("change", toggleTripFields);

  // --- 3. CLEAR FORM LOGIC ---
  $("#clearFormBtn").on("click", function () {
    // Manually empty the text inputs
    $("#origin_code, #destination_code, #destination_code_2").val("");

    // Manually empty the date inputs
    $("#date_from, #date_to, #date_from_2").val("");

    // Reset passengers to 1
    $("#passengers").val(1);

    // Force the dropdown back to 'one-way'
    $tripType.val("one-way").trigger("change");

    console.log("Form completely emptied and reset to One-way.");
  });

  // Close button for Multi-city Leg 2
  $("#removeLeg2").on("click", function () {
    $tripType.val("one-way").trigger("change");
  });

  // --- 4. AIRPORT AUTOCOMPLETE SETUP ---
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

  // --- 5. DATE RESTRICTION LOGIC ---
  if ($dateFrom.length) {
    const today = new Date().toISOString().split("T")[0];
    $dateFrom.attr("min", today);

    $dateFrom.on("change", function () {
      const selectedDate = $(this).val();
      // Update Return Date min
      if ($returnDateInput.length) $returnDateInput.attr("min", selectedDate);
      // Update Leg 2 Date min
      if ($date2Input.length) {
        $date2Input.attr("min", selectedDate);
        if ($date2Input.val() < selectedDate) $date2Input.val(selectedDate);
      }
    });
  }

  // --- 6. FORM SUBMISSION HANDLER ---
  const form = document.getElementById("searchForm");
  const loading = document.getElementById("loading");

  const extractIATA = (value) => {
    const matchParentheses = value.match(/\((\w{3})\)$/);
    if (matchParentheses) return matchParentheses[1];

    const trimmedValue = value.trim().toUpperCase();
    if (trimmedValue.length === 3 && /^[A-Z]{3}$/.test(trimmedValue))
      return trimmedValue;

    return trimmedValue;
  };

  if (form) {
    form.addEventListener("submit", (e) => {
      // We don't preventDefault here because we want the form to submit to Flask,
      // but we use it to show the loading spinner.
      if (loading) {
        loading.style.display = "block";
      }

      // Log details for debugging
      const origin = extractIATA(document.getElementById("origin_code").value);
      const destination = extractIATA(
        document.getElementById("destination_code").value,
      );
      console.log("Submitting search for:", origin, "to", destination);
    });
  }
});

/**
 * Renders local results (if available)
 */
function renderFlightResults(data) {
  const container = document.getElementById("results");
  if (!container) return;

  container.innerHTML = "<p>✅ Rendering started</p>";

  if (!data || !data.data || data.data.length === 0) {
    container.innerHTML += "<p>😕 No flights found.</p>";
    return;
  }

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
