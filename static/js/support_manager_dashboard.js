// ================================
// Support Manager Dashboard
// ================================

document.addEventListener("DOMContentLoaded", function () {

    console.log("Support Manager Dashboard Loaded");

    // ===========================
    // Card Hover Effect
    // ===========================

    document.querySelectorAll(".card").forEach(card => {

        card.addEventListener("mouseenter", () => {
            card.style.transform = "translateY(-5px)";
            card.style.transition = ".3s";
        });

        card.addEventListener("mouseleave", () => {
            card.style.transform = "translateY(0px)";
        });

    });

    // ===========================
    // Sidebar Toggle (Mobile)
    // ===========================

    const sidebar = document.getElementById("sidebar");
    const sidebarToggle = document.getElementById("sidebarToggle");
    const sidebarOverlay = document.getElementById("sidebarOverlay");

    if (sidebarToggle) {
        sidebarToggle.addEventListener("click", function () {
            sidebar.classList.toggle("show");
            sidebarOverlay.classList.toggle("show");
        });
    }

    if (sidebarOverlay) {
        sidebarOverlay.addEventListener("click", function () {
            sidebar.classList.remove("show");
            sidebarOverlay.classList.remove("show");
        });
    }

});
