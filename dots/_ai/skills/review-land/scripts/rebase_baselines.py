import json, re, sys, collections
log = open(sys.argv[1]).read()
start = log.find('"new_matches"')
if start == -1: sys.exit(1)
obj_start = log.rfind('{', 0, start)
depth = 0; end = obj_start
for i, ch in enumerate(log[obj_start:], obj_start):
    if ch == '{': depth += 1
    elif ch == '}':
        depth -= 1
        if depth == 0: end = i + 1; break
payload = json.loads(log[obj_start:end])
pat = re.compile(r'^(\S+) (\S+):(\d+)')
new = collections.defaultdict(list); stale = collections.defaultdict(list)
for row in payload.get('new_matches', []):
    m = pat.match(row); new[(m.group(1), m.group(2))].append(int(m.group(3)))
for row in payload.get('stale_matches', []):
    m = pat.match(row); stale[(m.group(1), m.group(2))].append(int(m.group(3)))
if set(new) != set(stale) or any(len(new[k]) != len(stale[k]) for k in new):
    sys.exit(1)  # not a pure displacement — human decides
for (rule, path), new_lines in new.items():
    bl = f"devtools/patterns/baselines/{rule}.txt"
    text = open(bl).read()
    for old, nw in zip(sorted(stale[(rule, path)]), sorted(new_lines)):
        o = f"{path}:{old}\n"
        if o not in text: sys.exit(1)
        text = text.replace(o, f"{path}:{nw}\n", 1)
    open(bl, 'w').write(text)
print("rebased displaced baselines")
