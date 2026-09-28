with open('core/resume_engine.py', 'r', encoding='utf-8', errors='ignore') as f:
    lines = f.readlines()

new_lines = []
for idx, line in enumerate(lines, 1):
    if idx >= 249 and idx <= 262:
        if line.startswith('            '):
            line = line[4:] # remove 4 spaces
    new_lines.append(line)

with open('core/resume_engine.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print('Indentation fixed in resume_engine.py!')
