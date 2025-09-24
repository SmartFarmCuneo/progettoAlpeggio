function selectPlan(planType) {
    // Mostra conferma
    const planNames = {
        basic: "Basic (€19/mese)",
        professional: "Professional (€49/mese)",
        enterprise: "Enterprise (€99/mese)",
    };

    const confirmed = confirm(
        `Confermi la selezione del piano ${planNames[planType]}?`
    );

    if (confirmed) {
        // Simula reindirizzamento al checkout
        alert(
            `Reindirizzamento al checkout per il piano ${planNames[planType]}...`
        );

        // Qui normalmente avresti:
        // window.location.href = `/checkout?plan=${planType}`;
    }
}

// Animazioni all'entrata
document.addEventListener("DOMContentLoaded", function () {
    const cards = document.querySelectorAll(".plan-card");
    const billingInfos = document.querySelectorAll(".billing-info");

    // Animazioni per le cards (già gestite via CSS con animation-delay)

    // Animazioni per le billing info
    billingInfos.forEach((info, index) => {
        info.style.opacity = "0";
        info.style.transform = "translateY(30px)";

        setTimeout(() => {
            info.style.transition = "all 0.8s ease";
            info.style.opacity = "1";
            info.style.transform = "translateY(0)";
        }, 800 + index * 200);
    });
});