// Day 3: Dashboard Analytics & Charts (Chart.js)

document.addEventListener("DOMContentLoaded", function () {
    const successRateEl = document.getElementById("successRateValue");
    const chartsSection = document.getElementById("chartsSection");
    const noDataSection = document.getElementById("noDataSection");
    const weeklyCanvas = document.getElementById("weeklyChart");
    const statusCanvas = document.getElementById("statusChart");

    // Fetch user-specific statistics from the secure API endpoint
    fetch("/api/stats")
        .then(function (response) {
            if (!response.ok) {
                throw new Error("Failed to fetch dashboard statistics.");
            }
            return response.json();
        })
        .then(function (data) {
            // 1. Update the Success Rate card
            if (successRateEl) {
                successRateEl.textContent = data.success_rate + "%";
            }

            // 2. If the user has zero applications, show friendly empty state
            if (data.total === 0) {
                if (chartsSection) chartsSection.classList.add("hidden");
                if (noDataSection) noDataSection.classList.remove("hidden");
                return;
            }

            // 3. Otherwise, reveal charts and render them
            if (chartsSection) chartsSection.classList.remove("hidden");
            if (noDataSection) noDataSection.classList.add("hidden");

            // Render Bar Chart: Applications per Week (Last 8 Weeks)
            if (weeklyCanvas) {
                new Chart(weeklyCanvas.getContext("2d"), {
                    type: "bar",
                    data: {
                        labels: data.weekly_labels,
                        datasets: [
                            {
                                label: "Applications",
                                data: data.weekly_counts,
                                backgroundColor: "rgba(37, 99, 235, 0.75)",
                                borderColor: "#2563eb",
                                borderWidth: 1,
                                borderRadius: 4,
                            },
                        ],
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: {
                                display: false,
                            },
                        },
                        scales: {
                            y: {
                                beginAtZero: true,
                                ticks: {
                                    stepSize: 1,
                                    precision: 0,
                                },
                            },
                        },
                    },
                });
            }

            // Render Doughnut Chart: Status Breakdown
            if (statusCanvas) {
                new Chart(statusCanvas.getContext("2d"), {
                    type: "doughnut",
                    data: {
                        labels: ["Applied", "Interview", "Offer", "Rejected"],
                        datasets: [
                            {
                                data: [
                                    data.status_counts.Applied || 0,
                                    data.status_counts.Interview || 0,
                                    data.status_counts.Offer || 0,
                                    data.status_counts.Rejected || 0,
                                ],
                                backgroundColor: [
                                    "#0284c7", // Sky blue for Applied
                                    "#f59e0b", // Amber for Interview
                                    "#10b981", // Emerald for Offer
                                    "#ef4444", // Rose for Rejected
                                ],
                                borderWidth: 2,
                                borderColor: "#ffffff",
                            },
                        ],
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: {
                                position: "bottom",
                                labels: {
                                    boxWidth: 14,
                                    padding: 16,
                                },
                            },
                        },
                    },
                });
            }
        })
        .catch(function (error) {
            console.error("Error loading dashboard stats:", error);
        });
});

