#!/usr/bin/env bash
set -euo pipefail

validator=$1
root=$TMPDIR/skills
mkdir -p "$root/good" "$root/broken-reference" "$root/malformed"

cat >"$root/good/SKILL.md" <<'EOF'
---
name: good
description: A deliberately plain description for a structural validator fixture.
---

# Good

This fixture has no trigger phrase requirement.
EOF

cat >"$root/broken-reference/SKILL.md" <<'EOF'
---
name: broken-reference
description: A valid description with a missing local reference.
---

[Missing](references/no-such-file.md)
EOF

cat >"$root/malformed/SKILL.md" <<'EOF'
---
name: malformed
description: A valid description
bad frontmatter line
---

# Malformed
EOF

if "$validator" "$root" >"$TMPDIR/broken.json"; then
  echo "validator accepted malformed fixtures" >&2
  exit 1
fi

jq -e '.findings | map(select(.error | contains("broken reference"))) | length == 1' \
  "$TMPDIR/broken.json" >/dev/null
jq -e '.findings | map(select(.error | contains("malformed frontmatter line"))) | length == 1' \
  "$TMPDIR/broken.json" >/dev/null

rm -rf "$root/broken-reference" "$root/malformed"
"$validator" "$root" >"$TMPDIR/good.json"
jq -e '.findings == []' "$TMPDIR/good.json" >/dev/null
