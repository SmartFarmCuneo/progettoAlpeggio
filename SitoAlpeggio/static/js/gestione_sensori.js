// Funzionalità JavaScript per la modifica del profilo
document.addEventListener("DOMContentLoaded", function () {
    const editBtn = document.getElementById("edit-btn");
    const cancelBtn = document.getElementById("cancel-btn");
    const successAlert = document.getElementById("success-alert");
    const profileForm = document.getElementById("profile-form");
    const actionInput = document.getElementById("action-salvataggio");
    const formInputs = document.querySelectorAll(
        '#profile-form input:not([type="hidden"]), #profile-form select'
    );
    const originalValues = {};

    // Salva i valori originali
    formInputs.forEach((input) => {
        originalValues[input.id] = input.value;
    });

    // Attiva modalità modifica
    editBtn.addEventListener("click", function () {
        if (editBtn.value === "Modifica") {
            editBtn.textContent = "Salva";
            editBtn.value = "Salva";
            editBtn.classList.add("save");
            cancelBtn.style.display = "inline-block";
            successAlert.style.display = "none";
        } else {
            // Salva le modifiche
            actionInput.value = "Salva"; // Imposta il valore per l'azione di salvataggio
            profileForm.submit(); // Invia il form
        }
    });

    // Annulla modifiche
    cancelBtn.addEventListener("click", function () {
        formInputs.forEach((input) => {
            input.value = originalValues[input.id]; // Ripristina valori originali
            input.readOnly = true;
            if (input.tagName === "SELECT") {
                input.disabled = true;
            }
        });

        editBtn.textContent = "Modifica";
        editBtn.classList.remove("save");
        cancelBtn.style.display = "none";
        successAlert.style.display = "none";
    });

    // Se c'è un parametro nell'URL che indica un salvataggio avvenuto, mostra il messaggio di successo
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.has("saved") && urlParams.get("saved") === "true") {
        successAlert.style.display = "block";
        setTimeout(() => {
            successAlert.style.display = "none";
        }, 3000);
    }
});