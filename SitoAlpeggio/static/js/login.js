// animazione semplice per mostrare titolo e form
window.addEventListener("load", function () {
    setTimeout(function () {
        document.getElementById("login-title").classList.add("show");
        document.getElementById("login-section").classList.add("show");
    }, 600);
});

// Smooth scrolling
document.querySelectorAll('a[href^="#"]').forEach((anchor) => {
    anchor.addEventListener("click", function (e) {
        e.preventDefault();
        const target = document.querySelector(this.getAttribute("href"));
        if (target) {
            target.scrollIntoView({ behavior: "smooth" });
        }
        // Chiudi il menu dopo il click su mobile
        document.getElementById("navbarMenu").classList.remove("active");
    });
});

const hamburger = document.getElementById("hamburger");
const navbarMenu = document.getElementById("navbarMenu");

// Toggle apertura/chiusura del menu
hamburger.addEventListener("click", () => {
    navbarMenu.classList.toggle("active");
    hamburger.classList.toggle("active");
});

// Smooth scrolling + chiusura menu al click su link
document.querySelectorAll('.nav-links a, .mobile-auth a').forEach((link) => {
    link.addEventListener("click", function (e) {
        // Smooth scroll (solo se link interno)
        if (this.getAttribute("href").startsWith("#")) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute("href"));
            if (target) {
                target.scrollIntoView({ behavior: "smooth" });
            }
        }

        // Chiudi menu dopo il click (mobile)
        navbarMenu.classList.remove("active");
        hamburger.classList.remove("active");
    });
});