import re

with open('app/ui/settings.py', 'r', encoding='utf-8') as f:
    content = f.read()

bad_lines = '''        self.stack.addWidget(page)
        self.pages["Updates"] = page'''

good_lines = '''        self.pages.addWidget(page)'''

content = content.replace(bad_lines, good_lines)

with open('app/ui/settings.py', 'w', encoding='utf-8') as f:
    f.write(content)
