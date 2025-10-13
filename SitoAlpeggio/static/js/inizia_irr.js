// Dati dei sensori (sostituire con dati reali dal backend)
const sensorsData = [
    { id: 1, name: 'Sensore 1', location: 'Campo Nord', status: 'disponibile', icon: '💧' },
    { id: 2, name: 'Sensore 2', location: 'Campo Nord', status: 'disponibile', icon: '💧' },
    { id: 3, name: 'Sensore 3', location: 'Campo Est', status: 'disponibile', icon: '💧' },
    { id: 4, name: 'Sensore 4', location: 'Campo Sud', status: 'in-uso', icon: '💧' },
    { id: 5, name: 'Sensore 5', location: 'Campo Sud', status: 'disponibile', icon: '💧' },
    { id: 6, name: 'Sensore 6', location: 'Campo Ovest', status: 'disponibile', icon: '💧' },
    { id: 7, name: 'Sensore 7', location: 'Campo Ovest', status: 'disponibile', icon: '💧' },
    { id: 8, name: 'Sensore 8', location: 'Campo Centro', status: 'disponibile', icon: '💧' },
    { id: 9, name: 'Sensore 9', location: 'Campo Centro', status: 'offline', icon: '💧' },
    { id: 10, name: 'Sensore 10', location: 'Campo Nord-Est', status: 'disponibile', icon: '💧' },
    { id: 11, name: 'Sensore 11', location: 'Campo Sud-Est', status: 'disponibile', icon: '💧' },
    { id: 12, name: 'Sensore 12', location: 'Campo Sud-Ovest', status: 'disponibile', icon: '💧' },
];

const selectedSensors = new Set();
const sensorsGrid = document.getElementById('sensors-grid');
const selectedCount = document.getElementById('selected-count');
const startBtn = document.getElementById('start-btn');

// Genera le card dei sensori
function renderSensors() {
    sensorsGrid.innerHTML = '';
    sensorsData.forEach(sensor => {
        const card = document.createElement('div');
        card.className = 'sensor-card';
        card.dataset.id = sensor.id;

        // Disabilita sensori non disponibili
        if (sensor.status !== 'disponibile') {
            card.style.opacity = '0.6';
            card.style.cursor = 'not-allowed';
        }

        card.innerHTML = `
            <div class="sensor-checkbox"></div>
            <div class="sensor-name">${sensor.name}</div>
            <div class="sensor-location">${sensor.location}</div>
            <span class="sensor-status ${sensor.status}">
              ${sensor.status === 'disponibile' ? 'Disponibile' :
                sensor.status === 'in-uso' ? 'In Uso' : 'Offline'}
            </span>
          `;

        // Aggiungi evento click solo se disponibile
        if (sensor.status === 'disponibile') {
            card.addEventListener('click', () => toggleSensor(sensor.id, card));
        }

        sensorsGrid.appendChild(card);
    });
}

// Toggle selezione sensore
function toggleSensor(id, card) {
    if (selectedSensors.has(id)) {
        selectedSensors.delete(id);
        card.classList.remove('selected');
    } else {
        selectedSensors.add(id);
        card.classList.add('selected');
    }
    updateUI();
}

// Aggiorna UI
function updateUI() {
    selectedCount.textContent = selectedSensors.size;
    startBtn.disabled = selectedSensors.size === 0;
}

// Seleziona tutti i sensori disponibili
document.getElementById('select-all').addEventListener('click', () => {
    sensorsData.forEach(sensor => {
        if (sensor.status === 'disponibile') {
            selectedSensors.add(sensor.id);
            const card = document.querySelector(`[data-id="${sensor.id}"]`);
            if (card) card.classList.add('selected');
        }
    });
    updateUI();
});

// Deseleziona tutti
document.getElementById('deselect-all').addEventListener('click', () => {
    selectedSensors.clear();
    document.querySelectorAll('.sensor-card').forEach(card => {
        card.classList.remove('selected');
    });
    updateUI();
});

// Avvia irrigazione
startBtn.addEventListener('click', () => {
    if (selectedSensors.size > 0) {
        // Salva i sensori selezionati (ad esempio in sessionStorage o invia al backend)
        const sensorsArray = Array.from(selectedSensors);
        sessionStorage.setItem('selectedSensors', JSON.stringify(sensorsArray));

        // Reindirizza alla pagina di monitoraggio
        window.location.href = '/avvia_irr'; // Modifica con il tuo route
    }
});

// Inizializza la pagina
renderSensors();