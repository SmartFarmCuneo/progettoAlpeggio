document.addEventListener("DOMContentLoaded", function () {
    const containerCampi = document.getElementById("campi");
    let campoSelezionato = null;
    let campoIdSelezionato = null;

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
              <div class="azione-buttons">
                <button id="gestisci-campo-btn" class="azione-button">Gestisci Campo</button>
                <div class="dropdown-container">
                  <button id="avvia-operazioni-btn" class="azione-button">Avvia operazioni</button>
                  <div id="dropdown-menu" class="dropdown-menu hidden">
                    <a href="/assoc_gest_sens" class="dropdown-item">Associa - gestisci sensori</a>
                    <a href="/ini_irr" class="dropdown-item">Avvia irrigazione</a>
                    <a href="#" id="registro-irrigazioni-link" class="dropdown-item">Registro irrigazioni</a>
                  </div>
                </div>
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

                    // Seleziona automaticamente il primo campo
                    selezionaCampo(listaPulsanti.firstChild, dettagliArea);

                    // Inizializza il menu a tendina
                    inizializzaDropdown();

                    // Inizializza il pulsante gestisci campo
                    inizializzaGestisciCampo();

                    // Inizializza il link registro irrigazioni
                    inizializzaRegistroIrrigazioni();
                } else {
                    containerCampi.innerHTML = `
            <div class="nessun-campo">
              Nessun campo disponibile. Aggiungi un nuovo campo per iniziare.
            </div>
          `;
                }
            });
    }

    function inizializzaGestisciCampo() {
        const gestisciBtn = document.getElementById("gestisci-campo-btn");

        if (gestisciBtn) {
            gestisciBtn.addEventListener("click", function (e) {
                e.preventDefault();

                if (campoIdSelezionato) {
                    window.location.href = `/gestioneCampo?campo_id=${campoIdSelezionato}`;
                } else {
                    alert("Seleziona un campo prima di procedere con la gestione.");
                }
            });
        }
    }

    function inizializzaRegistroIrrigazioni() {
        const registroIrrLink = document.getElementById("registro-irrigazioni-link");

        if (registroIrrLink) {
            registroIrrLink.addEventListener("click", function (e) {
                e.preventDefault();

                if (campoIdSelezionato) {
                    console.log("Campo ID selezionato:", campoIdSelezionato);
                    window.location.href = `/reg_irr?campo_id=${campoIdSelezionato}`;
                } else {
                    alert("Seleziona un campo prima di procedere.");
                }
            });
        }
    }

    function inizializzaDropdown() {
        const avviaBtn = document.getElementById("avvia-operazioni-btn");
        const dropdownMenu = document.getElementById("dropdown-menu");

        if (avviaBtn && dropdownMenu) {
            avviaBtn.addEventListener("click", function (e) {
                e.preventDefault();

                const rect = avviaBtn.getBoundingClientRect();
                const windowHeight = window.innerHeight;
                const menuHeight = 150;
                const spaceBelow = windowHeight - rect.bottom;
                const spaceAbove = rect.top;

                dropdownMenu.classList.remove("dropdown-up", "dropdown-down");

                if (spaceBelow < menuHeight && spaceAbove > spaceBelow) {
                    dropdownMenu.classList.add("dropdown-up");
                } else {
                    dropdownMenu.classList.add("dropdown-down");
                }

                dropdownMenu.classList.toggle("hidden");
                avviaBtn.classList.toggle("active");
            });

            document.addEventListener("click", function (e) {
                if (!e.target.closest(".dropdown-container")) {
                    dropdownMenu.classList.add("hidden");
                    avviaBtn.classList.remove("active");
                }
            });
        }
    }

    function selezionaCampo(button, dettagliArea) {
        document
            .querySelectorAll(".campo-button")
            .forEach((btn) => btn.classList.remove("selected"));
        button.classList.add("selected");
        campoSelezionato = button.dataset.campo;
        campoIdSelezionato = button.dataset.campoId;
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

    caricaCampi();
});

// Gestione click sulle card di stato
document.querySelectorAll('.status-card').forEach(card => {
    card.addEventListener('click', function () {
        document.querySelectorAll('.status-card').forEach(c => c.classList.remove('active'));
        this.classList.add('active');
    });
});

// Inizializzazione mappa
if (typeof L !== 'undefined') {
    const miniMap = L.map('mini-map').setView([41.9028, 12.4964], 13);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
    }).addTo(miniMap);
}