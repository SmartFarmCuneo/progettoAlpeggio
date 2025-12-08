// Funzione per verificare lo stato della sessione e mostrare/nascondere il pulsante
    function verificaSessione() {
      fetch('/api/get_session_data')
        .then(response => response.json())
        .then(data => {
          console.log("Stato sessione:", data);
          
          const visualizzaIrrigazione = document.getElementById('visualizza-irrigazione');
          
          // Mostra il pulsante solo se la sessione ritorna "Stop" (irrigazione attiva)
          if (data === "Stop") {
            visualizzaIrrigazione.style.display = 'block';
          } else {
            visualizzaIrrigazione.style.display = 'none';
          }
        })
        .catch(error => {
          console.error("Errore nella verifica della sessione:", error);
          // In caso di errore, nascondi il pulsante per sicurezza
          document.getElementById('visualizza-irrigazione').style.display = 'none';
        });
    }

    // Verifica la sessione al caricamento della pagina
    document.addEventListener('DOMContentLoaded', verificaSessione);