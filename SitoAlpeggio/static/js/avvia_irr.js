document.addEventListener("DOMContentLoaded", function () {
    // Ottieni campo_id dall'URL corrente
    const urlParams = new URLSearchParams(window.location.search);
    const campoIdSelezionato = urlParams.get('campo_id');

    const containerCampi = document.getElementById("campi");
    let campoSelezionato = null;

    function caricaCampi() {
        fetch("/api/campi-utente")
            .then((res) => res.json())
            .then((campi) => {
                if (campi.length > 0) {
                    containerCampi.innerHTML = `
            <div class="campi-lista">
              <h3>I Tuoi Campi</h3>
              <div id="lista-pulsanti"></div>
            </div>
            <div class="campo-dettagli">
              <div class="campo-nome">Seleziona un campo</div>
              <div class="mini-mappa-container">
                <div id="mini-map" style="height:100%;"></div>
              </div>
            </div>
          `;

                    const listaPulsanti = document.getElementById("lista-pulsanti");
                    const dettagliArea = document.querySelector(".campo-dettagli");

                    campi.forEach((campo, i) => {
                        const button = document.createElement("button");
                        button.className = "campo-button";
                        const nomeCampo = campo.nome || `Campo ${i + 1}`;
                        const comune = campo.comune ? campo.comune : "";
                        button.textContent = `${nomeCampo} - ${comune}`;
                        button.dataset.campo = nomeCampo;
                        button.dataset.campoId = campo.id_t;
                        button.dataset.coordinate = campo.coordinate || null;

                        button.addEventListener("click", () =>
                            selezionaCampo(button, dettagliArea)
                        );
                        listaPulsanti.appendChild(button);
                    });

                    // Dopo aver caricato tutti i campi, seleziona automaticamente quello dall'URL
                    selezionaCampoAutomatico(dettagliArea);
                } else {
                    containerCampi.innerHTML = `
            <div class="nessun-campo">
              Nessun campo disponibile. Aggiungi un nuovo campo per iniziare.
            </div>
          `;
                }
            });
    }

    function selezionaCampo(button, dettagliArea) {
        document
            .querySelectorAll(".campo-button")
            .forEach((btn) => btn.classList.remove("selected"));
        button.classList.add("selected");
        campoSelezionato = button.dataset.campo;
        dettagliArea.querySelector(".campo-nome").textContent =
            campoSelezionato;

        const coordStr = button.dataset.coordinate || null;
        caricaMiniMappa(coordStr);
    }

    function caricaMiniMappa(coordinateStr) {
        if (window.miniMap) window.miniMap.remove();

        const mapDiv = document.getElementById("mini-map");
        window.miniMap = L.map(mapDiv);
        L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
            attribution:
                '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
        }).addTo(window.miniMap);

        const primaryColor = getComputedStyle(document.documentElement)
            .getPropertyValue("--primary")
            .trim();

        if (!coordinateStr) {
            window.miniMap.setView([41.9028, 12.4964], 13);
            return;
        }

        let coords = coordinateStr.replace(/[()]/g, "").split(",");
        const latlngs = [];
        for (let i = 0; i < coords.length; i += 2) {
            if (coords[i] && coords[i + 1]) {
                latlngs.push([
                    parseFloat(coords[i].trim()),
                    parseFloat(coords[i + 1].trim()),
                ]);
            }
        }

        if (latlngs.length >= 3) {
            const polygon = L.polygon(latlngs, { color: primaryColor }).addTo(
                window.miniMap
            );
            window.miniMap.fitBounds(polygon.getBounds());
        } else if (latlngs.length === 1) {
            window.miniMap.setView(latlngs[0], 13);
            L.marker(latlngs[0]).addTo(window.miniMap);
        }
    }

    // Funzione per selezionare automaticamente il campo dall'URL
    async function selezionaCampoAutomatico(dettagliArea) {
        try {
            // Chiama l'API per ottenere le coordinate dalla sessione
            const response = await fetch('/api/get_session_coordinate');
            const coordinateData = await response.json();

            if (campoIdSelezionato) {
                // Trova il bottone del campo con l'ID corrispondente
                const campoButton = document.querySelector(`[data-campo-id="${campoIdSelezionato}"]`);

                if (campoButton) {
                    // Se ci sono coordinate dalla sessione, usale
                    if (coordinateData && coordinateData.coordinate) {
                        campoButton.dataset.coordinate = coordinateData.coordinate;
                    }

                    // Seleziona automaticamente il campo
                    selezionaCampo(campoButton, dettagliArea);
                } else {
                    console.warn(`Campo con ID ${campoIdSelezionato} non trovato`);
                }
            }
        } catch (error) {
            console.error('Errore nel caricamento delle coordinate:', error);
        }
    }

    caricaCampi();

    caricaSensoriInAttesa();
    caricaSensoriConclusi();
    caricaSensoriSospesi();
});

// Gestione click sulle card di stato
document.querySelectorAll('.status-card').forEach(card => {
    card.addEventListener('click', function () {
        document.querySelectorAll('.status-card').forEach(c => c.classList.remove('active'));
        this.classList.add('active');
    });
});

