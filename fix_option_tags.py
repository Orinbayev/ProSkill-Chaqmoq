filepath = r'c:\Users\user\Desktop\chaqmoq_academy\core\templates\core\user_view.html'

with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Fix split option tags on lines 307-308 (0-indexed: 306-307)
# Find the pattern and consolidate
for i in range(len(lines) - 1):
    if 'selected_month == m_id' in lines[i] and 'm_name }}' in lines[i+1]:
        # Consolidate lines 306-307
        lines[i] = '                                    <option value="{{ m_id }}" {% if selected_month == m_id %}selected{% endif %}>{{ m_name }}</option>\r\n'
        lines[i+1] = ''  # Mark for deletion
        print(f"✅ Fixed month option tag at line {i+1}")
        break

# Find and fix year option tag
for i in range(len(lines) - 1):
    if 'selected_year == y' in lines[i] and '</option>' in lines[i+1]:
        # Consolidate
        lines[i] = '                                    <option value="{{ y }}" {% if selected_year == y %}selected{% endif %}>{{ y }}</option>\r\n'
        lines[i+1] = ''  # Mark for deletion
        print(f"✅ Fixed year option tag at line {i+1}")
        break

# Remove empty lines
lines = [line for line in lines if line.strip() or line == '\r\n']

with open(filepath, 'w', encoding='utf-8') as f:
    f.writelines(lines)

print("\n✅ Barcha split option taglar tuzatildi!")
