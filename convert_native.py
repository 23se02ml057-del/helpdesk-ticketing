import os
import re

roles = ["sa", "admin", "agent", "manager", "customer"]

for role in roles:
    filepath = f"c:/Users/kikan/OneDrive/Desktop/HELP_DESK&TICKET/templates/change_password_{role}.html"
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. Update <form id="changePasswordForm"> to <form id="changePasswordForm" method="POST" action="{{ url_for('auth.change_password') }}">
    content = re.sub(
        r'<form id="changePasswordForm">',
        r'<form id="changePasswordForm" method="POST" action="{{ url_for(\'auth.change_password\') }}">\n                        <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">',
        content
    )
    
    # 2. Update inputs to have name attributes!
    content = re.sub(r'id="currentPassword"', r'id="currentPassword" name="current_password"', content)
    content = re.sub(r'id="newPassword"', r'id="newPassword" name="new_password"', content)
    content = re.sub(r'id="confirmPassword"', r'id="confirmPassword" name="confirm_password"', content)
    
    # 3. Strip the javascript fetch logic
    # We want to keep checkPasswordRequirements and checkPasswordMatch,
    # but modify the submit event listener.
    js_submit_pattern = r'document\.getElementById\(\'changePasswordForm\'\)\.addEventListener\(\'submit\', async function\(e\) \{[\s\S]*?\}\);'
    
    new_submit_logic = """document.getElementById('changePasswordForm').addEventListener('submit', function(e) {
    if (!checkPasswordRequirements()) {
        e.preventDefault();
        i18n.alertT('password_requirements');
        return false;
    }
    if (!checkPasswordMatch()) {
        e.preventDefault();
        i18n.alertT('passwords_do_not_match');
        return false;
    }
    
    const submitBtn = this.querySelector('button[type="submit"]');
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin me-2"></i>' + i18n.t('changing');
});"""
    
    content = re.sub(js_submit_pattern, new_submit_logic, content)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
        
    print(f"Updated {filepath} to use native POST.")
