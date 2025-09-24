document.addEventListener("DOMContentLoaded", function () {
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
              <div class="azione-buttons">
                <a href="/gestioneCampo" class="azione-button">Gestisci Campo</a>
                <a href="/storici" class="azione-button">Avvia operazioni</a>
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
                        button.dataset.coordinate = campo.coordinate || null;

                        button.addEventListener("click", () =>
                            selezionaCampo(button, dettagliArea)
                        );
                        listaPulsanti.appendChild(button);
                    });

                    // Seleziona automaticamente il primo campo
                    selezionaCampo(listaPulsanti.firstChild, dettagliArea);
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