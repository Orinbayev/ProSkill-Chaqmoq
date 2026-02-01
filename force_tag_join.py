import re

filepath = r'c:\Users\user\Desktop\chaqmoq_academy\core\templates\core\user_view.html'

with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_content = ""
for line in lines:
    # Aggressively join anything that looks like a split Django tag
    # This is a bit risky but we'll try to join lines that end with {{ or {%, or start with }} or %}
    new_content += line

# Better approach: find all occurrences of {{ and join until }}
def j(m): return m.group(0).replace('\n', ' ').replace('\r', '').replace('  ', ' ')

final_content = re.sub(r'\{\{.*?\}\}', j, new_content, flags=re.DOTALL)
final_content = re.sub(r'\{%.*?%\}', j, final_content, flags=re.DOTALL)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(final_content)

print("Forced join complete.")
