import os
import re

def title_case(match):
    quote = match.group(1)
    original = match.group(2)
    # Split by underscore
    words = original.split('_')
    # Capitalize each word
    title_cased = ' '.join(word.capitalize() for word in words)
    return f"_({quote}{title_cased}{quote})"

target_dir = os.path.join(os.path.dirname(__file__), 'templates')

updated_files = 0
total_replacements = 0

for root, dirs, files in os.walk(target_dir):
    for file in files:
        if file.endswith('.html'):
            filepath = os.path.join(root, file)
            
            # Try reading with different encodings
            content = None
            for encoding in ['utf-8', 'utf-16', 'latin-1']:
                try:
                    with open(filepath, 'r', encoding=encoding) as f:
                        content = f.read()
                    break
                except UnicodeDecodeError:
                    continue
                    
            if content is None:
                continue
            
            # Match both single and double quotes
            new_content, count = re.subn(r"_\((['\"])([a-z0-9_]+)\1\)", title_case, content)
            
            if count > 0:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                print(f"Updated {filepath}: {count} double/single quote replacements")
                updated_files += 1
                total_replacements += count

if total_replacements > 0:
    print(f"\nFinal Summary: Fixed {total_replacements} words across {updated_files} template files globally!")
else:
    print("\nNo remaining replacements found. System is clean!")
