document.addEventListener('DOMContentLoaded', function() {
    const sidebar = document.getElementById('sidebar');
    const sidebarToggle = document.getElementById('sidebarToggle');
    const sidebarOverlay = document.getElementById('sidebarOverlay');

    if (sidebarToggle && sidebar) {
        sidebarToggle.addEventListener('click', function() {
            sidebar.classList.toggle('show');
            if (sidebarOverlay) {
                sidebarOverlay.classList.toggle('show');
            }
        });
    }

    if (sidebarOverlay) {
        sidebarOverlay.addEventListener('click', function() {
            sidebar.classList.remove('show');
            sidebarOverlay.classList.remove('show');
        });
    }

    // Close sidebar when clicking a link on mobile
    if (sidebar) {
        const sidebarLinks = sidebar.querySelectorAll('a');
        sidebarLinks.forEach(function(link) {
            link.addEventListener('click', function() {
                if (window.innerWidth < 992) {
                    sidebar.classList.remove('show');
                    if (sidebarOverlay) {
                        sidebarOverlay.classList.remove('show');
                    }
                }
            });
        });
    }

    // Handle window resize
    window.addEventListener('resize', function() {
        if (window.innerWidth >= 992) {
            if (sidebar) {
                sidebar.classList.remove('show');
            }
            if (sidebarOverlay) {
                sidebarOverlay.classList.remove('show');
            }
        }
    });
});