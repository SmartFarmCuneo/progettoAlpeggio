document.addEventListener("DOMContentLoaded", function () {
  const selectProvincia = document.getElementById("select_provincia");
  const selectComune = document.getElementById("select_comune");
  const zipInput = document.getElementById("zip");
  const campoLat = document.getElementById("campo_lat");
  const campoLon = document.getElementById("campo_lon");

  let sessionProvincia = "";
  let sessionComune = "";
  let sessionCap = "";

  // Recupera coordinate dalla sessione
  fetch("/api/get_session_coordinate")
    .then((res) => res.json())
    .then((coord) => {
      if (coord && coord.lat && coord.lon) {
        campoLat.value = coord.lat;
        campoLon.value = coord.lon;

        fetch(
          `/api/get_location_by_coords?lat=${coord.lat}&lon=${coord.lon}`
        )
          .then((res) => res.json())
          .then((data) => {
            sessionProvincia = data.sigla_provincia || "";
            sessionComune = data.comune || "";
            sessionCap = data.cap || "";
            populateProvince();
          })
          .catch((err) => {
            console.error("Errore fetch location:", err);
            populateProvince();
          });
      } else {
        populateProvince();
      }
    })
    .catch((err) => {
      console.error("Errore fetch session coordinate:", err);
      populateProvince();
    });

  // Popola province
  function populateProvince() {
    fetch("/api/get_provincia")
      .then((res) => res.json())
      .then((data) => {
        selectProvincia.innerHTML = '<option value="">Scegli...</option>';
        if (data.province) {
          data.province.forEach((p) => {
            const option = document.createElement("option");
            option.value = p.sigla_provincia;
            option.textContent = p.denominazione_provincia;
            if (p.sigla_provincia === sessionProvincia)
              option.selected = true;
            selectProvincia.appendChild(option);
          });
        }
        if (sessionProvincia) populateComuni(sessionProvincia);
      })
      .catch((err) => console.error("Errore fetch province:", err));
  }

  // Popola comuni
  function populateComuni(prov) {
    selectComune.innerHTML = '<option value="">Scegli...</option>';
    if (!prov) return;
    fetch(`/api/get_comune?provincia=${prov}`)
      .then((res) => res.json())
      .then((data) => {
        if (data.comuni) {
          data.comuni.forEach((c) => {
            const option = document.createElement("option");
            option.value = c.denominazione_ita;
            option.textContent = c.denominazione_ita;
            if (c.denominazione_ita === sessionComune)
              option.selected = true;
            selectComune.appendChild(option);
          });
        }
        zipInput.value = sessionCap || "";
      })
      .catch((err) => console.error("Errore fetch comuni:", err));
  }

  // Quando cambia provincia
  selectProvincia.addEventListener("change", () => {
    sessionComune = "";
    sessionCap = "";
    populateComuni(selectProvincia.value);
  });
});