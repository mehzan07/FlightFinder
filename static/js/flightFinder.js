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

  // 🔁 Trip type toggle logic
  const tripTypeSelect = document.getElementById("trip_type");
  const toggleReturnFields = () => {
    const selected = tripTypeSelect.value;
    if (selected === "one-way") {
      returnDateGroup.style.display = "none";
      dateTo.required = false;
      dateTo.value = "";
    } else {
      returnDateGroup.style.display = "block";
      dateTo.required = true;
      if (!dateTo.value) {
        dateTo.value = "2025-12-17";
      }
    }
  };

  tripTypeSelect.addEventListener("change", toggleReturnFields);
  toggleReturnFields();

  // ✅ Unified form submit handler
  const form = document.getElementById("searchForm");
  const loading = document.getElementById("loading");

  if (form) {
    form.addEventListener("submit", (e) => {
      e.preventDefault();

      const extractIATA = (value) => {
        const match = value.match(/\((\w{3})\)$/);
        return match ? match[1] : value.trim();
      };

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

      // ✅ Replace this with fetch/render logic later
      // window.open(deepLink, "_blank");

//       fetch("/search-flights", {
//         method: "POST",
//         headers: { "Content-Type": "application/json" },
//         body: JSON.stringify({
//           origin,
//           destination,
//           dateFrom,
//           dateTo,
//         }),
//       })
//         .then((res) => res.json())
//         .then((data) => {
//           console.log("Flight results:", JSON.stringify(data, null, 2));
//           renderFlightResults(data);
//         })
//         .catch((err) => {
//           console.error("Flight search failed:", err);
//           document.getElementById("results").innerHTML =
//             "<p>😕 Flight search failed. Try again later.</p>";
//         });
//     });
//   }
// });

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
