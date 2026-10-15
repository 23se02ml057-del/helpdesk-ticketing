import sys, glob, re, ast
sys.path.insert(0, 'C:\\Users\\kikan\\OneDrive\\Desktop\\HELP_DESK&TICKET')

print("=" * 60)
print("FINAL COMPREHENSIVE VERIFICATION")
print("=" * 60)

# 1. Python compile
print("\n--- 1. Python Compile ---")
py_files = [f for f in glob.glob('**/*.py', recursive=True) if 'venv' not in f and '__pycache__' not in f and 'generate_translations' not in f]
fails = 0
for f in sorted(py_files):
    try:
        with open(f, encoding='utf-8', errors='ignore') as fh:
            ast.parse(fh.read())
    except SyntaxError:
        print(f"  FAIL {f}")
        fails += 1
print(f"  {len(py_files) - fails}/{len(py_files)} files compile OK")

# 2. Template inline style check for key templates
print("\n--- 2. Template Inline Styles ---")
key_templates = ['admin_skills.html', 'skills.html', 'categories.html', 'customers.html', 'tickets.html', 'ticket_assignment.html']
for name in key_templates:
    path = f'templates/{name}'
    with open(path, encoding='utf-8') as fh:
        content = fh.read()
    has_style = 'style=' in content
    status = "FAIL" if has_style else "PASS"
    print(f"  {status} {name} (inline styles: {has_style})")

# 3. Key template blocks
print("\n--- 3. Template Structure ---")
checks = [
    ('admin_skills.html', 'layout_admin.html'),
    ('categories.html', 'layout.html'),
    ('skills.html', 'layout.html'),
    ('customers.html', 'layout.html'),
    ('tickets.html', 'layout.html'),
    ('ticket_assignment.html', 'layout.html'),
]
for tpl, expected_ext in checks:
    with open(f'templates/{tpl}', encoding='utf-8') as fh:
        content = fh.read()
    ok = expected_ext in content
    status = "PASS" if ok else "FAIL"
    print(f"  {status} {tpl} extends {expected_ext}")

# 4. Admin skills specific checks
print("\n--- 4. Admin Skills Template ---")
with open('templates/admin_skills.html', encoding='utf-8') as fh:
    content = fh.read()
skills_checks = [
    ("7 column headers", len(re.findall(r'<th class="th-', content)) == 7),
    ("7 cells per row", len(re.findall(r'<td', re.search(r'<tr data-skill-name.*?</tr>', content, re.DOTALL).group())) == 7),
    ("Has stats-row", 'stats-row' in content),
    ("Has filter-card", 'filter-card' in content),
    ("Has result-bar", 'result-bar' in content),
    ("Has delete modal", 'deleteSkillModal' in content),
    ("Has applySkillFilters", 'applySkillFilters' in content),
    ("Has debounce", 'DEBOUNCE_MS' in content),
    ("Has status filter", 'skill-status-filter' in content),
    ("Has category filter", 'skill-category-filter' in content),
    ("Has department filter", 'skill-department-filter' in content),
    ("Translation keys", all(k in content for k in ['skill_management', 'add_skill'])),
]
for name, ok in skills_checks:
    status = "PASS" if ok else "FAIL"
    print(f"  {status} {name}")

# 5. Categories specific checks
print("\n--- 5. Categories Template ---")
with open('templates/categories.html', encoding='utf-8') as fh:
    content = fh.read()
cats_checks = [
    ("No inline styles", 'style=' not in content),
    ("Has CSS block", '<style>' in content),
    ("Has transitions", 'transition' in content),
    ("Has @media", '@media' in content),
    ("Has 3 modals", content.count('modal') >= 6),
    ("Has search", 'category-search-input' in content),
    ("Has table", 'categories-table' in content),
]
for name, ok in cats_checks:
    status = "PASS" if ok else "FAIL"
    print(f"  {status} {name}")

# 6. App import
print("\n--- 6. App Import ---")
try:
    from app import app
    print("  PASS App imports OK")
except Exception as e:
    print(f"  FAIL {e}")

# 7. Routes
print("\n--- 7. Route Check ---")
with app.app_context():
    client = app.test_client()
    with client.session_transaction() as sess:
        sess['user_id'] = 72
        sess['role_id'] = 1
        sess['email'] = 'kikanimanasvi@gmail.com'
    for path in ['/categories', '/admin/skills']:
        r = client.get(path)
        status = "PASS" if r.status_code == 200 else "FAIL"
        print(f"  {status} {path} -> {r.status_code}")

print("\n" + "=" * 60)
print("VERIFICATION COMPLETE")
print("=" * 60)
