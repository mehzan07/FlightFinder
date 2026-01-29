/**
 * Flightfinder.js - Final Corrected Version
 * Handles Autocomplete, UI Toggles, and API Safety logic
 */

// --- 1. THE AUTOCOMPLETE ENGINE ---
function setupAirportAutocomplete(inputId, hiddenId) {
  const $input = $("#" + inputId);
  const $hidden = $("#" + hiddenId);
  const $list = $("#" + inputId + "-list");

  $input.on("input", function () {
    const query = $(this).val().trim();
    if (query.length < 2) {
      $list.empty().hide();
      return;
    }
    const url = `/search-airports?term=${query}`;

    $.getJSON(url, function (data) {
      let html = "";
      if (data && data.length > 0) {
        data.forEach((item) => {
          const name = `${item.name}, ${item.country_name} (${item.code})`;
          html += `<div class="suggestion-item" data-code="${item.code}" data-full-name="${name}">${name}</div>`;
        });
        $list.html(html).show();
      } else {
        $list.empty().hide();
      }
    });
  });

  // Handle selecting an item from the list
  $(document).on(
    "click",
    "#" + inputId + "-list .suggestion-item",
    function (e) {
      const code = $(this).data("code");
      const fullName = $(this).data("full-name");

      $input.val(fullName); // What the user sees
      $hidden.val(code); // What the Python backend needs (3-letter code)
      $list.empty().hide();
    },
  );
}

// Reset UI state when navigating back to the page
window.onpageshow = function (event) {
  if (
    event.persisted ||
    (window.performance && window.performance.navigation.type === 2)
  ) {
    $("#loading").hide();
    $('button[type="submit"]').prop("disabled", false).text("Search Flights");
  }
};

// --- 2. INITIALIZATION & UI HANDLERS ---
$(document).ready(function () {
  // Reset UI State on Load
  $("#loading").hide();
  $('button[type="submit"]').prop("disabled", false).text("Search Flights");

  // Initialize Autocomplete for all fields
  setupAirportAutocomplete("origin_text", "origin_code");
  setupAirportAutocomplete("destination_text", "destination_code");
  setupAirportAutocomplete("destination_text_2", "destination_code_2");

  // Close suggestions when clicking outside
  $(document).on("click", function (event) {
    if (!$(event.target).closest(".position-relative").length) {
      $(".autocomplete-suggestions").hide();
    }
  });

  // Trip Type Toggle Logic (Show/Hide Return Date or Leg 2)
  $("#trip_type").on("change", function () {
    const selectedType = $(this).val();
    if (selectedType === "multi-city") {
      $("#multiCityGroup").slideDown();
      $("#returnDateGroup").slideUp();
    } else if (selectedType === "one-way") {
      $("#multiCityGroup").slideUp();
      $("#returnDateGroup").slideUp();
    } else {
      // Round-trip
      $("#multiCityGroup").slideUp();
      $("#returnDateGroup").slideDown();
    }
  });

  // Clear Form Logic
  $("#clearFormBtn").on("click", function () {
    $("#searchForm")[0].reset();
    $('input[type="hidden"]').val("");
    $(".autocomplete-suggestions").hide();
  });

  // Close Leg 2 Button (Resets to Round-trip)
  $("#removeLeg2").on("click", function () {
    $("#trip_type").val("round-trip").trigger("change");
  });

  // --- 3. THE CONSOLIDATED SUBMIT HANDLER (THE FIX) ---
  $("#searchForm").on("submit", function (e) {
    // A. CODE SAFETY: Extract (ARN) codes if hidden field is empty
    ["origin", "destination", "destination_2"].forEach(function (prefix) {
      const textVal = $("#" + prefix + "_text").val();
      const $hidden = $("#" + prefix + "_code");
      if (textVal && !$hidden.val() && textVal.includes("(")) {
        const extracted = textVal.match(/\(([^)]+)\)/);
        if (extracted) $hidden.val(extracted[1]);
      }
    });

    // B. AMADEUS 400 FIX: Disable '0' values for children/infants
    // This prevents them from being sent to Python/Amadeus and causing a 400 error.
    const childrenInput = $("#children");
    const infantsInput = $("#infants");

    if (childrenInput.val() === "0" || !childrenInput.val()) {
      childrenInput.attr("disabled", true);
    }
    if (infantsInput.val() === "0" || !infantsInput.val()) {
      infantsInput.attr("disabled", true);
    }

    // C. TRIP TYPE CLEANUP: Don't send return date if it's not a round-trip
    if ($("#trip_type").val() !== "round-trip") {
      $("#date_to").attr("disabled", true);
    }

    // D. SHOW LOADING STATE
    $("#loading").show();
    $(this)
      .find('button[type="submit"]')
      .prop("disabled", true)
      .text("Searching...");

    return true; // Allow the form to submit to the Python backend
  });
});