// Funzione per caricare i sensori in attesa dall'API
function caricaSensoriInAttesa() {
    fetch("/api/get_sensor_selected")
        .then((res) => res.json())
        .then((sensorIds) => {
            const cardAttesa = document.querySelector('.status-card[data-status="attesa"]');
            const sensorsListAttesa = cardAttesa.querySelector('.sensors-list');

            sensorsListAttesa.innerHTML = '';

            if (Array.isArray(sensorIds) && sensorIds.length > 0) {
                sensorIds.forEach(sensorId => {

                    const wrapper = document.createElement("div");
                    wrapper.className = "sensor-item sensor-row";
                    wrapper.style.display = "flex";
                    wrapper.style.justifyContent = "space-between";
                    wrapper.style.alignItems = "center";

                    const label = document.createElement("span");
                    label.textContent = sensorId;

                    // FORM PER INVIARE POST A /avvia_irr
                    const form = document.createElement("form");
                    form.method = "POST";
                    form.action = "/avvia_irr";

                    const inputAzione = document.createElement("input");
                    inputAzione.type = "hidden";
                    inputAzione.name = "azione";
                    inputAzione.value = "sospendi";

                    const inputSensore = document.createElement("input");
                    inputSensore.type = "hidden";
                    inputSensore.name = "sensor_id";
                    inputSensore.value = sensorId;

                    const button = document.createElement("button");
                    button.type = "submit";
                    button.textContent = "Sospendi";
                    button.className = "btn-sospendi";

                    form.appendChild(inputAzione);
                    form.appendChild(inputSensore);
                    form.appendChild(button);

                    wrapper.appendChild(label);
                    wrapper.appendChild(form);
                    sensorsListAttesa.appendChild(wrapper);
                });

            } else {
                const noSensor = document.createElement("div");
                noSensor.className = "sensor-item";
                noSensor.textContent = "Nessun sensore in attesa";
                noSensor.style.opacity = "0.7";
                sensorsListAttesa.appendChild(noSensor);
            }
        });
}


function caricaSensoriConclusi() {
    fetch("/api/get_sensor/concluded")
        .then((res) => res.json())
        .then((sensorIds) => {
            const cardConclusi = document.querySelector('.status-card[data-status="conclusi"]');
            if (!cardConclusi) {
                console.error('Card "Conclusi" non trovata');
                return;
            }

            const sensorsListConclusi = cardConclusi.querySelector('.sensors-list');
            if (!sensorsListConclusi) {
                console.error('Lista sensori conclusi non trovata');
                return;
            }

            sensorsListConclusi.innerHTML = '';

            if (Array.isArray(sensorIds) && sensorIds.length > 0) {
                sensorIds.forEach(sensorId => {
                    const sensorDiv = document.createElement('div');
                    sensorDiv.className = 'sensor-item';
                    sensorDiv.textContent = sensorId;
                    sensorsListConclusi.appendChild(sensorDiv);
                });
            } else {
                const noSensorDiv = document.createElement('div');
                noSensorDiv.className = 'sensor-item';
                noSensorDiv.textContent = 'Nessun sensore concluso';
                noSensorDiv.style.opacity = '0.6';
                sensorsListConclusi.appendChild(noSensorDiv);
            }
        })
        .catch((error) => {
            console.error('Errore nel caricamento dei sensori conclusi:', error);
        });
}

// Funzione per caricare i sensori sospesi dall'API
function caricaSensoriSospesi() {
    fetch("/api/get_sensor/suspended")
        .then((res) => res.json())
        .then((sensorIds) => {

            const cardSospesi = document.querySelector('.status-card[data-status="sospesi"]');
            const sensorsListSospesi = cardSospesi.querySelector('.sensors-list');

            sensorsListSospesi.innerHTML = '';

            if (Array.isArray(sensorIds) && sensorIds.length > 0) {

                sensorIds.forEach(sensorId => {

                    const wrapper = document.createElement("div");
                    wrapper.className = "sensor-item sensor-row";
                    wrapper.style.display = "flex";
                    wrapper.style.justifyContent = "space-between";
                    wrapper.style.alignItems = "center";

                    const label = document.createElement("span");
                    label.textContent = sensorId;

                    // FORM POST PER RIATTIVARE
                    const form = document.createElement("form");
                    form.method = "POST";
                    form.action = "/avvia_irr";

                    const inputAzione = document.createElement("input");
                    inputAzione.type = "hidden";
                    inputAzione.name = "azione";
                    inputAzione.value = "riattiva";   // <-- qui cambia

                    const inputSensore = document.createElement("input");
                    inputSensore.type = "hidden";
                    inputSensore.name = "sensor_id";
                    inputSensore.value = sensorId;

                    const button = document.createElement("button");
                    button.type = "submit";
                    button.textContent = "Riattiva";   // <-- testo pulsante
                    button.className = "btn-riattiva";

                    form.appendChild(inputAzione);
                    form.appendChild(inputSensore);
                    form.appendChild(button);

                    wrapper.appendChild(label);
                    wrapper.appendChild(form);
                    sensorsListSospesi.appendChild(wrapper);
                });

            } else {
                const noSensor = document.createElement("div");
                noSensor.className = "sensor-item";
                noSensor.textContent = "Nessun sensore sospeso";
                noSensor.style.opacity = "0.7";
                sensorsListSospesi.appendChild(noSensor);
            }
        })
        .catch((error) => {
            console.error("Errore nel caricamento dei sensori sospesi:", error);
        });
}
