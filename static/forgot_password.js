console.log("forgot_password.js loaded");

document.addEventListener("DOMContentLoaded", function () {

    const form = document.getElementById("forgotForm");

    if (!form) {
        console.error("forgotForm not found!");
        return;
    }

    const t = window.i18n ? function(key) { return i18n.t(key); } : function(key) { return key; };

    form.addEventListener("submit", async function (e) {

        e.preventDefault();

        const email = document.getElementById("email").value;

        try {

            const response = await fetch(
                "/auth/forgot-password",
                {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json"
                    },
                    body: JSON.stringify({
                        email: email
                    })
                }
            );

            const data = await response.json();

            const msg = document.getElementById("msg");

            if (msg) {
                msg.innerText = data.message;
            }

            console.log("Response:", data);

        } catch (error) {

            console.error("Error:", error);

            const msg = document.getElementById("msg");

            if (msg) {
                msg.innerText = t("something_went_wrong");
            }

        }

    });

});
