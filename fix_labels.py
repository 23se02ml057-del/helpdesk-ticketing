import os
import re

html_dir = "templates"
# Match exactly _('snake_case') or _("snake_case")
pattern = re.compile(r"(_\(['\"])([a-zA-Z0-9_]+)(['\"]\))")

def replacer(match):
    prefix = match.group(1)
    string = match.group(2)
    suffix = match.group(3)
    
    # Only format if there's an underscore and no spaces
    if '_' in string and ' ' not in string:
        # Avoid capitalizing completely uppercase strings like 'ID' if they exist, but here we just .title()
        string = string.replace('_', ' ').title()
    
    return prefix + string + suffix

updated_count = 0
for root, _, files in os.walk(html_dir):
    for file in files:
        if file.endswith(".html") and ("customer" in file or "layout_" in file):
            path = os.path.join(root, file)
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            
            new_content = pattern.sub(replacer, content)
            if new_content != content:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(new_content)
                updated_count += 1
                print(f"Updated {file}")

print(f"Fixed translation keys in {updated_count} customer templates.")
