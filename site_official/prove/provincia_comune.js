let provinceSelect = document.getElementById("province");
let comuniSelect = document.getElementById("comuni");
let capDisplay = document.getElementById("cap");
let comuniData = [];

// Carica le province
fetch("./json/gi_province.json")
    .then(response => response.json())
    .then(provinceData => {
        provinceData.forEach(provincia => {
            let option = document.createElement("option");
            option.value = provincia.sigla_provincia;
            option.textContent = provincia.denominazione_provincia;
            provinceSelect.appendChild(option);
        });
    });

// Carica i comuni
fetch("./json/gi_comuni_cap.json")
    .then(response => response.json())
    .then(data => comuniData = data);

// Aggiorna la lista dei comuni quando cambia la provincia
provinceSelect.addEventListener("change", function () {
    comuniSelect.innerHTML = '<option value="">-- Scegli un Comune --</option>';
    capDisplay.textContent = "CAP: --";
    let selectedProvince = this.value;
    let filteredComuni = comuniData.filter(comune => comune.sigla_provincia === selectedProvince);

    // riempie la select dei comuni con quelli della provincia selezionata
    filteredComuni.forEach(comune => {
        let option = document.createElement("option");
        option.value = comune.denominazione_ita;
        option.textContent = comune.denominazione_ita;
        option.dataset.cap = comune.cap;
        comuniSelect.appendChild(option);
    });
});

// Mostra il CAP quando viene selezionato un comune
comuniSelect.addEventListener("change", function () {
    let selectedOption = comuniSelect.options[comuniSelect.selectedIndex];
    capDisplay.textContent = "CAP: " + (selectedOption.dataset.cap || "--");
});
