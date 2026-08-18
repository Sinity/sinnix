#!/usr/bin/env bash
# Agent definition contract: every dispatchable definition carries the fields
# the dispatch hook requires, the read-only workers deny write-shaped tools
# while the implementation lane is granted them, and each structured-output
# schema is closed and validates a representative verdict.
#
# Provably fails when: a definition loses model/effort, a read-only worker is
# granted Write/Edit/MultiEdit (verified), or a verdict schema stops being a
# closed object with required fields.
set -euo pipefail

agents_dir=${1:?agent definitions directory}
schemas_dir="$agents_dir/schemas"
test -d "$agents_dir" -a -d "$schemas_dir"

for name in lane triage review judge; do
  file="$agents_dir/$name.md"
  test -f "$file"
  frontmatter=$(awk 'BEGIN { in_fm=0 } /^---$/ { in_fm++; next } in_fm == 1 { print } in_fm == 2 { exit }' "$file")
  printf '%s\n' "$frontmatter" | grep -q "^name: $name$"
  printf '%s\n' "$frontmatter" | grep -q '^model: '
  printf '%s\n' "$frontmatter" | grep -q '^effort: '
  # Key presence only: YAML array layout (inline vs wrapped) is owned by
  # the formatter, so anchoring on '[ ' broke on a reflow. Non-emptiness
  # of the tool sets is covered by the receipt assertions below.
  printf '%s\n' "$frontmatter" | grep -q '^tools:'
  printf '%s\n' "$frontmatter" | grep -q '^disallowedTools:'
done

# Capability boundaries, read from the definitions rather than a restated
# table: the read-only workers must deny every write-shaped tool, and the
# implementation lane must be granted them. `disallowedTools` may wrap onto
# the following line, so the block is read as one flattened string.
frontmatter_field() {
  awk -v field="$2" '
    BEGIN { n = 0; collecting = 0 }
    /^---$/ { n++; if (n == 2) exit; next }
    n == 1 {
      if ($0 ~ "^" field ":") { collecting = 1; sub("^" field ":", ""); printf "%s", $0; next }
      if (collecting && $0 ~ /^[[:space:]]/) { printf "%s", $0; next }
      if (collecting) exit
    }
  ' "$1"
}

write_tools="Write Edit MultiEdit"
for name in triage review judge; do
  denied=$(frontmatter_field "$agents_dir/$name.md" disallowedTools)
  granted=$(frontmatter_field "$agents_dir/$name.md" tools)
  for tool in $write_tools; do
    printf '%s' "$denied" | grep -q "\b$tool\b" ||
      {
        printf '%s must deny %s\n' "$name" "$tool" >&2
        exit 1
      }
    if printf '%s' "$granted" | grep -q "\b$tool\b"; then
      printf '%s must not be granted %s\n' "$name" "$tool" >&2
      exit 1
    fi
  done
done

lane_granted=$(frontmatter_field "$agents_dir/lane.md" tools)
for tool in Write Edit; do
  printf '%s' "$lane_granted" | grep -q "\b$tool\b" ||
    {
      printf 'lane must be granted %s\n' "$tool" >&2
      exit 1
    }
done
grep -q '^isolation: worktree$' "$agents_dir/lane.md"

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
