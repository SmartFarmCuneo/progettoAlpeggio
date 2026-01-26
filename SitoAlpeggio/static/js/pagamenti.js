document.addEventListener("DOMContentLoaded", async function () {
  const plansContainer = document.getElementById("plans-container");
  const loadingOverlay = document.getElementById("loading-overlay");
  const manageContainer = document.getElementById("manage-subscription-container");
  const stripePublicKey = document.getElementById("stripe-public-key").getAttribute("data-key");
  const stripe = Stripe(stripePublicKey);

  const showLoading = (show) => {
    loadingOverlay.style.display = show ? "flex" : "none";
  };

  try {
    const res = await fetch("/api/plans", { credentials: 'same-origin' });
    const data = await res.json();

    const plans = data.plans;
    const currentPlan = (data.current_plan || "free").toLowerCase();

    // Mostra il tasto gestione se non è free
    if (currentPlan !== "free") {
        manageContainer.style.display = "block";
    }

    plansContainer.innerHTML = "";

    // Ordiniamo i piani per prezzo (più affidabile dell'ordine manuale se i nomi cambiano)
    const sortedPlanKeys = Object.keys(plans).sort((a, b) => plans[a].price - plans[b].price);

    sortedPlanKeys.forEach(planKey => {
      const plan = plans[planKey];
      const isCurrent = planKey.toLowerCase() === currentPlan;

      const card = document.createElement("div");
      card.className = `plan-card ${isCurrent ? "current" : ""}`;
      card.innerHTML = `
        <div class="plan-title">
          ${plan.name}
          ${isCurrent ? '<span class="plan-badge">Attuale ✅</span>' : ''}
        </div>
        <div class="plan-price">
            <span class="currency">${plan.currency === 'eur' ? '€' : plan.currency}</span>${plan.price}
        </div>
        <div class="plan-period">${plan.interval === 'month' ? 'al mese' : 'all\'anno'}</div>
        <ul class="plan-features">
          ${plan.features.map(f => `<li>${f}</li>`).join("")}
        </ul>
        <button class="subscribe-btn ${isCurrent ? "secondary" : ""}"
          onclick="${isCurrent ? "selectCurrentPlan()" : `selectPlan('${planKey}')`}">
          ${isCurrent ? "Piano Attuale" : "Scegli " + plan.name}
        </button>
      `;
      plansContainer.appendChild(card);
    });
  } catch (err) {
    console.error("Errore nel caricamento dei piani:", err);
    plansContainer.innerHTML = "<p>Errore nel caricamento dei piani.</p>";
  }

  window.selectCurrentPlan = function () {
    alert("Stai già utilizzando questo piano! Se vuoi cambiare, usa il Portale Clienti.");
  };

  // --- FIX CHECKOUT ---
  window.selectPlan = async function (planKey) {
    showLoading(true);
    try {
      const response = await fetch("/create-checkout-session", {
        method: "POST",
        credentials: 'same-origin',
        headers: { "Content-Type": "application/json" },
        // Cambiato da plan_id a plan per matchare il tuo Python
        body: JSON.stringify({ plan: planKey }) 
      });

      const data = await response.json();
      
      if (data.error) {
        alert("Errore: " + data.error);
        showLoading(false);
      } else {
        // Stripe Checkout con sessionId
        const result = await stripe.redirectToCheckout({
          sessionId: data.sessionId
        });
        if (result.error) {
          alert(result.error.message);
          showLoading(false);
        }
      }
    } catch (error) {
      console.error("Erro manageSubscription:", error);
      alert("Si è verificato un errore tecnico.");
      showLoading(false);
    }
  };

  // --- FIX CUSTOMER PORTAL ---
  window.manageSubscription = async function () {
    showLoading(true);
    try {
      const res = await fetch("/create-customer-portal-session", { 
        method: "POST", 
        credentials: 'same-origin' 
      });
      const data = await res.json();
      if (data.url) {
        window.location.href = data.url;
      } else {
        alert("Errore: " + (data.error || "Impossibile accedere al portale."));
        showLoading(false);
      }
    } catch (err) {
      console.error(err);
      alert("Errore durante l'apertura del portale clienti.");
      showLoading(false);
    }
  };
});