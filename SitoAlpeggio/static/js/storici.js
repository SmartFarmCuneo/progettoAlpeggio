document.addEventListener("DOMContentLoaded", function () {
    const fieldSelect = document.getElementById("fieldSelect");
    const ricercaBtn = document.getElementById("ricerca");
    const formSection = document.getElementById("formSection");

    // Gestisce il click sul pulsante ricerca
    ricercaBtn.addEventListener("click", function () {
        if (fieldSelect.value) {
            formSection.classList.remove("d-none");
        } else {
            formSection.classList.add("d-none");
        }
    });

    // Funzione per caricare i campi tramite l'API
    function caricaCampi() {
        fetch("/api/campi-utente")
            .then((response) => response.json())
            .then((campi) => {
                console.log(campi);
                
                if (campi.length > 0) {
                    // Svuota la select prima di aggiungere nuove opzioni
                    fieldSelect.innerHTML = '<option value="">Scegli un campo...</option>';

                    // Aggiungi le opzioni per ogni campo ricevuto
                    campi.forEach((campo, i) => {
                        const option = document.createElement("option");
                        const nomeCampo = campo.nome || `Campo ${i + 1}`;
                        option.value = nomeCampo;
                        option.dataset.campoId = campo.id_t;
                        option.textContent = nomeCampo;
                        fieldSelect.appendChild(option);
                    });

                    // Se c'è un campo preselezionato dall'URL, selezionalo automaticamente
                    if (window.campoIdPreselezionato) {
                        preselezionaCampo(window.campoIdPreselezionato);
                    }
                }
            })
            .catch((error) => {
                console.error("Errore nel caricamento dei campi:", error);
                fieldSelect.innerHTML = '<option value="">Errore nel caricamento dei campi</option>';
            });
    }

    // Funzione per preselezionare un campo basato sull'ID
    function preselezionaCampo(campoId) {
        // Cerca l'option con il data-campo-id corrispondente
        const options = fieldSelect.querySelectorAll('option');
        
        for (let option of options) {
            if (option.dataset.campoId === campoId) {
                fieldSelect.value = option.value;
                // Mostra automaticamente la sezione con i risultati
                formSection.classList.remove("d-none");
                break;
            }
        }
    }

    caricaCampi();
});