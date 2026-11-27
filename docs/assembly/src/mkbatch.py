import json, sys
sys.path.insert(0, sys.argv[1]); from steps import STEPS, O
D = "/private/var/folders/1m/xl9j3tqn1wgblzhtvy1gqclm0000gn/T/solidcraft-mcp-23528-17346248"
ks = [int(k) for k in sys.argv[2].split(",")]
cmds = []
for st in STEPS:
    if st["n"] not in ks: continue
    n = st["n"]
    cmds.append({"command": "browser.visibility", "params": {"paths": [[O[k]] for k in st["show"]], "isolate": True, "visible": True}})
    cmds.append({"command": "explode.create", "params": {"name": f"A{n}", "moves": [{"occurrence": O[k], "translate": list(v)} for k, v in st["moves"].items()]}})
    cmds.append({"command": "motion.export_animation", "params": {"view": f"A{n}", "path": f"{D}/asm-{n:02d}", "samples": 2,
                 "width": 1920, "height": 1080, "camera": st["cam"], "grid": False, "axes": False}})
print(json.dumps(cmds))
