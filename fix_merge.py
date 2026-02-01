import os

path = r"c:\Users\user\Desktop\chaqmoq_academy\core\templates\core\stats_users.html"

with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
for i, line in enumerate(lines):
    # If we find line 502 (index 501) that is split
    if 'request.GET.section|default:\'\'' in line and 'stringformat:\'s\' or' in line:
        # We merge it with the next line
        next_line = lines[i+1].strip()
        merged_line = line.replace('\n', ' ') + next_line + '\n'
        new_lines.append(merged_line)
        # Skip next line
        lines[i+1] = "SKIP_ME"
    elif line == "SKIP_ME":
        continue
    else:
        new_lines.append(line)

with open(path, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print("Merged split template tags.")
