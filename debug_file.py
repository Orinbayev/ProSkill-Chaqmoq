
path = r'c:\Users\user\Desktop\chaqmoq_academy\core\templates\core\stats_users.html'
with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i in range(930, 950):
    if i < len(lines):
        print(f"{i+1}: {repr(lines[i])}")
