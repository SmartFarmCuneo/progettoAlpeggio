// Inizializza la mappa
var map = L.map("map").setView([41.9028, 12.4964], 13);
let coordinateSelezionate = "";

// Tile OpenStreetMap
L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
}).addTo(map);

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