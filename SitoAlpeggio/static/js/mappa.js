// Inizializza la mappa
var map = L.map("map").setView([41.9028, 12.4964], 13);
let coordinateSelezionate = "";

// Tile OpenStreetMap
L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
}).addTo(map);

var drawnItems = new L.FeatureGroup();
map.addLayer(drawnItems);

var drawControl = new L.Control.Draw({
    edit: { featureGroup: drawnItems, edit: false, remove: true },
    draw: {
        polygon: true,
        rectangle: false,
        polyline: false,
        circle: false,
        circlemarker: false,
        marker: false,
    },
});
map.addControl(drawControl);

function updateCoordinatesList(latlngs) {
    var coordinatesElement = document.getElementById("coordinates");
    coordinatesElement.innerHTML = "";
    coordinateSelezionate = "";

    latlngs.forEach(function (latlng, index) {
        let coordLat = latlng.lat.toFixed(6);
        let coordLng = latlng.lng.toFixed(6);
        coordinateSelezionate += `(${coordLat},${coordLng}),`;
        coordinatesElement.innerHTML += `
            <tr>
              <td>${index + 1}</td>
              <td>${coordLat}</td>
              <td>${coordLng}</td>
            </tr>`;
    });
}

map.on(L.Draw.Event.CREATED, function (e) {
    if (drawnItems.getLayers().length > 0) {
        drawnItems.clearLayers();
        alert("La nuova area selezionata sostituirà quella precedente");
    }

    var layer = e.layer;
    drawnItems.addLayer(layer);
    var latlngs = layer.getLatLngs()[0];
    updateCoordinatesList(latlngs);
});

// Salvataggio
document
    .getElementById("geoButton")
    .addEventListener("click", function () {
        if (drawnItems.getLayers().length === 0) {
            alert("Seleziona un'area prima di salvare le coordinate!");
        } else {
            document.getElementById("coordinateInput").value =
                coordinateSelezionate;
            document.getElementById("coordinateForm").submit();
        }
    });

async function fetchConsent() {
    try {
        const res = await fetch("/get-consent", {
            method: "GET",
            credentials: "same-origin",
        });
        if (!res.ok) return null;
        return await res.json();
    } catch (e) {
        return null;
    }
}

function centraMappaSuUtente() {
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
            function (position) {
                const lat = position.coords.latitude;
                const lng = position.coords.longitude;
                map.setView([lat, lng], 15); // zoom più vicino
                //L.marker([lat, lng]).addTo(map).bindPopup("Sei qui").openPopup();
            },
            function (error) {
                console.warn("Impossibile ottenere la posizione:", error.message);
            }
        );
    } else {
        console.warn("Geolocalizzazione non supportata dal browser");
    }
}

document.addEventListener("DOMContentLoaded", async function () {
    const consent = await fetchConsent();
    if (consent && consent.necessary && consent.analytics && consent.ads) {
        // 🔑 solo se ha accettato TUTTI i cookie
        centraMappaSuUtente();
    }
});