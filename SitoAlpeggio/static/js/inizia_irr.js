document.addEventListener("DOMContentLoaded", function () {

    let sensorsData = [];
    const selectedSensors  = new Set();
    const posizioniSensori = {};  // { node_id: { latitude, longitude, accuracy } }

    const sensorsGrid  = document.getElementById('sensors-grid');
    const selectedCount = document.getElementById('selected-count');
    const startBtn     = document.getElementById('start-btn');

    // ---------------------------------------------------------------
    // POPUP
    // ---------------------------------------------------------------
    function mostraPopup(messaggio) {
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

        document.getElementById('close-popup').addEventListener('click', () => {
            document.body.removeChild(overlay);
        });
    }

    // ---------------------------------------------------------------
    // CARICA SENSORI DA API
    // ---------------------------------------------------------------
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

    // ---------------------------------------------------------------
    // STATO SENSORE
    // ---------------------------------------------------------------
    function getStatusInfo(statoSens) {
        switch (statoSens) {
            case 'C': return { status: 'disponibile', label: 'Disponibile' };
            case 'O': return { status: 'in-uso',      label: 'In Uso' };
            case 'S': return { status: 'offline',     label: 'Sospeso' };
            default:  return { status: 'offline',     label: 'Sconosciuto' };
        }
    }

    // ---------------------------------------------------------------
    // PARSING STRINGA SENSORI
    // ---------------------------------------------------------------
    function parseSensoriData(dataString) {
        const sensori = [];

        const sensoriArray = dataString
            .trim()
            .split('|')
            .filter(s => s.trim() !== '');

        sensoriArray.forEach((sensoreStr) => {
            const parti = sensoreStr.split('/');

            if (parti.length >= 3) {
                const nome_sens  = parti[0].trim();
                const nodeId     = parti[1].trim();
                const statoSens  = parti[2].trim();
                const statusInfo = getStatusInfo(statoSens);

                sensori.push({
                    id:          nodeId,
                    name:        nome_sens,
                    status:      statusInfo.status,
                    statusLabel: statusInfo.label,
                    icon:        '💧'
                });
            }
        });

        return sensori;
    }

    // ---------------------------------------------------------------
    // RENDER SENSORI
    // ---------------------------------------------------------------
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
                card.style.cursor  = 'not-allowed';
            }

            card.innerHTML = `
                <div class="sensor-checkbox"></div>
                <div class="sensor-name">${sensor.name}</div>
                <div class="sensor-id">${sensor.id}</div>
                <span class="sensor-status ${sensor.status}">
                    ${sensor.statusLabel}
                </span>
                <button class="location-btn" data-sensor-id="${sensor.id}" title="Mostra posizione in tempo reale">
                    Rileva Posizione
                </button>
                <div class="location-info" id="location-${sensor.id}" style="display:none;">
                    <span class="location-text">Recupero posizione...</span>
                </div>
            `;

            // Selezione card (solo sensori disponibili)
            if (sensor.status === 'disponibile') {
                card.addEventListener('click', () => toggleSensor(sensor.id, card));
            }

            // -----------------------------------------------------------
            // PULSANTE POSIZIONE IN TEMPO REALE
            // -----------------------------------------------------------
            const locationBtn = card.querySelector('.location-btn');
            let watchId = null;

            locationBtn.addEventListener('click', (e) => {
                e.stopPropagation(); // evita selezione/deselezione della card

                const locationDiv  = document.getElementById(`location-${sensor.id}`);
                const locationText = locationDiv.querySelector('.location-text');

                // Toggle: se già aperto, chiudi e stoppa il watch
                if (locationDiv.style.display === 'block') {
                    locationDiv.style.display = 'none';
                    locationBtn.textContent   = 'Rileva Posizione';
                    if (watchId !== null) {
                        navigator.geolocation.clearWatch(watchId);
                        watchId = null;
                    }
                    // Rimuovi la posizione salvata quando si chiude
                    delete posizioniSensori[sensor.id];
                    return;
                }

                if (!navigator.geolocation) {
                    locationText.textContent  = '❌ Geolocalizzazione non supportata dal browser.';
                    locationDiv.style.display = 'block';
                    return;
                }

                locationDiv.style.display = 'block';
                locationText.textContent  = 'Recupero posizione...';
                locationBtn.textContent   = 'Annulla Rilevamento';

                watchId = navigator.geolocation.watchPosition(
                    (position) => {
                        const { latitude, longitude, accuracy } = position.coords;

                        // Salva la posizione aggiornata per questo sensore
                        posizioniSensori[sensor.id] = { latitude, longitude, accuracy };

                        locationText.innerHTML = `
                            <a href="https://maps.google.com/?q=${latitude},${longitude}"
                               target="_blank"
                               style="font-size:12px; color: var(--primary, #4CAF50);">
                                Apri su Maps
                            </a>
                        `;
                    },
                    (error) => {
                        const errori = {
                            1: '❌ Permesso negato dall\'utente.',
                            2: '❌ Posizione non disponibile.',
                            3: '❌ Timeout nella richiesta.'
                        };
                        locationText.textContent = errori[error.code] || '❌ Errore sconosciuto.';
                        locationBtn.textContent  = 'Rileva Posizione';
                        watchId = null;
                    },
                    {
                        enableHighAccuracy: false,
                        timeout:            10000,
                        maximumAge:         60000
                    }
                );
            });

            sensorsGrid.appendChild(card);
        });
    }

    // ---------------------------------------------------------------
    // SELEZIONE SINGOLA CARD
    // ---------------------------------------------------------------
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

    // ---------------------------------------------------------------
    // AGGIORNA UI
    // ---------------------------------------------------------------
    function updateUI() {
        selectedCount.textContent = selectedSensors.size;
        startBtn.disabled = selectedSensors.size === 0;
    }

    // ---------------------------------------------------------------
    // SELEZIONA / DESELEZIONA TUTTI
    // ---------------------------------------------------------------
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

    document.getElementById('deselect-all').addEventListener('click', () => {
        selectedSensors.clear();
        document.querySelectorAll('.sensor-card').forEach(card => {
            card.classList.remove('selected');
        });
        updateUI();
    });

    // ---------------------------------------------------------------
    // VERIFICA SESSIONE
    // ---------------------------------------------------------------
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

    // ---------------------------------------------------------------
    // AVVIO IRRIGAZIONE
    // ---------------------------------------------------------------
    startBtn.addEventListener('click', async () => {
        if (selectedSensors.size === 0) return;

        // 1. Verifica sessione
        const sessionData = await verificaSessione();
        if (sessionData === "Go") {
            mostraPopup("Sessione di irrigazione già avviata");
            return;
        }

        // 2. Prepara dati
        const sensorsArray = Array.from(selectedSensors);
        const campoId = new URLSearchParams(window.location.search).get('campo_id');

        // 3. Associa posizione a ogni sensore — null se il pulsante 📍 non è stato cliccato
        const sensoriConPosizione = sensorsArray.map(nodeId => ({
            node_id:   nodeId,
            posizione: posizioniSensori[nodeId] || null
        }));

        console.log("Sensori con posizione:", sensoriConPosizione);

        // 4. Invia al server
        fetch('/ini_irr', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                campo_id:            campoId,
                selectedSensors:     sensorsArray,
                sensoriConPosizione: sensoriConPosizione
            })
        })
            .then(response => response.json())
            .then(data => {
                console.log("Risposta dal server:", data);

                if (data.status === "ok") {
                    window.location.href = `/avvia_irr?campo_id=${campoId}`;
                } else if (data.status === "no") {
                    mostraPopup("Sessione già avviata.");
                } else {
                    mostraPopup("Errore sconosciuto durante l'avvio dell'irrigazione.");
                }
            })
            .catch(err => {
                console.error(err);
                mostraPopup("Errore durante l'avvio dell'irrigazione. Riprova.");
            });
    });

    // ---------------------------------------------------------------
    // INIT
    // ---------------------------------------------------------------
    caricaSensori();

});