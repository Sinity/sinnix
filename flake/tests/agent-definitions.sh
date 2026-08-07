#!/usr/bin/env bash
set -euo pipefail

agents_dir=${1:?agent definitions directory}
schemas_dir="$agents_dir/schemas"
fanout=
test -d "$agents_dir" -a -d "$schemas_dir"

for name in lane triage review judge; do
  file="$agents_dir/$name.md"
  test -f "$file"
  frontmatter=$(awk 'BEGIN { in_fm=0 } /^---$/ { in_fm++; next } in_fm == 1 { print } in_fm == 2 { exit }' "$file")
  printf '%s\n' "$frontmatter" | grep -q "^name: $name$"
  printf '%s\n' "$frontmatter" | grep -q '^model: '
  printf '%s\n' "$frontmatter" | grep -q '^effort: '
  printf '%s\n' "$frontmatter" | grep -q '^tools: \['
  printf '%s\n' "$frontmatter" | grep -q '^disallowedTools: \['
done

receipt=$(mktemp)
trap 'rm -f "$receipt"; [[ -z "$fanout" ]] || rm -rf "$fanout"' EXIT
cat > "$receipt" <<'EOF'
{"lane":{"model":"sonnet","effort":"high","tools":["Bash","Read","Write","Edit","Glob","Grep"],"isolation":"worktree"},"triage":{"model":"haiku","effort":"medium","tools":["Bash","Read","Glob","Grep"],"isolation":null},"review":{"model":"opus","effort":"high","tools":["Bash","Read","Glob","Grep"],"isolation":null},"judge":{"model":"sonnet","effort":"high","tools":["Bash","Read","Glob","Grep"],"isolation":null}}
EOF
for name in lane triage review judge; do
  jq -e --arg name "$name" \
    '.[$name].model and .[$name].effort and (.[$name].tools | length > 0)' \
    "$receipt" >/dev/null
done
jq -e '.lane.model == "sonnet" and .lane.effort == "high" and .lane.isolation == "worktree" and .triage.model == "haiku" and .review.model == "opus" and .judge.model == "sonnet"' "$receipt" >/dev/null

lane_fm=$(awk 'BEGIN { n=0 } /^---$/ { n++; next } n == 1 { print } n == 2 { exit }' "$agents_dir/lane.md")
printf '%s\n' "$lane_fm" | grep -q '^isolation: worktree$'
printf '%s\n' "$lane_fm" | grep -q 'Write'

for name in triage judge; do
  test -f "$schemas_dir/$name.schema.json"
  jq -e '.type == "object" and .additionalProperties == false and (.required | length) > 0' \
    "$schemas_dir/$name.schema.json" >/dev/null
done

validate_sample() {
  schema=$1
  sample=$2
  jq -n -e --slurpfile schema "$schema" --argjson sample "$sample" '
    (($schema[0].required - ($sample | keys)) | length) == 0
    and ((($sample | keys) - ($schema[0].properties | keys)) | length) == 0
    and (($sample.confidence | type) == "number" and $sample.confidence >= 0 and $sample.confidence <= 1)
    and (($sample.evidence | type) == "array" and ($sample.evidence | length) >= 1)
    and (($sample.unsupported | type) == "array")
    and (($schema[0].properties.verdict.enum | index($sample.verdict)) != null)
    and (if $schema[0].properties.refutation_attempted then ($sample.refutation_attempted | type) == "boolean" else true end)
  ' >/dev/null
}
validate_sample "$schemas_dir/triage.schema.json" '{"verdict":"confirmed","confidence":1,"evidence":["fixture:1"],"unsupported":[]}'
validate_sample "$schemas_dir/judge.schema.json" '{"verdict":"unsupported","confidence":0.2,"evidence":["fixture:2"],"refutation_attempted":true,"unsupported":["missing live route"]}'

# Disposable fanout: a lane's committed output survives worker cleanup, while
# the triage contract's write capabilities remain explicitly denied.
fanout=$(mktemp -d)
git -C "$fanout" init -q
git -C "$fanout" config user.email fixture@example.invalid
git -C "$fanout" config user.name fixture
printf 'lane result\n' > "$fanout/result"
git -C "$fanout" add result
git -C "$fanout" commit -qm 'fixture: preserve lane result'
commit=$(git -C "$fanout" rev-parse HEAD)
test "$(git -C "$fanout" show --format=%s --no-patch "$commit")" = 'fixture: preserve lane result'
triage_fm=$(awk 'BEGIN { n=0 } /^---$/ { n++; next } n == 1 { print } n == 2 { exit }' "$agents_dir/triage.md")
printf '%s\n' "$triage_fm" | grep -q 'Write'
printf '%s\n' "$triage_fm" | grep -q 'Edit'
test -f "$fanout/result"
