with open("templates/admin_dashboard.html", "r", encoding="utf-8") as f:
    content = f.read()

anchor = "</script>"
assert content.count(anchor) >= 1, "</script> tag not found"

init_calls = "loadChannels();\nloadContents();\n"

if "loadChannels();" not in content:
    idx = content.rindex(anchor)
    content = content[:idx] + init_calls + content[idx:]
    print("init calls re-added before </script>")
else:
    print("loadChannels(); already present, no change needed")

with open("templates/admin_dashboard.html", "w", encoding="utf-8") as f:
    f.write(content)
