import re

path = r'c:\Users\user\Desktop\chaqmoq_academy\accounts\templates\accounts\center_picker.html'

with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace the broken lines
# Using simple replace for the known broken strings
content = content.replace('{ { p.monthly_price } }', '{{ p.monthly_price|default:0 }}')
content = content.replace('{ { p.discount_percent |default: 0 } }', '{{ p.discount_percent|default:0 }}')

# Also safeguard strings while we are at it
content = content.replace('code: "{{ p.code }}', 'code: "{{ p.code|escapejs }}')
content = content.replace('title: "{{ p.title }}', 'title: "{{ p.title|escapejs }}')

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
    
print("Fixed availablePlans syntax.")
