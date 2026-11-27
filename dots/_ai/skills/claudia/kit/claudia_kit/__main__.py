"""python -m claudia_kit <stage> ...: hand the arguments to one stage's own command line."""
import importlib, sys
from . import STAGES, __doc__ as DOC

if len(sys.argv) < 2 or sys.argv[1] not in STAGES:
    sys.exit(DOC)
importlib.import_module(f"claudia_kit.{sys.argv[1]}").main(sys.argv[2:])
