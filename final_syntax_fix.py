import os
import re

path = r"c:\Users\user\Desktop\chaqmoq_academy\core\templates\core\stats_users.html"

with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Fix gender spaces
content = content.replace("request.GET.gender=='male'", "request.GET.gender == 'male'")
content = content.replace("request.GET.gender=='female'", "request.GET.gender == 'female'")

# Fix section spaces
content = content.replace("request.GET.section|default:''==cat.id|stringformat:'i'", "request.GET.section|default:'' == cat.id|stringformat:'i'")

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Spaces fixed in stats_users.html")
