filepath = r'c:\Users\user\Desktop\chaqmoq_academy\core\templates\core\user_view.html'

with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find and fix all split tags in timeline section (around lines 188-203)
# We need to consolidate:
# 189-190: rule_nom span
# 192-194: ball span
# 198-199: beruvchi span  
# 200-201: calendar span
# 202-203: group.nom span

# Strategy: Replace lines 188-203 with cleaned version
timeline_section_start = 187  # 0-indexed (line 188)
timeline_section_end = 204    # Up to line 204

new_section = [
    '                             <div class="d-flex justify-content-between align-items-center mb-1">\r\n',
    '                                <span class="fw-bold text-white small">{{ action.rule_nom|default:"Ball belgilandi" }}</span>\r\n',
    '                                <span class="fw-black {% if action.ball > 0 %}text-success{% else %}text-danger{% endif %} small">{% if action.ball > 0 %}+{% endif %}{{ action.ball }}</span>\r\n',
    '                            </div>\r\n',
    '                            <div class="d-flex flex-wrap gap-2 text-white-50" style="font-size: 0.75rem;">\r\n',
    '                                <span><i class="fa-solid fa-user-pen me-1"></i> {{ action.beruvchi.get_full_name|default:"Tizim" }}</span>\r\n',
    '                                <span><i class="fa-solid fa-calendar me-1"></i> {{ action.sana|date:"d.m.Y, H:i" }}</span>\r\n',
    '                                {% if action.group %}<span><i class="fa-solid fa-users me-1 text-warning"></i> {{ action.group.nom|safe }}</span>{% endif %}\r\n',
]

# Replace
lines[timeline_section_start:timeline_section_end] = new_section

with open(filepath, 'w', encoding='utf-8') as f:
    f.writelines(lines)

print("✅ Barcha split taglar tuzatildi!")
print("✅ Vaqt formati: d.m.Y, H:i (har doim to'liq)")
