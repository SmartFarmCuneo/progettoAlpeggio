function closeNavbarMenu() {
    const navbarMenu = document.getElementById("navbarMenu");
    const hamburger = document.getElementById("hamburger");

    if (navbarMenu && hamburger) {
        navbarMenu.classList.remove("active");
        hamburger.classList.remove("active");
    }
}
document.addEventListener("DOMContentLoaded", () => {
    console.log("JS eseguito su:", window.location.pathname);

    closeNavbarMenu();

    const loginTitle = document.getElementById("login-title");
    const loginSection = document.getElementById("login-section");
    if (loginTitle && loginSection) {
        setTimeout(() => {
            loginTitle.classList.add("show");
            loginSection.classList.add("show");
        }, 600);
    }

    // Gestione toggle hamburger
    const hamburger = document.getElementById("hamburger");
    const navbarMenu = document.getElementById("navbarMenu");
    if (hamburger && navbarMenu) {
        hamburger.addEventListener("click", () => {
            navbarMenu.classList.toggle("active");
            hamburger.classList.toggle("active");
        });
    }

    // Chiude il menu quando si clicca su qualsiasi link
    document.querySelectorAll('a').forEach(link => {
        link.addEventListener("click", () => {
            closeNavbarMenu();
        });
    });
});
