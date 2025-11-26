document.addEventListener("DOMContentLoaded", function () {
    const addSensorBtn = document.getElementById("add-sensor-btn");
    const modal = document.getElementById("addSensorModal");
    const closeModal = document.querySelector(".close");
    const cancelModalBtn = document.getElementById("cancel-modal-btn");
    const successAlert = document.getElementById("success-alert");
    const errorAlert = document.getElementById("error-alert");
    const addSensorForm = document.getElementById("add-sensor-form");

    // Apri modal
    addSensorBtn.addEventListener("click", function () {
        modal.style.display = "block";
    });

    // Chiudi modal con X
    closeModal.addEventListener("click", function () {
        modal.style.display = "none";
        addSensorForm.reset();
    });

    // Chiudi modal con pulsante Annulla
    cancelModalBtn.addEventListener("click", function () {
        modal.style.display = "none";
        addSensorForm.reset();
    });

    // Chiudi modal cliccando fuori
    window.addEventListener("click", function (event) {
        if (event.target === modal) {
            modal.style.display = "none";
            addSensorForm.reset();
        }
    });

    // Gestione messaggi di successo/errore dall'URL
    const urlParams = new URLSearchParams(window.location.search);

    if (urlParams.has("success")) {
        const successType = urlParams.get("success");
        let message = "Operazione completata con successo!";

        if (successType === "added") {
            message = "Sensore aggiunto con successo!";
        } else if (successType === "deleted") {
            message = "Sensore eliminato con successo!";
        }

        successAlert.textContent = message;
        successAlert.style.display = "block";

        setTimeout(() => {
            successAlert.style.display = "none";
        }, 3000);

        // Rimuovi il parametro dall'URL senza ricaricare la pagina
        window.history.replaceState({}, document.title, window.location.pathname);
    }

    if (urlParams.has("error")) {
        const errorType = urlParams.get("error");
        let message = "Si è verificato un errore. Riprova.";

        if (errorType === "duplicate") {
            message = "Errore: ID sensore già esistente!";
        } else if (errorType === "invalid") {
            message = "Errore: Dati non validi!";
        }

        errorAlert.textContent = message;
        errorAlert.style.display = "block";

        setTimeout(() => {
            errorAlert.style.display = "none";
        }, 4000);

        // Rimuovi il parametro dall'URL senza ricaricare la pagina
        window.history.replaceState({}, document.title, window.location.pathname);
    }

    // Validazione form prima dell'invio
    addSensorForm.addEventListener("submit", function (e) {
        const idSensore = document.getElementById("id_sensore").value.trim();
        const nomeSensore = document.getElementById("nome_sensore").value.trim();

        if (!idSensore || !nomeSensore) {
            e.preventDefault();
            errorAlert.textContent = "Tutti i campi sono obbligatori!";
            errorAlert.style.display = "block";

            setTimeout(() => {
                errorAlert.style.display = "none";
            }, 3000);
        }
    });
});