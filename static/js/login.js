function login() {
    const email = document.getElementById('email').value.trim();
    const password = document.getElementById('password').value;
    const btn = document.querySelector('.btn-login');

    if (!email || !password) {
        alert(window.i18n ? i18n.t('email_and_password_required') : 'Please enter both email and password');
        return;
    }

    const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');

    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> ' + (window.i18n ? i18n.t('signing_in') : 'Signing in...');

    fetch('/auth/login', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken,
        },
        body: JSON.stringify({ email: email, password: password })
    })
    .then(response => response.json().then(data => ({ status: response.status, ok: response.ok, data })))
    .then(result => {
        if (result.ok && result.data.message === 'Login Success') {
            const roleId = result.data.role_id;
            let redirectUrl = '/login';

            if (roleId == 1) {
                redirectUrl = '/super-admin-dashboard';
            } else if (roleId == 2) {
                redirectUrl = '/support_manager/dashboard';
            } else if (roleId == 3) {
                redirectUrl = '/support_agent/dashboard';
            } else if (roleId == 5) {
                redirectUrl = '/admin/dashboard';
            } else if (roleId == 4 || roleId == 6) {
                redirectUrl = '/customer-dashboard';
            }

            window.location.href = redirectUrl;
        } else if (result.data.message && result.data.message.indexOf('verify your email') !== -1) {
            alert(result.data.message || (window.i18n ? i18n.t('please_verify_email') : 'Please verify your email before logging in'));
            window.location.href = '/resend-verification';
        } else {
            alert(result.data.message || (window.i18n ? i18n.t('login_failed') : 'Login failed'));
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert(window.i18n ? i18n.t('login_error') : 'An error occurred during login');
    })
    .finally(() => {
        btn.disabled = false;
        btn.innerHTML = window.i18n ? i18n.t('login') : 'Login';
    });
}
