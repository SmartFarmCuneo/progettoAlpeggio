document.addEventListener("DOMContentLoaded", function () {
  // Elementi del DOM
  const fieldSelect = document.getElementById("fieldSelect");
  const searchButton = document.getElementById("searchButton");
  const detailForm = document.getElementById("detailForm");
  const campoSelezionato = document.getElementById("campoSelezionato");
  const campoNome = document.getElementById("campoNome");
  const deleteButton = document.getElementById("deleteButton");
  const loadingSpinner = document.getElementById("loadingSpinner");

  // Dati del campo attualmente caricato
  let currentFieldData = null;

  // Funzione per ottenere parametri URL
  function getUrlParameter(name) {
    const urlParams = new URLSearchParams(window.location.search);
    return urlParams.get(name);
  }

  // Funzione per mostrare/nascondere loading
  function toggleLoading(show) {
    if (show) {
      loadingSpinner.style.display = "inline-block";
      searchButton.classList.add("loading");
    } else {
      loadingSpinner.style.display = "none";
      searchButton.classList.remove("loading");
    }
  }

  // Variabili per i dati del campo dalla sessione/database
  let sessionProvincia = "";
  let sessionComune = "";
  let sessionCap = "";
  let sessionBestiame = 0;

  // Funzione per caricare i dati del campo selezionato
  async function caricaDatiCampo(fieldId) {
    try {
      toggleLoading(true);

      // Chiamata API per ottenere i dati del campo
      const response = await fetch(`/api/campo/${fieldId}`);
      if (!response.ok) {
        throw new Error("Errore nel caricamento dei dati del campo");
      }

      const fieldData = await response.json();
      currentFieldData = fieldData;

      // Salva i dati del campo nelle variabili di sessione
      sessionProvincia = fieldData.provincia || "";
      sessionComune = fieldData.comune || "";
      sessionCap = fieldData.CAP || "";
      sessionBestiame = fieldData.num_bestiame || 0;

      // Popola il campo bestiame
      document.getElementById("livestockCount").value = sessionBestiame;

      // Carica le province con i dati del campo
      await populateProvince();

      // Mostra il form e imposta il nome del campo
      campoSelezionato.value = fieldId;
      campoNome.textContent = fieldSelect.options[fieldSelect.selectedIndex].text;
      detailForm.style.display = "block";

      // Scroll verso il form
      detailForm.scrollIntoView({ behavior: "smooth" });

    } catch (error) {
      console.error("Errore nel caricamento dei dati:", error);
      alert("Errore nel caricamento dei dati del campo. Riprova.");
    } finally {
      toggleLoading(false);
    }
  }

  // Event listener per il form di ricerca
  searchButton.addEventListener("click", function (e) {
    e.preventDefault();

    if (!fieldSelect.value) {
      alert("Seleziona un campo prima di proseguire.");
      return;
    }

    caricaDatiCampo(fieldSelect.value);
  });

  // Event listener per il pulsante elimina
  deleteButton.addEventListener("click", function () {
    if (confirm("Sei sicuro di voler eliminare questo campo? Questa azione non può essere annullata.")) {
      const form = document.getElementById("detailForm");
      const actionInput = document.createElement("input");
      actionInput.type = "hidden";
      actionInput.name = "action";
      actionInput.value = "delete";
      form.appendChild(actionInput);
      form.submit();
    }
  });

  // Funzione per caricare i campi dell'utente
  async function caricaCampi() {
    try {
      const response = await fetch("/api/campi-utente");
      if (!response.ok) {
        throw new Error("Errore nel caricamento dei campi");
      }

      const campi = await response.json();

      // Svuota la select
      fieldSelect.innerHTML = '<option value="">Scegli un campo...</option>';

      // Aggiungi i campi
      campi.forEach((campo, index) => {
        const option = document.createElement("option");
        option.value = campo.id_t;
        option.textContent = `Campo ${index + 1} - ${campo.comune}`;
        fieldSelect.appendChild(option);
      });

      // Controlla se c'è un parametro URL per preselezionare un campo
      const campoIdFromUrl = getUrlParameter('campo_id');
      if (campoIdFromUrl) {
        // Trova e seleziona il campo corrispondente
        const optionToSelect = Array.from(fieldSelect.options).find(
          option => option.value === campoIdFromUrl
        );
        
        if (optionToSelect) {
          fieldSelect.value = campoIdFromUrl;
          // Carica automaticamente i dati del campo
          await caricaDatiCampo(campoIdFromUrl);
        }
      }

    } catch (error) {
      console.error("Errore nel caricamento dei campi:", error);
      fieldSelect.innerHTML = '<option value="">Errore nel caricamento dei campi</option>';
    }
  }

  // Funzione per caricare le province con logica della sessione
  async function populateProvince() {
    try {
      const response = await fetch("/api/get_provincia");
      const data = await response.json();

      const selectProvincia = document.getElementById("select_provincia");
      selectProvincia.innerHTML = '<option value="">Scegli...</option>';

      if (data.province && Array.isArray(data.province)) {
        data.province.forEach((provincia) => {
          const option = document.createElement("option");
          option.value = provincia.sigla_provincia;
          option.textContent = provincia.denominazione_provincia;

          // Seleziona la provincia se corrisponde a quella del campo
          if (provincia.sigla_provincia === sessionProvincia) {
            option.selected = true;
          }

          selectProvincia.appendChild(option);
        });
      }

      // Se c'è una provincia salvata, carica i relativi comuni
      if (sessionProvincia) {
        await populateComuni(sessionProvincia);
      }
    } catch (error) {
      console.error("Errore nel caricamento delle province:", error);
    }
  }

  // Funzione per caricare i comuni con logica della sessione
  async function populateComuni(provinciaSelezionata) {
    try {
      const selectComune = document.getElementById("select_comune");
      selectComune.innerHTML = '<option value="">Scegli...</option>';

      if (!provinciaSelezionata) return;

      const response = await fetch(`/api/get_comune?provincia=${provinciaSelezionata}`);
      const data = await response.json();

      if (data.comuni && Array.isArray(data.comuni)) {
        data.comuni.forEach((comune) => {
          const option = document.createElement("option");
          option.value = comune.denominazione_ita;
          option.textContent = comune.denominazione_ita;

          // Seleziona il comune se corrisponde a quello del campo
          if (comune.denominazione_ita === sessionComune) {
            option.selected = true;
          }

          selectComune.appendChild(option);
        });
      }

      // Imposta il CAP del campo
      document.getElementById("zip").value = sessionCap || "";

    } catch (error) {
      console.error("Errore nel caricamento dei comuni:", error);
    }
  }

  // Event listener per cambio provincia
  document.getElementById("select_provincia").addEventListener("change", function () {
    const provinciaSelezionata = this.value;

    // Reset dei valori di comune e CAP quando cambia la provincia
    sessionComune = "";
    sessionCap = "";

    if (provinciaSelezionata) {
      populateComuni(provinciaSelezionata);
    } else {
      document.getElementById("select_comune").innerHTML = '<option value="">Scegli...</option>';
      document.getElementById("zip").value = "";
    }
  });

  // Funzione per resettare il form
  window.resetForm = function () {
    if (currentFieldData) {
      document.getElementById("zip").value = currentFieldData.CAP || "";
      // Ripristina provincia e comune se necessario
    }
  };

  // Validazione del form
  const forms = document.querySelectorAll(".needs-validation");
  Array.from(forms).forEach(function (form) {
    form.addEventListener("submit", function (event) {
      if (!form.checkValidity()) {
        event.preventDefault();
        event.stopPropagation();
      }
      form.classList.add("was-validated");
    }, false);
  });

  // Carica i campi all'avvio della pagina
  caricaCampi();
});