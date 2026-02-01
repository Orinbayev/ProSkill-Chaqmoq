import re
import os

filepath = r'c:\Users\user\Desktop\chaqmoq_academy\core\templates\core\user_view.html'

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Unified regex to join multi-line tags
# Matches {{ followed by anything (including newlines) until }}
def join_tags(match):
    tag = match.group(0)
    # Replace all whitespace sequences (including newlines) with a single space
    # but keep spaces inside strings if any (simple approach)
    joined = re.sub(r'\s+', ' ', tag)
    return joined

# Fix {{ ... }}
content = re.sub(r'\{\{.*?\}\}', join_tags, content, flags=re.DOTALL)
# Fix {% ... %}
content = re.sub(r'\{%.*?%\}', join_tags, content, flags=re.DOTALL)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)

print("All tags joined successfully.")
