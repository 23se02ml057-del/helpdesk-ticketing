import os
import re

html_to_inject = """
                        <div class="password-requirements bg-light p-3 rounded mt-2 border">
                            <h6 class="text-muted small fw-bold mb-2">{{ _('Password Must Contain') }}</h6>
                            <div class="requirement d-flex align-items-center gap-2 mb-1 not-met" id="req-length">
                                <i class="fa-solid fa-circle" style="font-size:8px;"></i>
                                <span class="small text-secondary">{{ _('Req At Least 8') }}</span>
                            </div>
                            <div class="requirement d-flex align-items-center gap-2 mb-1 not-met" id="req-upper">
                                <i class="fa-solid fa-circle" style="font-size:8px;"></i>
                                <span class="small text-secondary">{{ _('Req One Uppercase Az') }}</span>
                            </div>
                            <div class="requirement d-flex align-items-center gap-2 mb-1 not-met" id="req-lower">
                                <i class="fa-solid fa-circle" style="font-size:8px;"></i>
                                <span class="small text-secondary">{{ _('Req One Lowercase Az') }}</span>
                            </div>
                            <div class="requirement d-flex align-items-center gap-2 mb-1 not-met" id="req-number">
                                <i class="fa-solid fa-circle" style="font-size:8px;"></i>
                                <span class="small text-secondary">{{ _('Req One Number 09') }}</span>
                            </div>
                        </div>
                        <small id="matchMessage" style="color:#ef4444;display:none;margin-top:5px;">{{ _('Passwords Do Not Match') }}</small>
"""

js_to_inject = """
function updateRequirement(id, met) {
    const element = document.getElementById(id);
    if(!element) return;
    const icon = element.querySelector('i');
    if (met) {
        element.classList.remove('not-met');
        element.classList.add('met');
        icon.classList.remove('text-secondary', 'fa-circle');
        icon.classList.add('text-success', 'fa-check-circle');
    } else {
        element.classList.remove('met');
        element.classList.add('not-met');
        icon.classList.remove('text-success', 'fa-check-circle');
        icon.classList.add('text-secondary', 'fa-circle');
    }
}

function checkPasswordRequirements() {
    const password = document.getElementById('newPassword').value;
    const hasLength = password.length >= 8;
    const hasUpper = /[A-Z]/.test(password);
    const hasLower = /[a-z]/.test(password);
    const hasNumber = /[0-9]/.test(password);
    
    updateRequirement('req-length', hasLength);
    updateRequirement('req-upper', hasUpper);
    updateRequirement('req-lower', hasLower);
    updateRequirement('req-number', hasNumber);
    
    return hasLength && hasUpper && hasLower && hasNumber;
}

function checkPasswordMatch() {
    const password = document.getElementById('newPassword').value;
    const confirm = document.getElementById('confirmPassword').value;
    const matchMessage = document.getElementById('matchMessage');
    if(matchMessage) {
        if (confirm && password !== confirm) {
            matchMessage.style.display = 'block';
            return false;
        } else {
            matchMessage.style.display = 'none';
            return true;
        }
    }
    return password === confirm;
}

document.getElementById('newPassword').addEventListener('input', function() {
    checkPasswordRequirements();
    if (document.getElementById('confirmPassword').value) {
        checkPasswordMatch();
    }
});

document.getElementById('confirmPassword').addEventListener('input', checkPasswordMatch);
"""

roles = ["sa", "admin", "agent", "manager", "customer"]

for role in roles:
    filepath = f"c:/Users/kikan/OneDrive/Desktop/HELP_DESK&TICKET/templates/change_password_{role}.html"
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Inject HTML
    # We want to insert it right before the confirm password div or right after new password input.
    # Find <input type="password" id="newPassword"...></div>
    
    new_html_content = re.sub(
        r'(<input type="password" id="newPassword".*?>\s*)(</div>)?',
        r'\1\n' + html_to_inject + r'\2',
        content
    )
    
    # Inject JS
    # Replace the existing checkPasswordRequirements
    new_js_content = re.sub(
        r'function checkPasswordRequirements\(\) \{.*?\n\}',
        js_to_inject,
        new_html_content,
        flags=re.DOTALL
    )
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(new_js_content)
        
    print(f"Updated {filepath}")
