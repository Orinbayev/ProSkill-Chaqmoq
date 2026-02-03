import re

path = r'c:\Users\user\Desktop\chaqmoq_academy\accounts\templates\accounts\center_picker.html'

with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Regex to find availablePlans block
# It starts with "let availablePlans = [" and ends with "];"
# We use DOTALL to match newlines
pattern = re.compile(r'let availablePlans = \[.*?\];', re.DOTALL)

replacement = """let availablePlans = [
    {% for p in db_plans %}
  {
    code: "{{ p.code }}",
    title: "{{ p.title }}",
    monthly_price: {{ p.monthly_price }},
    discount_percent: {{ p.discount_percent|default:0 }}
  } {% if not forloop.last %}, {% endif %}
  {% endfor %}
  ];"""

if pattern.search(content):
    content = pattern.sub(replacement, content)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("availablePlans updated successfully.")
else:
    print("availablePlans block not found!")
