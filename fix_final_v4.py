import os

path = r"c:\Users\user\Desktop\chaqmoq_academy\core\templates\core\stats_users.html"

with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Fix spaces for Django 5.x
content = content.replace("request.GET.gender=='male'", "request.GET.gender == 'male'")
content = content.replace("request.GET.gender=='female'", "request.GET.gender == 'female'")
content = content.replace("request.GET.section|default:''==cat.id|stringformat:'i'", "request.GET.section|default:'' == cat.id|stringformat:'i'")

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Final surgical fix for spaces applied.")
