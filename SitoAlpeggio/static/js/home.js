document.addEventListener("DOMContentLoaded", function () {
    const containerCampi = document.getElementById("campi");
    let campoSelezionato = null;
    let campoIdSelezionato = null; // Aggiungiamo l'ID del campo

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
                    <a href="/contr_man" class="dropdown-item">Controllo manuale</a>
                    <a href="/ric_spec" class="dropdown-item">Ricerca specifica</a>
                    <a href="/ric_tot_parz" class="dropdown-item">Ricerca totale-parziale</a>
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
                        button.dataset.campoId = campo.id_t; // Aggiungiamo l'ID del campo
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
            gestisciBtn.addEventListener("click", function(e) {
                e.preventDefault();
                
                if (campoIdSelezionato) {
                    // Reindirizza alla pagina di gestione campo con l'ID del campo selezionato
                    window.location.href = `/gestioneCampo?campo_id=${campoIdSelezionato}`;
                } else {
                    alert("Seleziona un campo prima di procedere con la gestione.");
                }
            });
        }
    }

    function inizializzaDropdown() {
        const avviaBtn = document.getElementById("avvia-operazioni-btn");
        const dropdownMenu = document.getElementById("dropdown-menu");

        if (avviaBtn && dropdownMenu) {
            avviaBtn.addEventListener("click", function(e) {
                e.preventDefault();
                
                // Calcola la posizione ottimale per il dropdown
                const rect = avviaBtn.getBoundingClientRect();
                const windowHeight = window.innerHeight;
                const menuHeight = 150; // Altezza approssimativa del menu
                const spaceBelow = windowHeight - rect.bottom;
                const spaceAbove = rect.top;
                
                // Rimuovi classi precedenti
                dropdownMenu.classList.remove("dropdown-up", "dropdown-down");
                
                // Decidi se aprire verso l'alto o verso il basso
                if (spaceBelow < menuHeight && spaceAbove > spaceBelow) {
                    dropdownMenu.classList.add("dropdown-up");
                } else {
                    dropdownMenu.classList.add("dropdown-down");
                }
                
                dropdownMenu.classList.toggle("hidden");
                avviaBtn.classList.toggle("active");
            });

            // Chiudi il menu se si clicca fuori
            document.addEventListener("click", function(e) {
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
        campoIdSelezionato = button.dataset.campoId; // Salviamo l'ID del campo selezionato
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

        // Parsing formato Visualizza Campi
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