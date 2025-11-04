// Deep link builder function
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

document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("searchForm");

  if (form) {
    form.addEventListener("submit", (e) => {
      e.preventDefault();

      const origin = document.getElementById("origin").value.trim();
      const destination = document.getElementById("destination").value.trim();
      const dateFrom = document.getElementById("date_from").value;
      const dateTo = document.getElementById("date_to").value;

      const deepLink = buildAviasalesSearchLink(
        origin,
        destination,
        dateFrom,
        dateTo,
      );

      console.log("Generated deep link:", deepLink);

      // TEMP: Open the link in a new tab to verify
      window.open(deepLink, "_blank");

      // LATER: Replace with API call or render results in your UI
    });
  }
});

$(document).ready(function () {
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

  // 📅 Date logic
  const dateFrom = document.getElementById("date_from");
  const dateTo = document.getElementById("date_to");
  const returnDateGroup = document.getElementById("returnDateGroup");

  if (dateFrom && dateTo) {
    const today = new Date().toISOString().split("T")[0];
    dateFrom.min = today;
    dateFrom.addEventListener("change", () => {
      dateTo.min = dateFrom.value;
    });
  }

  // 🔁 Trip type toggle logic (dropdown-based)
  const tripTypeSelect = document.getElementById("trip_type");
  const toggleReturnFields = () => {
    const selected = tripTypeSelect.value;
    if (selected === "one-way") {
      returnDateGroup.style.display = "none";
      dateTo.required = false;
      dateTo.value = ""; // ✅ Clear value to avoid backend validation
    } else {
      returnDateGroup.style.display = "block";
      dateTo.required = true;
      if (!dateTo.value) {
        dateTo.value = "2025-12-17"; // ✅ Restore original default
      }
    }
  };

  tripTypeSelect.addEventListener("change", toggleReturnFields);
  toggleReturnFields(); // ✅ Run on page load

  // ⏳ Loading spinner on submit
  const form = document.querySelector("form");
  const loading = document.getElementById("loading");
  if (form) {
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      if (loading) {
        loading.style.display = "block";
        setTimeout(() => {
          form.submit();
        }, 500);
      } else {
        form.submit(); // ✅ fallback
      }
    });
  }
});
