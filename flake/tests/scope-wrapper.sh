#!/usr/bin/env bash
set -euo pipefail

# The rc under test is the RENDERED one: `commandMatchers` are baked into the
# wrapper's class resolver at evaluation time (runtime-defaults'
# renderDirenvrc), so a wrapped command consults no runtime inventory. Feeding
# the raw scripts/sinnix-direnvrc here would leave the placeholder in place and
# the gpu-runtime assertions below would fail on a syntax error.
direnvrc="${1:?rendered direnv rc required}"
fixture="$(mktemp -d)"
trap 'rm -rf "$fixture"' EXIT

source "$direnvrc"
wrapper_dir="$fixture/wrapper"
original_dir="$fixture/original"
mkdir -p "$wrapper_dir" "$original_dir" "$fixture/bin"
_sinnix_write_scope_wrapper "$wrapper_dir/.sinnix-scope-wrapper"
sed -i "1c#!$(command -v bash)" "$wrapper_dir/.sinnix-scope-wrapper"

cat >"$fixture/bin/sinnix-scope" <<'EOF_SCOPE'
#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "$1" >>"$SCOPE_RECORD"
EOF_SCOPE
chmod +x "$fixture/bin/sinnix-scope"
sed -i "1c#!$(command -v bash)" "$fixture/bin/sinnix-scope"

ln -s .sinnix-scope-wrapper "$wrapper_dir/nix"
ln -s .sinnix-scope-wrapper "$wrapper_dir/just"
export SINNIX_SCOPE_BIN="$fixture/bin/sinnix-scope"
export SINNIX_SCOPE_WRAPPER_DIR="$wrapper_dir"
export SINNIX_SCOPE_ORIGINAL_PATH="$original_dir:$PATH"
export SCOPE_RECORD="$fixture/classes"

"$wrapper_dir/nix" develop /realm/project/stashbox#analysis --command stashbox-vlm-serve
"$wrapper_dir/nix" develop /realm/project/stashbox#analysis --command=stashbox-llama-vlm-serve-gpu
"$wrapper_dir/nix" develop /realm/project/stashbox#analysis --command cargo test
"$wrapper_dir/nix" build .#sinnix-prime
"$wrapper_dir/just" chisel

expected=$'gpu-runtime\ngpu-runtime\nnix-build\nnix-build\nbackground'
actual="$(<"$SCOPE_RECORD")"
if [[ $actual != "$expected" ]]; then
  printf 'unexpected scope classes:\n%s\n' "$actual" >&2
  exit 1
fi

printf 'scope wrapper fixture passed\n'
