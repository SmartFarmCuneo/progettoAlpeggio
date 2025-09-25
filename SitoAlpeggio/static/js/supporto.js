const faqItems = document.querySelectorAll(".faq-question");

faqItems.forEach((btn) => {
    btn.addEventListener("click", () => {
        const answer = btn.nextElementSibling;
        const arrow = btn.querySelector(".arrow");

        // Chiudi eventuali risposte aperte
        document.querySelectorAll(".faq-answer").forEach((ans) => {
            if (ans !== answer) ans.style.maxHeight = null;
        });

        document.querySelectorAll(".arrow").forEach((arr) => {
            if (arr !== arrow) arr.classList.remove("open");
        });

        // Alterna apertura/chiusura
        if (answer.style.maxHeight) {
            answer.style.maxHeight = null;
            arrow.classList.remove("open");
        } else {
            answer.style.maxHeight = answer.scrollHeight + "px";
            arrow.classList.add("open");
        }
    });
});