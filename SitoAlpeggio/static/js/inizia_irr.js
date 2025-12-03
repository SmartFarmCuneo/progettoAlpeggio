document.addEventListener("DOMContentLoaded", function () {

    let sensorsData = [];
    const selectedSensors = new Set();

    const sensorsGrid = document.getElementById('sensors-grid');
    const selectedCount = document.getElementById('selected-count');
    const startBtn = document.getElementById('start-btn');

    // Funzione per mostrare il popup
    function mostraPopup(messaggio) {
        // Crea overlay scuro
        const overlay = document.createElement('div');
        overlay.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.5);
            display: flex;
            justify-content: center;
            align-items: center;
            z-index: 9999;
        `;

        // Crea popup
        const popup = document.createElement('div');
        popup.style.cssText = `
            background: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
            max-width: 400px;
            text-align: center;
        `;

        popup.innerHTML = `
            <h3 style="margin-bottom: 15px; color: #ff6b6b;">Attenzione</h3>
            <p style="margin-bottom: 20px; color: #333;">${messaggio}</p>
            <button id="close-popup" style="
                background: var(--primary, #4CAF50);
                color: white;
                border: none;
                padding: 10px 30px;
                border-radius: 5px;
                cursor: pointer;
                font-size: 16px;
            ">OK</button>
        `;

        overlay.appendChild(popup);
        document.body.appendChild(overlay);

        // Chiudi popup al click
        document.getElementById('close-popup').addEventListener('click', () => {
            document.body.removeChild(overlay);
        });
    }

    // Carica sensori da API
    function caricaSensori() {
        fetch("/api/get_sensor")
            .then((res) => res.json())
            .then((data) => {
                console.log("Dati ricevuti dall'API:", data);

                if (data && data !== "nessuna info") {
                    sensorsData = parseSensoriData(data);
                    console.log("Sensori analizzati:", sensorsData);

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

    // Ritorna info stato
    function getStatusInfo(statoSens) {
        switch (statoSens) {
            case 'C': return { status: 'disponibile', label: 'Disponibile' };
            case 'O': return { status: 'in-uso', label: 'In Uso' };
            case 'S': return { status: 'offline', label: 'Sospeso' };
            default:  return { status: 'offline', label: 'Sconosciuto' };
        }
    }

    // Parsing stringa ricevuta
    function parseSensoriData(dataString) {
        const sensori = [];

        const sensoriArray = dataString
            .trim()
            .split('|')
            .filter(s => s.trim() !== '');

        sensoriArray.forEach((sensoreStr) => {
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

    // Render sensori
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

            if (sensor.status === 'disponibile') {
                card.addEventListener('click', () => toggleSensor(sensor.id, card));
            }

            sensorsGrid.appendChild(card);
        });
    }

    // Selezione sensori
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

    // Aggiorna elementi UI
    function updateUI() {
        selectedCount.textContent = selectedSensors.size;
        startBtn.disabled = selectedSensors.size === 0;
    }

    // Seleziona tutti
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

    // Funzione per verificare lo stato della sessione
    function verificaSessione() {
        return fetch('/api/get_session_data')
            .then(response => response.json())
            .then(data => {
                console.log("Stato sessione:", data);
                return data;
            })
            .catch(error => {
                console.error("Errore nella verifica della sessione:", error);
                return null;
            });
    }

    // Avvio irrigazione con controllo sessione
    startBtn.addEventListener('click', async () => {
        if (selectedSensors.size > 0) {
            // Prima verifica lo stato della sessione
            const sessionData = await verificaSessione();
            
            if (sessionData === "Stop") {
                mostraPopup("Sessione di irrigazione già avviata. Terminare quella corrente per proseguire con una prossima.");
                return;
            }
            
            if (sessionData !== "Go") {
                mostraPopup("Errore nella verifica dello stato. Riprova più tardi.");
                return;
            }

            // Se la verifica è OK, procedi con l'invio
            const sensorsArray = Array.from(selectedSensors);
            const campoId = new URLSearchParams(window.location.search).get('campo_id');

            fetch('/ini_irr', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ campo_id: campoId, selectedSensors: sensorsArray })
            })
                .then(response => response.json())
                .then(data => {
                    console.log("Risposta dal server:", data);
                    
                    // Controlla lo stato della risposta
                    if (data.status === "ok") {
                        // Se lo stato è "ok", procedi con il redirect
                        window.location.href = `/avvia_irr?campo_id=${campoId}`;
                    } else if (data.status === "no") {
                        // Se lo stato è "no", mostra il popup
                        mostraPopup("Sessione di irrigazione già avviata. Terminare quella corrente per proseguire con una prossima.");
                    } else {
                        // Gestisci altri possibili stati
                        mostraPopup("Errore sconosciuto durante l'avvio dell'irrigazione.");
                    }
                })
                .catch(err => {
                    console.error(err);
                    mostraPopup("Errore durante l'avvio dell'irrigazione. Riprova.");
                });
        }
    });

    // Carica i sensori all'avvio
    caricaSensori();

});