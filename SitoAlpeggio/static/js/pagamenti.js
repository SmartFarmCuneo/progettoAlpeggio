document.addEventListener("DOMContentLoaded", async function () {
  const plansContainer = document.getElementById("plans-container");
  const loadingOverlay = document.getElementById("loading-overlay");
  const stripePublicKey = document.getElementById("stripe-public-key").getAttribute("data-key");
  const stripe = Stripe(stripePublicKey);

  // Funzione per mostrare loading
  const showLoading = (show) => {
    loadingOverlay.style.display = show ? "flex" : "none";
  };

  // Piano gratuito
  const freeCard = `
    <div class="plan-card current">
      <div class="plan-title">Free</div>
      <div class="plan-price"><span class="currency">€</span>0</div>
      <div class="plan-period">al mese</div>
      <ul class="plan-features">
        <li>Aggiunta fino a 10 campi</li>
        <li>Dati meteorologici base</li>
        <li>3 tipi di sensori</li>
        <li>Supporto email</li>
        <li>Report mensili</li>
      </ul>
      <button class="subscribe-btn secondary" onclick="selectFreePlan()">Piano Attuale</button>
    </div>
  `;

  try {
    // Recupera i piani dal backend
    const res = await fetch("/api/plans");
    const plans = await res.json();

    // Pulisci contenitore
    plansContainer.innerHTML = "";
    plansContainer.insertAdjacentHTML("beforeend", freeCard);

    // Crea dinamicamente i piani
    Object.entries(plans).forEach(([planId, plan]) => {
      const card = document.createElement("div");
      card.className = "plan-card";
      card.innerHTML = `
        <div class="plan-title">${plan.name}</div>
        <div class="plan-price"><span class="currency">€</span>${plan.price}</div>
        <div class="plan-period">al mese</div>
        <ul class="plan-features">
          ${plan.features.map(f => `<li>${f}</li>`).join("")}
        </ul>
        <button class="subscribe-btn" onclick="selectPlan('${planId}')">
          Scegli ${plan.name}
        </button>
      `;
      plansContainer.appendChild(card);
    });
  } catch (err) {
    console.error("Errore nel caricamento dei piani:", err);
    plansContainer.innerHTML = "<p>Errore nel caricamento dei piani.</p>";
  }

  // Funzione per piani a pagamento
  window.selectPlan = async function (planId) {
    showLoading(true);
    try {
      const response = await fetch("/create-checkout-session", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ plan_id: planId })
      });

      const data = await response.json();
      if (data.error) {
        alert("Errore: " + data.error);
      } else {
        window.location.href = data.checkout_url;
      }
    } catch (error) {
      console.error("Errore:", error);
      alert("Si è verificato un errore. Riprova più tardi.");
    } finally {
      showLoading(false);
    }
  };

  // Piano gratuito
  window.selectFreePlan = function () {
    alert("Stai già utilizzando il piano gratuito!");
  };

  // Portale clienti Stripe
  window.manageSubscription = async function () {
    showLoading(true);
    try {
      const res = await fetch("/create-customer-portal-session", { method: "POST" });
      const data = await res.json();
      if (data.url) window.location.href = data.url;
      else alert("Errore: " + (data.error || "Impossibile accedere al portale."));
    } catch (err) {
      console.error(err);
      alert("Errore durante l'apertura del portale clienti.");
    } finally {
      showLoading(false);
    }
  };
});
