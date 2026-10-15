document.getElementById("registerForm").addEventListener("submit", function (e) {
    e.preventDefault();

    const t = window.i18n ? function (key) { return i18n.t(key); } : function (key) { return key; };
    const first_name = document.getElementById("first_name").value.trim();
    const last_name = document.getElementById("last_name").value.trim();
    const email = document.getElementById("email").value.trim();
    const mobile = document.getElementById("mobile").value.trim();
    const password = document.getElementById("password").value;
    const confirm_password = document.getElementById("confirm_password").value;
    const deptElem = document.getElementById("department_id");
    const department_id = deptElem ? deptElem.value : null;
    const msgDiv = document.getElementById("msg");
    const submitBtn = document.querySelector(".btn-register");

    if (password.length < 8 || !/[A-Z]/.test(password) || !/[a-z]/.test(password) || !/[0-9]/.test(password)) {
        msgDiv.innerHTML = '<div style="color:#f8d7da; text-align:center; margin-top:15px; padding:10px; background:rgba(248,118,117,0.1); border-radius:8px;">Password does not meet the requirements.</div>';
        const rules = document.getElementById("passwordRules");
        if (rules) rules.style.display = "block";
        return;
    }




    if (!first_name || !last_name || !email || !password) {
        msgDiv.innerHTML = '<div style="color:#f8d7da; text-align:center; margin-top:15px; padding:10px; background:rgba(248,118,117,0.1); border-radius:8px;">Please fill in all fields.</div>';
        return;
    }

    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(email)) {
        msgDiv.innerHTML = '<div style="color:#f8d7da; text-align:center; margin-top:15px; padding:10px; background:rgba(248,118,117,0.1); border-radius:8px;">Invalid email format.</div>';
        return;
    }

    if (password !== confirm_password) {
        msgDiv.innerHTML = '<div style="color:#f8d7da; text-align:center; margin-top:15px; padding:10px; background:rgba(248,118,117,0.1); border-radius:8px;">Passwords do not match.</div>';
        return;
    }

    submitBtn.disabled = true;
    submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> ' + t('creating_account');
    msgDiv.innerHTML = '';

    const payload = {
        first_name: first_name,
        last_name: last_name,
        email: email,
        mobile: mobile,
        password: password,
        confirm_password: confirm_password,
        department_id: department_id ? parseInt(department_id, 10) : null
    };

    fetch("/auth/register", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": document.querySelector('meta[name="csrf-token"]').getAttribute('content')
        },
        body: JSON.stringify(payload)
    })
        .then(response => response.json().then(data => ({ status: response.status, ok: response.ok, data })))
        .then(result => {
            if (result.ok) {
                msgDiv.innerHTML = '<div style="color:#d4edda; text-align:center; margin-top:15px; padding:15px; background:rgba(34,197,94,0.1); border-radius:8px;">Successfully registered your account. Please check your registered email id.</div>';
                document.getElementById("registerForm").style.display = "none";
                const loginLinkDom = document.querySelector(".login-link");
                if (loginLinkDom) loginLinkDom.style.display = "none";
            } else {
                msgDiv.innerHTML = '<div style="color:#f8d7da; text-align:center; margin-top:15px;">' + (result.data.message || t('registration_failed')) + '</div>';
            }
        })
        .catch(err => {
            console.error('Registration error:', err);
            msgDiv.innerHTML = '<div style="color:#f8d7da; text-align:center; margin-top:15px;">' + t('error_occurred') + '</div>';
        })
        .finally(() => {
            submitBtn.disabled = false;
            submitBtn.innerHTML = t('create_account');
        });
});

const pwdInput = document.getElementById("password");
const pwdRules = document.getElementById("passwordRules");
if (pwdInput && pwdRules) {
    pwdInput.addEventListener("focus", () => {
        pwdRules.style.display = "block";
    });
    pwdInput.addEventListener("input", (e) => {
        const val = e.target.value;
        document.getElementById("rule-length").style.color = val.length >= 8 ? "#4ade80" : "#60a5fa";
        document.getElementById("rule-upper").style.color = /[A-Z]/.test(val) ? "#4ade80" : "#60a5fa";
        document.getElementById("rule-lower").style.color = /[a-z]/.test(val) ? "#4ade80" : "#60a5fa";
        document.getElementById("rule-number").style.color = /[0-9]/.test(val) ? "#4ade80" : "#60a5fa";
    });
}

