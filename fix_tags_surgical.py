import re
import os

filepath = r'c:\Users\user\Desktop\chaqmoq_academy\core\templates\core\user_view.html'

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Join split tags: {% \n ... %} or {{ \n ... }}
# This regex looks for {% or {{ followed by whitespace and a newline, 
# then more whitespace, and joins it with the following content.
new_content = re.sub(r'(\{%|\{\{)\s*\n\s*', r'\1 ', content)

# Also join content followed by a split end tag: ... \n whitespace %} or }}
new_content = re.sub(r'\s*\n\s*(\}%|\}\})', r' \1', new_content)

# Specific fix for the messy blocks I saw
# Remove repeated whitespace and newlines inside tags
def clean_tags(match):
    return re.sub(r'\s*\n\s*', ' ', match.group(0))

new_content = re.sub(r'\{%.*?%\}', clean_tags, new_content, flags=re.DOTALL)
new_content = re.sub(r'\{\{.*?\}\}', clean_tags, new_content, flags=re.DOTALL)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(new_content)

print("Tags fixed successfully.")
