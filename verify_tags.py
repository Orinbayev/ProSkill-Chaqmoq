import re

filepath = r'c:\Users\user\Desktop\chaqmoq_academy\core\templates\core\user_view.html'

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Pattern for multi-line {{ }} or {% %}, but also specifically check for spacings in operators
multi_line_tag = re.compile(r'(\{\{.*?\}\}|\{%.*?%\})', re.DOTALL)
matches = multi_line_tag.findall(content)

found_error = False
for m in matches:
    if '\n' in m:
        print(f"SPLIT TAG FOUND: {repr(m)}")
        found_error = True
    
    # Check for keywords without spaces around logic
    if '{% if' in m or '{% elif' in m:
        if '==' in m and ' == ' not in m:
            print(f"SPACING ERROR IN TAG: {repr(m)}")
            found_error = True

if not found_error:
    print("NO TAG ERRORS FOUND. Success!")
