/**
 * Flightfinder.js - Main logic for Airport Autocomplete and Form UI
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

    const url = `https://autocomplete.travelpayouts.com/places2?term=${query}&locale=en&types[]=city&types[]=airport`;

    $.getJSON(url, function (data) {
      let html = "";
      if (data && data.length > 0) {
        data.forEach((item) => {
          // Display: "Stockholm, Sweden (ARN)"
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

      $input.val(fullName); // What user sees
      $hidden.val(code); // What Python sees
      $list.empty().hide();
    },
  );
}

// This triggers every time the page is shown, including via the "Back" button
window.onpageshow = function(event) {
    if (event.persisted || (window.performance && window.performance.navigation.type === 2)) {
        // Force the loading spinner to hide and button to re-enable
        $('#loading').hide();
        $('button[type="submit"]').prop('disabled', false).text('Search Flights');
    }
};


// --- 2. INITIALIZATION & UI HANDLERS ---
$(document).ready(function () {
  // 1. FORCE RESET: Hide loading and enable button every time the page loads
    $('#loading').hide();
    $('button[type="submit"]').prop('disabled', false).text('Search Flights');
  // Initialize Autocomplete for all 3 fields
  setupAirportAutocomplete("origin_text", "origin_code");
  setupAirportAutocomplete("destination_text", "destination_code");
  setupAirportAutocomplete("destination_text_2", "destination_code_2");

  // Close any open autocomplete lists if user clicks anywhere else
  $(document).on("click", function (event) {
    if (!$(event.target).closest(".position-relative").length) {
      $(".autocomplete-suggestions").hide();
    }
  });

  // --- TRIP TYPE LOGIC ---
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

  // --- FORM BUTTONS ---

  // Clear Form Logic
  $("#clearFormBtn").on("click", function () {
    $("#searchForm")[0].reset();
    $('input[type="hidden"]').val(""); // Clear hidden codes too
    $(".autocomplete-suggestions").hide();
  });

  // Leg 2 Close Button
  $("#removeLeg2").on("click", function () {
    $("#trip_type").val("round-trip").trigger("change");
  });

  // --- SEARCH LOADING STATE ---
  $("#searchForm").on("submit", function () {
    // Show the spinner, hide the button to prevent double clicks
    $("#loading").show();
    $(this)
      .find('button[type="submit"]')
      .attr("disabled", "disabled")
      .text("Searching...");
  });
});
