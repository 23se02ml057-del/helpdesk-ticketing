async function loadDashboard() {

    let response = await fetch("/dashboard/stats");

    let data = await response.json();


    document.getElementById("total-users").innerText =
        data.total_users;

    document.getElementById("total-tickets").innerText =
        data.total_tickets;


    document.getElementById("open-tickets").innerText =
        data.open_tickets;


    document.getElementById("closed-tickets").innerText =
        data.closed_tickets;
}


loadDashboard();
