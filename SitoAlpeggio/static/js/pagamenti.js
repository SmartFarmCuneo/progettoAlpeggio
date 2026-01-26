document.addEventListener("DOMContentLoaded", async function () {
  const plansContainer = document.getElementById("plans-container");
  const loadingOverlay = document.getElementById("loading-overlay");
  const manageContainer = document.getElementById("manage-subscription-container");
  const stripePublicKey = document.getElementById("stripe-public-key").getAttribute("data-key");
  const stripe = Stripe(stripePublicKey);

  const showLoading = (show) => {
    loadingOverlay.style.display = show ? "flex" : "none";
  };

  showLoading(true);

  try {
    const res = await fetch("/api/plans", { credentials: 'same-origin' });
    const data = await res.json();

    console.log("Risposta API /api/plans:", data); // DEBUG

    const plans = data.plans;
    const currentPlan = (data.current_plan || "free").toLowerCase();

    console.log("Piani ricevuti:", plans); // DEBUG
    console.log("Piano attuale:", currentPlan); // DEBUG

    if (currentPlan !== "free") {
      manageContainer.style.display = "block";
    }

    plansContainer.innerHTML = "";
    const sortedPlanKeys = Object.keys(plans).sort((a, b) => plans[a].price - plans[b].price);

    console.log("Piani ordinati:", sortedPlanKeys); // DEBUG

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

    showLoading(false);

  } catch (err) {
    console.error("Errore nel caricamento dei piani:", err); // DEBUG
    plansContainer.innerHTML = "<p>Errore nel caricamento dei piani.</p>";
    showLoading(false);
  }

  window.selectCurrentPlan = function () {
    alert("Stai già utilizzando questo piano! Se vuoi cambiare, usa il Portale Clienti.");
  };

  window.selectPlan = async function (planKey) {
    showLoading(true);

    // Se sceglie Free, cancella prima l'abbonamento attivo
    if (planKey === 'free') {
      try {
        const response = await fetch("/subscribe-free", {
          method: "POST",
          credentials: 'same-origin',
          headers: { "Content-Type": "application/json" }
        });
        const data = await response.json();
        if (data.success) {
          alert("Sei passato al piano Free. L'abbonamento è stato cancellato.");
          window.location.href = "/pagamenti?success=true";
        } else {
          alert("Errore: " + data.error);
          showLoading(false);
        }
      } catch (error) {
        console.error("Errore cambio piano free:", error);
        alert("Si è verificato un errore tecnico.");
        showLoading(false);
      }
      return;
    }

    // Per i piani a pagamento, usa Stripe
    try {
      const response = await fetch("/create-checkout-session", {
        method: "POST",
        credentials: 'same-origin',
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ plan: planKey })
      });

      const data = await response.json();

      if (data.error) {
        alert("Errore: " + data.error);
        showLoading(false);
      } else {
        const result = await stripe.redirectToCheckout({
          sessionId: data.sessionId
        });
        if (result.error) {
          alert(result.error.message);
          showLoading(false);
        }
      }
    } catch (error) {
      console.error("Errore selectPlan:", error);
      alert("Si è verificato un errore tecnico.");
      showLoading(false);
    }
  };

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