"""Execute the rendered model assignments without launching a client or auth."""

import os
import re
import subprocess
import sys
from pathlib import Path

wrapper, expected = sys.argv[1:]
variables = (
    "ANTHROPIC_MODEL",
    "ANTHROPIC_DEFAULT_OPUS_MODEL",
    "ANTHROPIC_DEFAULT_SONNET_MODEL",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL",
    "CLAUDE_CODE_SUBAGENT_MODEL",
)
assignments = [
    line.strip()
    for line in Path(wrapper).read_text().splitlines()
    if re.match(r"\s*(?:export )?[A-Z_]*MODEL=", line)
]
assert assignments, "wrapper has no model assignments"
environment = {key: value for key, value in os.environ.items() if "MODEL" not in key}
result = subprocess.run(
    [
        "bash",
        "-eu",
        "-c",
        "\n".join(assignments)
        + "\n"
        + "\n".join(f'printf "%s\\n" "${{{name}}}"' for name in variables),
    ],
    env=environment,
    capture_output=True,
    text=True,
    check=True,
    timeout=5,
)
assert result.stdout.splitlines() == [expected] * len(variables), result.stdout
