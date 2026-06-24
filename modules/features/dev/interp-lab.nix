# Model interpretability / insight workbench.
#
# The heavy base (torch, transformers) is in nixpkgs, but the specialist interp
# libraries (transformer-lens, sae-lens, nnsight, circuitsvis, bertviz) change
# weekly and are absent from nixpkgs — so they live in a uv-managed project
# (uv installs are persisted under ~/.local/share/uv) rather than the Nix
# closure. Two entry points are exposed on PATH:
#
#   sinnix-interp-lab   launches marimo notebooks with the full interp stack.
#                       Inspect activations, logit lens, attention maps, and
#                       decompose into SAE features (Gemma Scope) on small models
#                       (GPT-2 / Pythia / Gemma-2-2B) that fit 10 GB easily.
#
#   sinnix-steer        builds a control / steering vector with repeng from a
#                       contrastive dataset and exports it as a GGUF, ready for
#                       llama.cpp / koboldcpp `--control-vector`. This is the
#                       DIY-abliteration path: compute the refusal direction
#                       yourself and ablate or amplify any behaviour.
{
  mkFeatureModule,
  pkgs,
  lib,
  config,
  ...
}@args:
mkFeatureModule {
  path = [
    "dev"
    "interpLab"
  ];
  description = "Model interpretability workbench (TransformerLens/SAELens/nnsight) + steering";
  configFn =
    {
      config,
      pkgs,
      lib,
      ...
    }:
    let
      interpDir = "${config.sinnix.paths.librariesRoot}/model/interp";
      user = config.sinnix.user.name;

      pyproject = pkgs.writeText "sinnix-interp-pyproject.toml" ''
        [project]
        name = "sinnix-interp-lab"
        version = "0.1.0"
        requires-python = ">=3.11,<3.13"
        dependencies = [
          "torch>=2.4",
          "transformers>=4.44",
          "transformer-lens>=2.0",
          "sae-lens>=4.0",
          "nnsight>=0.3",
          "circuitsvis>=1.43",
          "bertviz>=1.4",
          "marimo>=0.9",
          "jupyterlab>=4.2",
          "matplotlib",
          "pandas",
        ]
      '';

      # repeng driver: read a JSON dataset of {positive, negative} string pairs,
      # train a control vector against a HF base model, export GGUF.
      steerDriver = pkgs.writeText "sinnix-steer-driver.py" ''
        import argparse, json, torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        from repeng import ControlVector, ControlModel, DatasetEntry

        ap = argparse.ArgumentParser()
        ap.add_argument("--model", required=True, help="HF model id (base for the vector)")
        ap.add_argument("--dataset", required=True, help="JSON: [{\"positive\":..,\"negative\":..}, ...]")
        ap.add_argument("--out", required=True, help="output .gguf path")
        ap.add_argument("--layers", default="-5:-18", help="layer range start:stop (negative indices)")
        a = ap.parse_args()

        start, stop = (int(x) for x in a.layers.split(":"))
        tok = AutoTokenizer.from_pretrained(a.model)
        tok.pad_token_id = tok.pad_token_id or tok.eos_token_id
        model = AutoModelForCausalLM.from_pretrained(a.model, torch_dtype=torch.float16, device_map="cuda")
        cm = ControlModel(model, list(range(start, stop, -1)))

        raw = json.load(open(a.dataset))
        ds = [DatasetEntry(positive=e["positive"], negative=e["negative"]) for e in raw]
        cv = ControlVector.train(cm, tok, ds)
        cv.export_gguf(a.out)
        print("wrote", a.out)
      '';

      interpLab = pkgs.writeShellApplication {
        name = "sinnix-interp-lab";
        runtimeInputs = [
          pkgs.uv
          pkgs.coreutils
          pkgs.git
        ];
        text = ''
          PROJ="''${SINNIX_INTERP_DIR:-$HOME/interp-lab}"
          mkdir -p "$PROJ/notebooks"
          [ -f "$PROJ/pyproject.toml" ] || install -m644 ${pyproject} "$PROJ/pyproject.toml"
          export HF_HOME="${interpDir}/hf"
          export UV_CACHE_DIR="${interpDir}/uv-cache"
          export UV_TORCH_BACKEND="''${UV_TORCH_BACKEND:-auto}"
          mkdir -p "$HF_HOME" "$UV_CACHE_DIR"
          cd "$PROJ"
          echo "interp-lab project: $PROJ  (HF_HOME=$HF_HOME)"
          exec uv run marimo edit --host 127.0.0.1 "$@"
        '';
      };

      steer = pkgs.writeShellApplication {
        name = "sinnix-steer";
        runtimeInputs = [
          pkgs.uv
          pkgs.coreutils
        ];
        text = ''
          if [ "$#" -lt 3 ]; then
            cat <<'USAGE'
          sinnix-steer — build a control/steering (or abliteration) vector as GGUF.

            sinnix-steer <hf-model-id> <dataset.json> <out-name.gguf> [start:stop]

          dataset.json: [{"positive": "...", "negative": "..."}, ...]
            For abliteration: positive = compliant continuations, negative =
            refusals. Apply the result with a NEGATIVE strength to suppress
            refusals, or POSITIVE to amplify the steered trait, via
            koboldcpp/llama.cpp --control-vector.

          Output is written under ${interpDir}/../control-vectors/.
          USAGE
            exit 2
          fi
          model="$1"; dataset="$2"; outname="$3"; layers="''${4:-"-5:-18"}"
          outdir="${config.sinnix.paths.librariesRoot}/model/control-vectors"
          mkdir -p "$outdir"
          export HF_HOME="${interpDir}/hf"
          export UV_CACHE_DIR="${interpDir}/uv-cache"
          export UV_TORCH_BACKEND="''${UV_TORCH_BACKEND:-auto}"
          exec uv run --with repeng --with torch --with transformers --with accelerate \
            python ${steerDriver} --model "$model" --dataset "$dataset" \
            --out "$outdir/$outname" --layers "$layers"
        '';
      };
    in
    {
      environment.systemPackages = [
        pkgs.uv
        pkgs.marimo
        interpLab
        steer
      ];

      systemd.tmpfiles.rules = [
        "d ${interpDir} 0755 ${user} users -"
        "d ${interpDir}/hf 0755 ${user} users -"
        "d ${interpDir}/uv-cache 0755 ${user} users -"
      ];
    };
} args
