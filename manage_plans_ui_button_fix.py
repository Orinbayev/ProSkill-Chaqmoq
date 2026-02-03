import os

path = r'c:\Users\user\Desktop\chaqmoq_academy\accounts\templates\accounts\center_picker.html'

with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Fix button onclick
if 'openPlanModal()' in content:
    content = content.replace('openPlanModal()', 'openPlansManager()')
    print("Fixed openPlanModal()")
else:
    print("openPlanModal() not found (maybe already fixed?)")

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
