document.addEventListener("DOMContentLoaded", () => {

    const mapDiv = document.getElementById("mini-map");
    const coordinateCampo = mapDiv.dataset.coord || null;

    console.log("Coordinate campo:", coordinateCampo);

    caricaSensoriInAttesa();
    caricaSensoriConclusi();
    caricaSensoriSospesi();
    caricaMiniMappa(coordinateCampo);

    // === CLICK CARD STATO ===
    document.querySelectorAll(".status-card").forEach(card => {
        card.addEventListener("click", () => {
            document.querySelectorAll(".status-card")
                .forEach(c => c.classList.remove("active"));
            card.classList.add("active");
        });
    });
});


function caricaMiniMappa(coordinateStr) {

    const mapDiv = document.getElementById("mini-map");
    if (!mapDiv) return;

    // reset mappa se già esiste
    if (window.miniMap) {
        window.miniMap.remove();
    }

    window.miniMap = L.map("mini-map");

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: "&copy; OpenStreetMap",
        maxZoom: 19
    }).addTo(window.miniMap);

    // nessuna coordinata → vista default
    if (!coordinateStr || coordinateStr.trim() === "") {
        window.miniMap.setView([41.9028, 12.4964], 12);
        return;
    }

    const latlngs = [];

    const matches = coordinateStr.match(/\(([^)]+)\)/g);

    if (!matches) {
        console.error("Formato coordinate non valido:", coordinateStr);
        window.miniMap.setView([41.9028, 12.4964], 12);
        return;
    }

    matches.forEach(coppia => {
        const [lat, lng] = coppia
            .replace(/[()]/g, "")
            .split(",")
            .map(Number);

        if (!isNaN(lat) && !isNaN(lng)) {
            latlngs.push([lat, lng]);
        }
    });

    // singolo punto
    if (latlngs.length === 1) {
        L.marker(latlngs[0]).addTo(window.miniMap);
        window.miniMap.setView(latlngs[0], 16);
        return;
    }

    // poligono
    if (latlngs.length > 1) {
        const polygon = L.polygon(latlngs, {
            color: "green",
            fillColor: "#4CAF50",
            fillOpacity: 0.4
        }).addTo(window.miniMap);

        window.miniMap.fitBounds(polygon.getBounds());
    }
}

// =====================
// SENSORI IN ATTESA
// =====================
function caricaSensoriInAttesa() {
    fetch("/api/get_sensor_selected")
        .then(res => res.json())
        .then(sensorIds => {

            const list = document.querySelector('[data-status="attesa"] .sensors-list');
            list.innerHTML = "";

            if (!sensorIds.length) {
                list.innerHTML = "<div class='sensor-item'>Nessun sensore in attesa</div>";
                return;
            }

            sensorIds.forEach(id => {
                const row = document.createElement("div");
                row.className = "sensor-item";

                row.innerHTML = `
                    <span>${id}</span>
                    <form method="POST" action="/avvia_irr">
                        <input type="hidden" name="azione" value="sospendi">
                        <input type="hidden" name="sensor_id" value="${id}">
                        <button class="btn-sospendi">Sospendi</button>
                    </form>
                `;

                list.appendChild(row);
            });
        });
}


// =====================
// SENSORI CONCLUSI
// =====================
function caricaSensoriConclusi() {
    fetch("/api/get_sensor/concluded")
        .then(res => res.json())
        .then(sensorIds => {

            const list = document.querySelector('[data-status="conclusi"] .sensors-list');
            list.innerHTML = "";

            if (!sensorIds.length) {
                list.innerHTML = "<div class='sensor-item'>Nessun sensore concluso</div>";
                return;
            }

            sensorIds.forEach(id => {
                const div = document.createElement("div");
                div.className = "sensor-item";
                div.textContent = id;
                list.appendChild(div);
            });
        });
}


// =====================
// SENSORI SOSPESI
// =====================
function caricaSensoriSospesi() {
    fetch("/api/get_sensor/suspended")
        .then(res => res.json())
        .then(sensorIds => {

            const list = document.querySelector('[data-status="sospesi"] .sensors-list');
            list.innerHTML = "";

            if (!sensorIds.length) {
                list.innerHTML = "<div class='sensor-item'>Nessun sensore sospeso</div>";
                return;
            }

            sensorIds.forEach(id => {
                const row = document.createElement("div");
                row.className = "sensor-item";

                row.innerHTML = `
                    <span>${id}</span>
                    <form method="POST" action="/avvia_irr">
                        <input type="hidden" name="azione" value="riattiva">
                        <input type="hidden" name="sensor_id" value="${id}">
                        <button class="btn-sospendi">Riattiva</button>
                    </form>
                `;

                list.appendChild(row);
            });
        });
}
