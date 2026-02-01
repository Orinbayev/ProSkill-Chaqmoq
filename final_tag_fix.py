import re
import os

filepath = r'c:\Users\user\Desktop\chaqmoq_academy\core\templates\core\user_view.html'

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# This regex is specifically designed to find split tags and join them
def tag_fixer(match):
    return re.sub(r'\s+', ' ', match.group(0))

# Fix {{ ... }} tags that span multiple lines
content = re.sub(r'\{\{.*?\}\}', tag_fixer, content, flags=re.DOTALL)
# Fix {% ... %} tags that span multiple lines
content = re.sub(r'\{%.*?%\}', tag_fixer, content, flags=re.DOTALL)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)

print("Tags fixed and joined.")
