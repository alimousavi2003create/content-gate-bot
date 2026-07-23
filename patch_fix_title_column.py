with open("database.py", "r", encoding="utf-8") as f:
    content = f.read()

anchor = '        c.execute("""\n            CREATE TABLE IF NOT EXISTS reactions ('
assert anchor in content, "reactions table anchor not found"

migration = '        c.execute("ALTER TABLE contents ADD COLUMN IF NOT EXISTS title TEXT")\n'
content = content.replace(anchor, migration + anchor, 1)

with open("database.py", "w", encoding="utf-8") as f:
    f.write(content)
print("database.py: title column migration added")
