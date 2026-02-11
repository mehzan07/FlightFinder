/**
 * Flightfinder.js - Updated Version
 * Handles Autocomplete, UI Toggles, Reset, Loading States, and Back-Button Fix
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
    const url = `/search-airports?term=${encodeURIComponent(query)}`;

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

  // Handle selecting an item
  $(document).on(
    "click",
    "#" + inputId + "-list .suggestion-item",
    function () {
      const code = $(this).data("code");
      const fullName = $(this).data("full-name");

      $input.val(fullName);
      $hidden.val(code);
      $list.empty().hide();
    },
  );
}

$(document).ready(function () {
  // 1. Initial UI State
  $("#loading").hide();
  const $searchBtn = $('#searchForm button[type="submit"]');
  $searchBtn.prop("disabled", false).text("Search Flights");

  // Initialize Autocomplete
  setupAirportAutocomplete("origin_text", "origin_code");
  setupAirportAutocomplete("destination_text", "destination_code");
  setupAirportAutocomplete("destination_text_2", "destination_code_2");

  // Close suggestions when clicking outside
  $(document).on("click", function (event) {
    if (!$(event.target).closest(".position-relative").length) {
      $(".autocomplete-suggestions").hide();
    }
  });

  // 2. Trip Type Toggle
  $("#trip_type").on("change", function () {
    const selectedType = $(this).val();
    $("#searchForm input").prop("disabled", false);

    if (selectedType === "multi-city") {
      $("#multiCityGroup").show();
      $("#returnDateGroup").hide();
      $("#date_to").prop("disabled", true);
    } else if (selectedType === "one-way") {
      $("#multiCityGroup").hide();
      $("#returnDateGroup").hide();
      $("#date_to").prop("disabled", true);
    } else {
      $("#multiCityGroup").hide();
      $("#returnDateGroup").show();
    }
  });

  // 3. Clear All Button Logic
  $("#clearFormBtn").on("click", function (e) {
    e.preventDefault();
    $("#searchForm")[0].reset();
    $("#searchForm input").val("");
    $("#searchForm select").prop("selectedIndex", 0);
    $('input[type="hidden"]').val("");
    $("[id$='-list']").empty().hide();
    $(".autocomplete-suggestions").empty().hide();

    // Reset Search Button & Hide Loading
    $searchBtn.prop("disabled", false).text("Search Flights");
    $("#loading").hide();
  });

  // 4. Submit Handler (Shows the Spinner)
  $("#searchForm").on("submit", function () {
    // Multi-city safety check
    if (
      $("#trip_type").val() === "multi-city" &&
      !$("#destination_code_2").val()
    ) {
      alert("Please select a second destination for Multi-City");
      return false;
    }

    // Auto-fill hidden codes if user typed them manually
    ["origin", "destination", "destination_2"].forEach(function (prefix) {
      const textVal = $("#" + prefix + "_text").val();
      const $hidden = $("#" + prefix + "_code");
      if (textVal && !$hidden.val() && textVal.includes("(")) {
        const code = textVal.match(/\(([^)]+)\)/);
        if (code) $hidden.val(code[1]);
      }
    });

    // UI FEEDBACK: Show spinner and change button
    $("#loading").show();
    $searchBtn
      .prop("disabled", true)
      .html(
        '<span class="spinner-border spinner-border-sm"></span> Searching...',
      );

    return true;
  });

  // 5. Force hide navigation fallback
  $(
    "nav a:contains('History'), nav a:contains('Account'), nav a:contains('Booking')",
  ).each(function () {
    $(this).closest("li, .nav-item").hide();
    $(this).hide();
  });
});

// 6. iPhone/Safari "Back Button" Fix
// This resets the UI immediately when navigating back to the page
window.onpageshow = function (event) {
  $("#loading").hide();
  const $searchBtn = $('#searchForm button[type="submit"]');
  $searchBtn.prop("disabled", false).text("Search Flights");
};
