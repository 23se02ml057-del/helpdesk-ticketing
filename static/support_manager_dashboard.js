// ================================
// Dashboard Loaded
// ================================

document.addEventListener("DOMContentLoaded", function () {

    console.log("Support Manager Dashboard Loaded");

    // ===========================
    // Ticket Analytics Bar Chart
    // ===========================

    const ticketChart = document.getElementById("ticketChart");

    if (ticketChart) {

        new Chart(ticketChart, {

            type: "bar",

            data: {

                labels: [
                    "Mon",
                    "Tue",
                    "Wed",
                    "Thu",
                    "Fri",
                    "Sat",
                    "Sun"
                ],

                datasets: [

                    {

                        label: "Created",

                        data: [
                            18,
                            25,
                            14,
                            30,
                            26,
                            12,
                            20
                        ],

                        backgroundColor: "#0d6efd",

                        borderRadius: 8

                    },

                    {

                        label: "Resolved",

                        data: [
                            10,
                            18,
                            12,
                            25,
                            20,
                            8,
                            15
                        ],

                        backgroundColor: "#198754",

                        borderRadius: 8

                    }

                ]

            },

            options: {

                responsive: true,

                maintainAspectRatio: false,

                plugins: {

                    legend: {

                        position: "top"

                    }

                }

            }

        });

    }

    // ===========================
    // Priority Doughnut Chart
    // ===========================

    const priorityChart = document.getElementById("priorityChart");

    if (priorityChart) {

        new Chart(priorityChart, {

            type: "doughnut",

            data: {

                labels: [

                    "Low",
                    "Medium",
                    "High",
                    "Critical"

                ],

                datasets: [

                    {

                        data: [

                            35,
                            50,
                            40,
                            20

                        ],

                        backgroundColor: [

                            "#198754",
                            "#0dcaf0",
                            "#ffc107",
                            "#dc3545"

                        ]

                    }

                ]

            },

            options: {

                responsive: true,

                maintainAspectRatio: false,

                plugins: {

                    legend: {

                        position: "bottom"

                    }

                }

            }

        });

    }

    // ===========================
    // Weekly Trend Line Chart
    // ===========================

    const weeklyChart = document.getElementById("weeklyChart");

    if (weeklyChart) {

        new Chart(weeklyChart, {

            type: "line",

            data: {

                labels: [

                    "Mon",
                    "Tue",
                    "Wed",
                    "Thu",
                    "Fri",
                    "Sat",
                    "Sun"

                ],

                datasets: [

                    {

                        label: "Tickets",

                        data: [

                            12,
                            18,
                            15,
                            28,
                            22,
                            14,
                            17

                        ],

                        fill: false,

                        borderColor: "#0d6efd",

                        tension: 0.4

                    }

                ]

            },

            options: {

                responsive: true,

                maintainAspectRatio: false

            }

        });

    }

    // ===========================
    // Department Chart
    // ===========================

    const departmentChart = document.getElementById("departmentChart");

    if (departmentChart) {

        new Chart(departmentChart, {

            type: "pie",

            data: {

                labels: [

                    "IT",
                    "HR",
                    "Finance",
                    "Admin"

                ],

                datasets: [

                    {

                        data: [

                            60,
                            18,
                            12,
                            10

                        ],

                        backgroundColor: [

                            "#0d6efd",
                            "#198754",
                            "#ffc107",
                            "#dc3545"

                        ]

                    }

                ]

            },

            options: {

                responsive: true,

                maintainAspectRatio: false

            }

        });

    }

    // ===========================
    // Counter Animation
    // ===========================

    const counters = document.querySelectorAll(".counter");

    counters.forEach(counter => {

        const target = parseInt(counter.innerText);

        counter.innerText = 0;

        let count = 0;

        const speed = Math.max(10, target / 50);

        const updateCounter = () => {

            if (count < target) {

                count += speed;

                counter.innerText = Math.ceil(count);

                requestAnimationFrame(updateCounter);

            } else {

                counter.innerText = target;

            }

        };

        updateCounter();

    });

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

});