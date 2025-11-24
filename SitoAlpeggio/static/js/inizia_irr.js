document.addEventListener("DOMContentLoaded", function () {
    let sensorsData = [];
    const selectedSensors = new Set();
    const sensorsGrid = document.getElementById('sensors-grid');
    const selectedCount = document.getElementById('selected-count');
    const startBtn = document.getElementById('start-btn');

    function caricaSensori() {
        fetch("/api/get_sensor")
            .then((res) => res.json())
            .then((data) => {
                console.log("Dati ricevuti dall'API:", data);

                if (data && data !== "nessuna info") {
                    // Parsing dei dati ricevuti
                    sensorsData = parseSensoriData(data);
                    console.log("Sensori parsati:", sensorsData);

                    if (sensorsData.length > 0) {
                        renderSensors();
                    } else {
                        sensorsGrid.innerHTML = '<p style="text-align: center; color: #666;">Nessun sensore disponibile</p>';
                    }
                } else {
                    sensorsGrid.innerHTML = '<p style="text-align: center; color: #666;">Nessun sensore disponibile</p>';
                    console.log("Nessun sensore trovato");
                }
            })
            .catch((error) => {
                console.error("Errore nel caricamento dei sensori:", error);
                sensorsGrid.innerHTML = '<p style="text-align: center; color: #ff6b6b;">Errore nel caricamento dei sensori</p>';
            });
    }

    // Funzione per convertire lo stato del sensore
    function getStatusInfo(statoSens) {
        switch (statoSens) {
            case 'C':
                return { status: 'disponibile', label: 'Disponibile' };
            case 'O':
                return { status: 'in-uso', label: 'In Uso' };
            case 'S':
                return { status: 'offline', label: 'Sospeso' };
            default:
                return { status: 'offline', label: 'Sconosciuto' };
        }
    }

    // Funzione per parsare i dati ricevuti dall'API
    function parseSensoriData(dataString) {
        const sensori = [];

        // Rimuovi l'ultimo "|" se presente e dividi per "|"
        const sensoriArray = dataString.trim().split('|').filter(s => s.trim() !== '');

        sensoriArray.forEach((sensoreStr, index) => {
            // Dividi per "/" per ottenere posizione, Node_Id e stato_sens
            const parti = sensoreStr.split('/');

            if (parti.length >= 3) {
                const posizione = parti[0].trim();
                const nodeId = parti[1].trim();
                const statoSens = parti[2].trim();

                const statusInfo = getStatusInfo(statoSens);

                sensori.push({
                    id: nodeId,
                    name: `Sensore ${nodeId}`,
                    location: posizione,
                    status: statusInfo.status,
                    statusLabel: statusInfo.label,
                    icon: '💧'
                });
            }
        });

        return sensori;
    }

    // Genera le card dei sensori
    function renderSensors() {
        sensorsGrid.innerHTML = '';

        if (!sensorsData || sensorsData.length === 0) {
            sensorsGrid.innerHTML = '<p style="text-align: center; color: #666;">Nessun sensore disponibile</p>';
            return;
        }

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
                  ${sensor.statusLabel}
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
            const sensorsArray = Array.from(selectedSensors);
            const campoId = new URLSearchParams(window.location.search).get('campo_id');

            fetch('/ini_irr', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    campo_id: campoId,
                    selectedSensors: sensorsArray
                })
            })
                .then(response => response.json())
                .then(data => {
                    console.log("Risposta dal server:", data);
                    // Reindirizza alla pagina di monitoraggio
                    window.location.href = `/avvia_irr?campo_id=${campoId}`;
                })
                .catch(err => console.error(err));
        }
    });

    // Carica i sensori all'avvio
    caricaSensori();
});