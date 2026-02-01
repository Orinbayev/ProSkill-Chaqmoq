import re
import os

# Paths to search and fix
search_dirs = [
    r'c:\Users\user\Desktop\chaqmoq_academy\core\templates\core',
    r'c:\Users\user\Desktop\chaqmoq_academy\education\templates\education'
]

# Regex to find {% ... %} tags
tag_regex = re.compile(r'(\{%.*?%\})', re.DOTALL)

def fix_tag_content(tag_text):
    # Only touch it if it contains ==
    if '==' in tag_text:
        # Avoid changing things inside quotes as best as possible, 
        # but in Django tags, usually we want spaces around == anyway.
        # This regex looks for == and ensures there is a space before and after.
        # It handles:
        # a==b -> a == b
        # a ==b -> a == b
        # a== b -> a == b
        # [^\s!<>]= -> ensure we don't break !=, <=, >=
        
        # 1. Add space before == if missing
        tag_text = re.sub(r'([^\s!<>])==', r'\1 ==', tag_text)
        # 2. Add space after == if missing
        tag_text = re.sub(r'==([^\s])', r'== \1', tag_text)
        
    return tag_text

files_fixed = 0

for d in search_dirs:
    for root, _, files in os.walk(d):
        for f in files:
            if f.endswith('.html'):
                path = os.path.join(root, f)
                try:
                    with open(path, 'r', encoding='utf-8') as file:
                        content = file.read()
                    
                    new_content = tag_regex.sub(lambda m: fix_tag_content(m.group(0)), content)
                    
                    if new_content != content:
                        with open(path, 'w', encoding='utf-8') as file:
                            file.write(new_content)
                        print(f"Fixed spaces in: {path}")
                        files_fixed += 1
                except Exception as e:
                    print(f"Error processing {path}: {e}")

print(f"Total files fixed: {files_fixed}")
