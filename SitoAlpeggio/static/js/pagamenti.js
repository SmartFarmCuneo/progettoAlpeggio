document.addEventListener("DOMContentLoaded", async function () {
  const plansContainer = document.getElementById("plans-container");
  const loadingOverlay = document.getElementById("loading-overlay");
  const stripePublicKey = document.getElementById("stripe-public-key").getAttribute("data-key");
  const stripe = Stripe(stripePublicKey);

  const showLoading = (show) => {
    loadingOverlay.style.display = show ? "flex" : "none";
  };

  try {
    // 🔹 Recupera piani + piano attuale
    // --> aggiunto credentials: 'same-origin' per essere sicuri che il cookie 'token' venga inviato
    const res = await fetch("/api/plans", { credentials: 'same-origin' });
    const data = await res.json();

    const plans = data.plans;
    const currentPlan = data.current_plan || "free";

    plansContainer.innerHTML = "";

    // 🔹 Ordine definito
    const planOrder = ["free", "basic", "professional", "enterprise"];

    // 🔹 Genera dinamicamente le card
    planOrder.forEach(planKey => {
      const plan = plans[planKey];
      if (!plan) return;

      // confronto case-insensitive e tolerance whitespace
      const isCurrent = planKey.toLowerCase() === (String(currentPlan).trim().toLowerCase());

      const card = document.createElement("div");
      card.className = `plan-card ${isCurrent ? "current" : ""}`;
      card.innerHTML = `
        <div class="plan-title">
          ${plan.name}
          ${isCurrent ? '<span class="plan-badge">Attuale ✅</span>' : ''}
        </div>
        <div class="plan-price"><span class="currency">€</span>${plan.price}</div>
        <div class="plan-period">al mese</div>
        <ul class="plan-features">
          ${plan.features.map(f => `<li>${f}</li>`).join("")}
        </ul>
        <button class="subscribe-btn ${isCurrent ? "secondary" : ""}"
          ${isCurrent
            ? 'onclick="selectCurrentPlan()"'
            : `onclick="selectPlan('${planKey}')"`}>
          ${isCurrent ? "Piano Attuale" : "Scegli " + plan.name}
        </button>
      `;
      plansContainer.appendChild(card);
    });
  } catch (err) {
    console.error("Errore nel caricamento dei piani:", err);
    plansContainer.innerHTML = "<p>Errore nel caricamento dei piani.</p>";
  }

  // 🔹 Piano già attivo
  window.selectCurrentPlan = function () {
    alert("Stai già utilizzando questo piano!");
  };

  // 🔹 Checkout Stripe
  window.selectPlan = async function (planId) {
    showLoading(true);
    try {
      const response = await fetch("/create-checkout-session", {
        method: "POST",
        credentials: 'same-origin',              // <-- anche qui invia cookie
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

  // 🔹 Portale clienti Stripe
  window.manageSubscription = async function () {
    showLoading(true);
    try {
      const res = await fetch("/create-customer-portal-session", { method: "POST", credentials: 'same-origin' });
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