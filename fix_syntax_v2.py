import os

path = r"c:\Users\user\Desktop\chaqmoq_academy\core\templates\core\stats_users.html"

with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    line = line.replace("request.GET.gender=='male'", "request.GET.gender == 'male'")
    line = line.replace("request.GET.gender=='female'", "request.GET.gender == 'female'")
    line = line.replace("request.GET.section|default:''==cat.id|stringformat:'i'", "request.GET.section|default:'' == cat.id|stringformat:'i'")
    new_lines.append(line)

with open(path, 'w', encoding='utf-8', newline='') as f:
    f.writelines(new_lines)

print("Done")
