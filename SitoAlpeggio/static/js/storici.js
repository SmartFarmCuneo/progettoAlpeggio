document.addEventListener("DOMContentLoaded", function () {
    const fieldSelect = document.getElementById("ricerca");
    const formSection = document.getElementById("formSection");

    fieldSelect.addEventListener("click", function () {
        if (this.value) {
            formSection.classList.remove("d-none"); // Mostra il form se viene selezionato un campo
        } else {
            formSection.classList.add("d-none"); // Nascondi il form se non c'è nulla selezionato
        }
    });
});

document.addEventListener("DOMContentLoaded", function () {
    const fieldSelect = document.getElementById("fieldSelect");

    // Funzione per caricare i campi tramite l'API
    function caricaCampi() {
        fetch("/api/numCampi")
            .then((response) => response.json()) // Supponiamo che la risposta sia un numero intero
            .then((numCampi) => {
                console.log(numCampi); // Mostra il numero ricevuto
                if (numCampi > 0) {
                    // Svuota la select prima di aggiungere nuove opzioni
                    fieldSelect.innerHTML =
                        '<option value="">Scegli un campo...</option>';

                    // Aggiungi le opzioni ai campi ricevuti
                    for (let i = 0; i < numCampi; i++) {
                        const option = document.createElement("option");
                        option.value = "campo" + (i + 1); // Aggiungi un campo con un numero
                        option.textContent = "Campo " + (i + 1);
                        fieldSelect.appendChild(option);
                    }
                }
            })
            .catch((error) => {
                console.error("Errore nel caricamento dei campi:", error);
                fieldSelect.innerHTML =
                    '<option value="">Errore nel caricamento dei campi</option>';
            });
    }

    caricaCampi(); // Carica i campi all'avvio della pagina
});