"""Generate typed native Beads requests from `bd owner schema`.

Regenerate using datamodel-code-generator 0.80.0:
  bd owner schema --json > owner-schema.json
  uvx --from datamodel-code-generator==0.80.0 --with pyyaml python generate_beads_inputs.py owner-schema.json
Package checks use --check with the pinned Beads binary's emitted schema.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path

OPERATIONS = {
    "createIssue": "beads.create",
    "updateIssue": "beads.update",
    "addComment": "beads.comment",
    "claimIssue": "beads.claim",
    "releaseIssue": "beads.unclaim",
    "closeIssue": "beads.close",
    "reopenIssue": "beads.reopen",
    "compareAndSetMetadata": "beads.metadata.compare_set",
    "batchCreateIssues": "beads.graph.create",
    "applyBatch": "beads.changeset",
    "batchCloseIssues": "beads.batch.close",
    "claimNextIssue": "beads.claim_next",
    "addDependencies": "beads.dependencies.add",
    "removeDependency": "beads.dependencies.remove",
    "rememberMemory": "beads.memory.remember",
    "forgetMemory": "beads.memory.forget",
    "getDependencyTree": "beads.graph",
    "listDependencyCycles": "beads.cycles",
    "listMemories": "beads.memories",
    "getMemory": "beads.memory.get",
    "listRelatedIssues": "beads.related",
    "listDependencies": "beads.dependencies",
    "countDependencyEdges": "beads.dependencies.count",
    "listBlockingAnnotations": "beads.blockers",
}
ROOT = Path(__file__).parent / "sinnix_agent_gateway"


def canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def extract(document: dict) -> tuple[dict, dict]:
    """Select published operations, preserving every owner's schema member."""
    definitions = document["components"]["schemas"].copy()
    operations = {}
    for item in document["paths"].values():
        for method, operation in item.items():
            if (
                not isinstance(operation, dict)
                or operation.get("operationId") not in OPERATIONS
            ):
                continue
            identity = operation["operationId"]
            name = identity[0].upper() + identity[1:] + "Input"
            properties, required = {}, []
            for location in ("path", "query"):
                fields, mandatory = {}, []
                for parameter in [
                    *item.get("parameters", []),
                    *operation.get("parameters", []),
                ]:
                    if "$ref" in parameter:
                        parameter = document["components"]["parameters"][
                            parameter["$ref"].rsplit("/", 1)[1]
                        ]
                    if parameter["in"] != location:
                        continue
                    schema = dict(parameter["schema"])
                    if "description" in parameter:
                        schema["description"] = parameter["description"]
                    fields[parameter["name"]] = schema
                    if parameter.get("required"):
                        mandatory.append(parameter["name"])
                if fields:
                    properties[location] = {
                        "type": "object",
                        "properties": fields,
                        "additionalProperties": False,
                    }
                    if mandatory:
                        properties[location]["required"] = mandatory
                        required.append(location)
            body = operation.get("requestBody")
            if body:
                properties["body"] = body["content"]["application/json"]["schema"]
                if body.get("required"):
                    required.append("body")
            definitions[name] = {
                "type": "object",
                "properties": properties,
                "additionalProperties": False,
            }
            if required:
                definitions[name]["required"] = required
            operations[identity] = {
                "action": OPERATIONS[identity],
                "model": name,
                "write": method not in {"get", "head"},
                "summary": operation["summary"],
            }
    missing = set(OPERATIONS) - operations.keys()
    if missing:
        raise ValueError(f"owner removed declared operations: {missing}")
    # Retain only definitions reachable from the selected requests.
    used = {}

    def visit(value):
        if isinstance(value, dict):
            if "$ref" in value:
                key = value["$ref"].rsplit("/", 1)[1]
                value["$ref"] = "#/$defs/" + key
                if key not in used:
                    used[key] = definitions[key]
                    visit(used[key])
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    if document.get("x-beads-owner-read"):
        definitions["OwnerReadInput"] = document["x-beads-owner-read"]
    refs = [{"$ref": "#/$defs/" + row["model"]} for row in operations.values()]
    if "OwnerReadInput" in definitions:
        refs.append({"$ref": "#/$defs/OwnerReadInput"})
    visit(refs)
    return {"$defs": used, "anyOf": refs}, operations


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("schema", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    document = json.loads(args.schema.read_text())
    schema, operations = extract(document)
    metadata_path = ROOT / "generated_beads_contracts.json"
    output = ROOT / "generated_beads_inputs.py"
    source = {
        "request_schema": schema,
        "operations": operations,
        "owner_read": document.get("x-beads-owner-read"),
    }
    if args.check:
        stored = json.loads(metadata_path.read_text())
        if (
            stored["source"] != source
            or stored["model_sha256"] != hashlib.sha256(output.read_bytes()).hexdigest()
        ):
            raise SystemExit(
                "Beads generated input contracts differ from the pinned owner"
            )
        return
    with tempfile.TemporaryDirectory() as work:
        path = Path(work) / "beads-requests.json"
        path.write_text(canonical(schema))
        subprocess.run(
            [
                "datamodel-codegen",
                "--input",
                str(path),
                "--input-file-type",
                "jsonschema",
                "--output-model-type",
                "pydantic_v2.BaseModel",
                "--output",
                str(output),
                "--target-python-version",
                "3.12",
                "--use-standard-collections",
                "--use-union-operator",
                "--field-constraints",
                "--use-schema-description",
                "--strict-nullable",
                "--use-missing-sentinel",
                "--enum-field-as-literal",
                "all",
                "--disable-timestamp",
                "--formatters",
                "builtin",
            ],
            check=True,
        )
    metadata_path.write_text(
        json.dumps(
            {
                "generator": "datamodel-code-generator==0.80.0",
                "source": source,
                "model_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
