document.addEventListener("DOMContentLoaded", function () {
    // Carica dinamicamente Leaflet se non è già definito
    if (typeof L === "undefined") {
        // Crea link per CSS di Leaflet
        const leafletCSS = document.createElement("link");
        leafletCSS.rel = "stylesheet";
        leafletCSS.href = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css";
        document.head.appendChild(leafletCSS);

        // Carica script di Leaflet
        const leafletScript = document.createElement("script");
        leafletScript.src = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js";
        leafletScript.onload = initializeApp; // Inizializza l'app dopo il caricamento di Leaflet
        document.head.appendChild(leafletScript);
    } else {
        // Se Leaflet è già caricato, inizia subito
        initializeApp();
    }

    function initializeApp() {
        const containerCampi = document.querySelector(".campi");

        // Funzione per caricare i campi tramite l'API
        function caricaCampi() {
            fetch("/api/numCampi")
                .then((response) => response.json())
                .then((infoCampi) => {
                    //console.log(infoCampi);
                    if (infoCampi > 0) {
                        containerCampi.innerHTML = "";
                        caricaInfoCampi();
                    } else {
                        // Messaggio se non ci sono campi
                        containerCampi.innerHTML =
                            '<div class="campo-card text-center"><h3>Nessun campo disponibile</h3><p>Aggiungi il tuo primo campo per iniziare.</p></div>';
                    }
                })
                .catch((error) => {
                    console.error("Errore nel caricamento dei campi:", error);
                    containerCampi.innerHTML =
                        '<div class="campo-card text-center"><h3>Errore nel caricamento</h3><p>Si è verificato un problema nel caricamento dei campi.</p></div>';
                });
        }

        function caricaInfoCampi() {
            fetch("/api/infoCampi")
                .then((response) => response.json())
                .then((data) => {
                    console.log("ciao");
                    console.log(data);

                    const campi = data.split("|").filter((el) => el.trim() !== ""); // Split delle info campi
                    campi.forEach((campo, index) => {
                        const [coordinate, comune] = campo.split("/");
                        let coordinateComplete = coordinate.split("(").join("");
                        coordinateComplete = coordinateComplete.split(")").join("");
                        const coordinateFinale = coordinateComplete.split(",");
                        console.log(coordinateFinale);

                        // Creazione dell'elenco numerato delle coordinate
                        let coordinateList = '<ol class="coordinate-list">';
                        for (let i = 0; i < coordinateFinale.length; i += 2) {
                            if (coordinateFinale[i] && coordinateFinale[i + 1]) {
                                coordinateList += `<li>Lat: ${coordinateFinale[
                                    i
                                ].trim()}, Lng: ${coordinateFinale[i + 1].trim()}</li>`;
                            }
                        }
                        coordinateList += "</ol>";

                        const mapId = `map-${index}`;

                        const campoHTML = `
                          <div class="campo-card">
                              <div class="row align-items-center">
                                  <!-- Colonna sinistra: Testo -->
                                  <div class="col-md-6">
                                      <h2>Campo ${index + 1} - ${comune}</h2>
                                      <div class="mt-3">
                                          <h5>Coordinate:</h5>
                                          ${coordinateList}
                                      </div>
                                      <button class="btn btn-primary mt-3" type="button">Dettagli</button>
                                  </div>
                                  <!-- Colonna destra: Mappa -->
                                  <div class="col-md-6">
                                      <div id="${mapId}" class="map-container"></div>
                                  </div>
                              </div>
                          </div>
                      `;

                        containerCampi.innerHTML += campoHTML;

                        // Dopo aver aggiunto il campo al DOM, inizializza la mappa
                        setTimeout(() => {
                            initializeMap(mapId, coordinateFinale);
                        }, 100);
                    });
                })
                .catch((error) => {
                    console.error(
                        "Errore nel caricamento delle info dei campi:",
                        error
                    );
                    containerCampi.innerHTML =
                        '<div class="campo-card text-center"><h3>Errore nel caricamento</h3><p>Si è verificato un problema nel caricamento delle informazioni dei campi.</p></div>';
                });
        }

        // Funzione per inizializzare la mappa Leaflet e disegnare il poligono
        function initializeMap(mapId, coordinates) {
            const mapElement = document.getElementById(mapId);

            const latlngs = [];
            for (let i = 0; i < coordinates.length; i += 2) {
                if (coordinates[i] && coordinates[i + 1]) {
                    // Supponendo che le coordinate siano in formato lat,lng
                    latlngs.push(
                        L.latLng(
                            parseFloat(coordinates[i].trim()),
                            parseFloat(coordinates[i + 1].trim())
                        )
                    );
                }
            }

            if (latlngs.length < 3) {
                console.error(
                    `Non ci sono abbastanza coordinate valide per il campo ${mapId}`
                );
                mapElement.innerHTML =
                    '<div class="text-center p-4" style="color: var(--text-body);">Coordinate insufficienti per disegnare il campo</div>';
                return;
            }

            // Inizializza la mappa
            const map = L.map(mapId).setView(
                [latlngs[0].lat, latlngs[0].lng],
                13
            );

            // Aggiungi il layer della mappa
            L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
                attribution:
                    '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
            }).addTo(map);

            // Crea il layer per gli elementi disegnati
            const drawnItems = new L.FeatureGroup().addTo(map);

            // Ottieni il colore primario dal CSS
            const primaryColor = getComputedStyle(document.documentElement)
                .getPropertyValue("--primary")
                .trim();

            // Crea e aggiungi il poligono con il colore del tema
            const polygon = L.polygon(latlngs, {
                color: primaryColor,
                fillColor: primaryColor,
                fillOpacity: 0.2
            }).addTo(drawnItems);

            // Adatta la vista della mappa ai limiti del poligono
            map.fitBounds(polygon.getBounds());
        }

        caricaCampi();
    }
});