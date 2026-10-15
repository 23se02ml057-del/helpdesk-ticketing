function register() {
    const form = document.getElementById('registerForm');
    const btn = form.querySelector('.btn-register');

    const first_name = document.getElementById('first_name').value.trim();
    const last_name = document.getElementById('last_name').value.trim();
    const email = document.getElementById('email').value.trim();
    const mobile = document.getElementById('mobile').value.trim();
    const password = document.getElementById('password').value;
    const confirm_password = document.getElementById('confirm_password').value;
    const department_id = 6;

    if (!first_name || !last_name || !email || !password) {
        alert(window.i18n ? i18n.t('all_fields_required') : 'Please fill in all required fields');
        return;
    }

    if (password !== confirm_password) {
        alert(window.i18n ? i18n.t('passwords_do_not_match') : 'Passwords do not match');
        return;
    }

    const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');

    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> ' + (window.i18n ? i18n.t('creating_account') : 'Creating account...');

    fetch('/auth/register', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken,
        },
        body: JSON.stringify({
            first_name: first_name,
            last_name: last_name,
            email: email,
            mobile: mobile,
            password: password,
            confirm_password: confirm_password,
            department_id: 6
        })
    })
    .then(response => response.json().then(data => ({ status: response.status, ok: response.ok, data })))
    .then(result => {
        if (result.ok || result.data.success) {
            alert(window.i18n ? i18n.t('registration_success') : 'Registration successful! Please login.');
            window.location.href = '/login';
        } else if (result.data.message && result.data.message.indexOf('already registered but not verified') !== -1) {
            alert(result.data.message || (window.i18n ? i18n.t('email_already_registered') : 'Email already registered'));
            window.location.href = '/resend-verification';
        } else {
            alert(result.data.message || (window.i18n ? i18n.t('registration_failed') : 'Registration failed'));
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert(window.i18n ? i18n.t('registration_error') : 'An error occurred during registration');
    })
    .finally(() => {
        btn.disabled = false;
        btn.innerHTML = window.i18n ? i18n.t('create_account') : 'Create Account';
    });
}

document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('registerForm');
    if (form) {
        form.addEventListener('submit', function(e) {
            e.preventDefault();
            register();
        });
    }
});
