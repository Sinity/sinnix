<!-- GENERATED FILE. DO NOT EDIT. -->
<!-- gateway-catalog-revision: v2-g3.0-pueue-jobs -->
<!-- gateway-catalog-sha256: 73967b9d691118482283e66b72ecb11faa84c0a62f2b15c4f0838787f9d5242f -->

# Sinnix Agent Gateway V2 reference

This reference is generated from `sinnix_agent_gateway.registry.REGISTRY`. The catalog hash changes when an action, resource, schema, route, principal, bound, or example changes.

Revision: `v2-g3.0-pueue-jobs`. Catalog SHA-256: `73967b9d691118482283e66b72ecb11faa84c0a62f2b15c4f0838787f9d5242f`.

## Ten CLI verbs

Each verb calls the matching MCP tool through the same runtime and principal. Requests accept `--input`, `--input-file`, or `--stdin`; common request controls can be supplied as flags. Mutating requests require the idempotency key declared by their selected action.

| Verb      | CLI subcommand                 | MCP tool  |
| --------- | ------------------------------ | --------- |
| `status`  | `sinnix-agent-gateway status`  | `status`  |
| `catalog` | `sinnix-agent-gateway catalog` | `catalog` |
| `query`   | `sinnix-agent-gateway query`   | `query`   |
| `get`     | `sinnix-agent-gateway get`     | `get`     |
| `context` | `sinnix-agent-gateway context` | `context` |
| `events`  | `sinnix-agent-gateway events`  | `events`  |
| `wait`    | `sinnix-agent-gateway wait`    | `wait`    |
| `change`  | `sinnix-agent-gateway change`  | `change`  |
| `operate` | `sinnix-agent-gateway operate` | `operate` |
| `run`     | `sinnix-agent-gateway run`     | `run`     |

## Resources

| Resource            | Owner              | Canonical reference                                      | Query   |
| ------------------- | ------------------ | -------------------------------------------------------- | ------- |
| `project`           | `projects`         | `sinnix://projects/{project_id}`                         | `true`  |
| `checkout`          | `projects`         | `sinnix://projects/{project_id}/checkouts/{checkout_id}` | `true`  |
| `bead`              | `beads`            | `sinnix://projects/{project_id}/beads/{bead_id}`         | `true`  |
| `task_authority`    | `beads`            | `sinnix://projects/{project_id}/task-authority`          | `false` |
| `job`               | `jobs`             | `sinnix://jobs/{job_id}`                                 | `true`  |
| `artifact`          | `artifacts`        | `sinnix://artifacts/{artifact_id}`                       | `true`  |
| `receipt`           | `audit`            | `sinnix://receipts/{receipt_id}`                         | `true`  |
| `result`            | `results`          | `sinnix://results/{result_id}`                           | `true`  |
| `machine_unit`      | `machine`          | `sinnix://machine/units/{manager}/{unit}`                | `true`  |
| `browser_page`      | `browser`          | `sinnix://browser/pages/{page_id}`                       | `true`  |
| `browser_workspace` | `browser`          | `sinnix://browser/agent-workspace`                       | `false` |
| `process`           | `machine`          | `sinnix://processes/{pid}/{start_ticks}`                 | `true`  |
| `terminal`          | `terminals`        | `sinnix://terminals/{terminal_id}`                       | `true`  |
| `desktop`           | `desktop`          | `sinnix://desktop/current`                               | `true`  |
| `host_file`         | `files`            | `sinnix://files/{file_token}`                            | `true`  |
| `mcp_tool`          | `mcp-broker`       | `sinnix://mcp/{server}/tools/{tool}`                     | `true`  |
| `capture_lane`      | `captures`         | `sinnix://captures/{lane}`                               | `true`  |
| `capability`        | `capability-index` | `sinnix://capabilities/{name}`                           | `true`  |
| `session`           | `sessions`         | `sinnix://sessions/{provider}/{session_id}`              | `true`  |
| `context_snapshot`  | `context`          | `sinnix://contexts/{snapshot_id}`                        | `true`  |

## Actions

| Action               | Verb      | Owner              | Route                     | Schema                                                                                             |
| -------------------- | --------- | ------------------ | ------------------------- | -------------------------------------------------------------------------------------------------- |
| `gateway.status`     | `status`  | `gateway`          | `observe.gateway_status`  | [`sinnix://gateway/v2/actions/gateway.status`](sinnix://gateway/v2/actions/gateway.status)         |
| `gateway.catalog`    | `catalog` | `registry`         | `registry.search`         | [`sinnix://gateway/v2/actions/gateway.catalog`](sinnix://gateway/v2/actions/gateway.catalog)       |
| `resources.get`      | `get`     | `resolver`         | `resources.get`           | [`sinnix://gateway/v2/actions/resources.get`](sinnix://gateway/v2/actions/resources.get)           |
| `projects.query`     | `query`   | `projects`         | `projects.search`         | [`sinnix://gateway/v2/actions/projects.query`](sinnix://gateway/v2/actions/projects.query)         |
| `beads.query`        | `query`   | `beads`            | `beads.query`             | [`sinnix://gateway/v2/actions/beads.query`](sinnix://gateway/v2/actions/beads.query)               |
| `projects.context`   | `context` | `project-context`  | `project_context.context` | [`sinnix://gateway/v2/actions/projects.context`](sinnix://gateway/v2/actions/projects.context)     |
| `audit.events`       | `events`  | `audit`            | `audit.tail`              | [`sinnix://gateway/v2/actions/audit.events`](sinnix://gateway/v2/actions/audit.events)             |
| `jobs.wait`          | `wait`    | `systemd-jobs`     | `job.wait`                | [`sinnix://gateway/v2/actions/jobs.wait`](sinnix://gateway/v2/actions/jobs.wait)                   |
| `projects.change`    | `change`  | `projects`         | `projects.change`         | [`sinnix://gateway/v2/actions/projects.change`](sinnix://gateway/v2/actions/projects.change)       |
| `files.change`       | `change`  | `files`            | `files.change`            | [`sinnix://gateway/v2/actions/files.change`](sinnix://gateway/v2/actions/files.change)             |
| `beads.change`       | `change`  | `beads`            | `beads.write`             | [`sinnix://gateway/v2/actions/beads.change`](sinnix://gateway/v2/actions/beads.change)             |
| `beads.changeset`    | `change`  | `beads`            | `beads.changeset`         | [`sinnix://gateway/v2/actions/beads.changeset`](sinnix://gateway/v2/actions/beads.changeset)       |
| `beads.operate`      | `operate` | `beads`            | `beads.maintenance`       | [`sinnix://gateway/v2/actions/beads.operate`](sinnix://gateway/v2/actions/beads.operate)           |
| `mcp.change`         | `change`  | `mcp-broker`       | `mcp.call.write`          | [`sinnix://gateway/v2/actions/mcp.change`](sinnix://gateway/v2/actions/mcp.change)                 |
| `machine.operate`    | `operate` | `ops-reducer`      | `ops.actions.execute`     | [`sinnix://gateway/v2/actions/machine.operate`](sinnix://gateway/v2/actions/machine.operate)       |
| `operations.run`     | `run`     | `systemd-jobs`     | `job.start`               | [`sinnix://gateway/v2/actions/operations.run`](sinnix://gateway/v2/actions/operations.run)         |
| `agent.for_bead`     | `run`     | `systemd-jobs`     | `job.agent.start`         | [`sinnix://gateway/v2/actions/agent.for_bead`](sinnix://gateway/v2/actions/agent.for_bead)         |
| `jobs.cancel`        | `operate` | `systemd-jobs`     | `job.cancel`              | [`sinnix://gateway/v2/actions/jobs.cancel`](sinnix://gateway/v2/actions/jobs.cancel)               |
| `desktop.operate`    | `operate` | `desktop`          | `desktop.action`          | [`sinnix://gateway/v2/actions/desktop.operate`](sinnix://gateway/v2/actions/desktop.operate)       |
| `terminals.operate`  | `operate` | `terminals`        | `terminals.action`        | [`sinnix://gateway/v2/actions/terminals.operate`](sinnix://gateway/v2/actions/terminals.operate)   |
| `browser.operate`    | `operate` | `browser`          | `browser.action`          | [`sinnix://gateway/v2/actions/browser.operate`](sinnix://gateway/v2/actions/browser.operate)       |
| `shell.run`          | `run`     | `systemd-jobs`     | `job.shell.start`         | [`sinnix://gateway/v2/actions/shell.run`](sinnix://gateway/v2/actions/shell.run)                   |
| `projects.list`      | `query`   | `projects`         | `projects.list`           | [`sinnix://gateway/v2/actions/projects.list`](sinnix://gateway/v2/actions/projects.list)           |
| `projects.tree`      | `query`   | `projects`         | `projects.tree`           | [`sinnix://gateway/v2/actions/projects.tree`](sinnix://gateway/v2/actions/projects.tree)           |
| `projects.read`      | `query`   | `projects`         | `projects.read`           | [`sinnix://gateway/v2/actions/projects.read`](sinnix://gateway/v2/actions/projects.read)           |
| `projects.diff`      | `query`   | `projects`         | `projects.diff`           | [`sinnix://gateway/v2/actions/projects.diff`](sinnix://gateway/v2/actions/projects.diff)           |
| `machine.query`      | `query`   | `machine`          | `observe.machine_query`   | [`sinnix://gateway/v2/actions/machine.query`](sinnix://gateway/v2/actions/machine.query)           |
| `capabilities.query` | `query`   | `capability-index` | `capability_index.query`  | [`sinnix://gateway/v2/actions/capabilities.query`](sinnix://gateway/v2/actions/capabilities.query) |
| `mcp.query`          | `query`   | `mcp-broker`       | `mcp.call.read`           | [`sinnix://gateway/v2/actions/mcp.query`](sinnix://gateway/v2/actions/mcp.query)                   |
| `desktop.query`      | `query`   | `desktop`          | `desktop.read`            | [`sinnix://gateway/v2/actions/desktop.query`](sinnix://gateway/v2/actions/desktop.query)           |
| `terminals.query`    | `query`   | `terminals`        | `terminals.read`          | [`sinnix://gateway/v2/actions/terminals.query`](sinnix://gateway/v2/actions/terminals.query)       |
| `browser.query`      | `query`   | `browser`          | `browser.read`            | [`sinnix://gateway/v2/actions/browser.query`](sinnix://gateway/v2/actions/browser.query)           |
| `files.query`        | `query`   | `files`            | `files.read`              | [`sinnix://gateway/v2/actions/files.query`](sinnix://gateway/v2/actions/files.query)               |
| `sessions.query`     | `query`   | `sessions`         | `sessions.query`          | [`sinnix://gateway/v2/actions/sessions.query`](sinnix://gateway/v2/actions/sessions.query)         |
| `memory.query`       | `query`   | `memory`           | `memory.query`            | [`sinnix://gateway/v2/actions/memory.query`](sinnix://gateway/v2/actions/memory.query)             |
| `timeline.query`     | `query`   | `timeline`         | `timeline.query`          | [`sinnix://gateway/v2/actions/timeline.query`](sinnix://gateway/v2/actions/timeline.query)         |
| `artifacts.query`    | `query`   | `artifacts`        | `artifacts.query`         | [`sinnix://gateway/v2/actions/artifacts.query`](sinnix://gateway/v2/actions/artifacts.query)       |
| `audit.verify`       | `query`   | `audit`            | `audit.verify`            | [`sinnix://gateway/v2/actions/audit.verify`](sinnix://gateway/v2/actions/audit.verify)             |
| `captures.query`     | `query`   | `captures`         | `captures.query`          | [`sinnix://gateway/v2/actions/captures.query`](sinnix://gateway/v2/actions/captures.query)         |
| `jobs.query`         | `query`   | `systemd-jobs`     | `job.list`                | [`sinnix://gateway/v2/actions/jobs.query`](sinnix://gateway/v2/actions/jobs.query)                 |

### `gateway.status`

Return independent gateway contract and availability observations.

Owner route: `observe.gateway_status`. Principals: `agent-control, observer, operator`. Typed failures: `deadline, invalid_request, not_found, owner_failed, policy_denied, response_bound, unavailable`.

Input schema:

```json
{
  "additionalProperties": false,
  "properties": {
    "actor": {
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "deadline_at": {
      "type": "number"
    },
    "idempotency_key": {
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "reason": {
      "maxLength": 2000,
      "minLength": 1,
      "type": "string"
    },
    "request_id": {
      "maxLength": 128,
      "minLength": 1,
      "type": "string"
    }
  },
  "type": "object"
}
```

Examples:

```json
{}
```

### `gateway.catalog`

Search the generated V2 resource and action catalog.

Owner route: `registry.search`. Principals: `agent-control, observer, operator`. Typed failures: `deadline, invalid_request, not_found, owner_failed, policy_denied, response_bound, unavailable`.

Input schema:

```json
{
  "additionalProperties": false,
  "properties": {
    "actor": {
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "availability": {
      "enum": ["available", "unavailable"]
    },
    "deadline_at": {
      "type": "number"
    },
    "domain": {
      "maxLength": 128,
      "type": "string"
    },
    "effect": {
      "enum": ["read", "change", "operate", "run"]
    },
    "idempotency_key": {
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "project": {
      "maxLength": 128,
      "minLength": 1,
      "type": "string"
    },
    "reason": {
      "maxLength": 2000,
      "minLength": 1,
      "type": "string"
    },
    "request_id": {
      "maxLength": 128,
      "minLength": 1,
      "type": "string"
    },
    "resource_kind": {
      "maxLength": 128,
      "type": "string"
    },
    "text": {
      "maxLength": 512,
      "type": "string"
    },
    "verb": {
      "enum": [
        "status",
        "catalog",
        "query",
        "get",
        "context",
        "events",
        "wait",
        "change",
        "operate",
        "run"
      ]
    }
  },
  "type": "object"
}
```

Examples:

```json
{
  "availability": "available",
  "resource_kind": "bead"
}
```

### `resources.get`

Resolve one canonical owner-backed resource through its registered source of truth.

Owner route: `resources.get`. Principals: `agent-control, observer, operator`. Typed failures: `deadline, invalid_request, not_found, owner_failed, policy_denied, response_bound, unavailable`.

Input schema:

```json
{
  "additionalProperties": false,
  "properties": {
    "actor": {
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "as_of": {
      "maxLength": 128,
      "minLength": 1,
      "type": "string"
    },
    "deadline_at": {
      "type": "number"
    },
    "idempotency_key": {
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "includes": {
      "items": {
        "enum": [
          "blockers",
          "comments",
          "history",
          "events",
          "dependencies",
          "dependents",
          "children",
          "refs"
        ]
      },
      "maxItems": 8,
      "type": "array"
    },
    "max_bytes": {
      "default": 64000,
      "maximum": 262144,
      "minimum": 1,
      "type": "integer"
    },
    "offset": {
      "default": 0,
      "minimum": 0,
      "type": "integer"
    },
    "projection": {
      "default": "summary",
      "enum": ["summary", "log", "result"]
    },
    "reason": {
      "maxLength": 2000,
      "minLength": 1,
      "type": "string"
    },
    "ref": {
      "maxLength": 2048,
      "minLength": 1,
      "type": "string"
    },
    "request_id": {
      "maxLength": 128,
      "minLength": 1,
      "type": "string"
    }
  },
  "required": ["ref"],
  "type": "object"
}
```

Examples:

```json
{
  "ref": "sinnix://projects/sinnix"
}
```

### `projects.query`

Search one canonical project or checkout through the bounded project owner.

Owner route: `projects.search`. Principals: `agent-control, observer, operator`. Typed failures: `deadline, invalid_request, not_found, owner_failed, policy_denied, response_bound, unavailable`.

Input schema:

```json
{
  "additionalProperties": false,
  "properties": {
    "actor": {
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "deadline_at": {
      "type": "number"
    },
    "idempotency_key": {
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "max_matches": {
      "default": 200,
      "maximum": 1000,
      "minimum": 1,
      "type": "integer"
    },
    "query": {
      "maxLength": 1000,
      "minLength": 1,
      "type": "string"
    },
    "reason": {
      "maxLength": 2000,
      "minLength": 1,
      "type": "string"
    },
    "ref": {
      "maxLength": 2048,
      "minLength": 1,
      "pattern": "^sinnix://projects/[^/]+(?:/checkouts/[^/]+)?$",
      "type": "string"
    },
    "request_id": {
      "maxLength": 128,
      "minLength": 1,
      "type": "string"
    }
  },
  "required": ["ref", "query"],
  "type": "object"
}
```

Examples:

```json
{
  "max_matches": 20,
  "query": "mkServiceModule",
  "ref": "sinnix://projects/sinnix"
}
```

### `beads.query`

Query canonical project-qualified Beads resources with bounded snapshot paging and explicit coverage.

Owner route: `beads.query`. Principals: `agent-control, observer, operator`. Typed failures: `deadline, invalid_request, not_found, owner_failed, policy_denied, response_bound, unavailable`.

Input schema:

```json
{
  "additionalProperties": false,
  "properties": {
    "action_name": {
      "const": "beads.query"
    },
    "actor": {
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "deadline_at": {
      "type": "number"
    },
    "idempotency_key": {
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "parameters": {
      "additionalProperties": false,
      "properties": {
        "cursor": {
          "maxLength": 256,
          "minLength": 1,
          "type": "string"
        },
        "expression": {
          "description": "Native Beads expression. It accepts the owner query grammar, for example status=open AND priority<=1.",
          "maxLength": 4000,
          "minLength": 1,
          "type": "string"
        },
        "filters": {
          "description": "Filter AST: field=value or field={op,value}; op is one of =, !=, >, >=, <, <=. Combine non-empty nodes with and, or, or not.",
          "maxProperties": 32,
          "type": "object"
        },
        "graph": {
          "additionalProperties": false,
          "properties": {
            "bead_id": {
              "type": "string"
            },
            "depth": {
              "maximum": 20,
              "minimum": 1,
              "type": "integer"
            },
            "direction": {
              "enum": ["down", "up", "both"]
            },
            "edge_type": {
              "type": "string"
            },
            "max_rows": {
              "maximum": 1000,
              "minimum": 1,
              "type": "integer"
            },
            "mermaid": {
              "type": "boolean"
            },
            "status": {
              "type": "string"
            }
          },
          "type": "object"
        },
        "includes": {
          "items": {
            "enum": [
              "comments",
              "history",
              "events",
              "dependencies",
              "dependents",
              "children",
              "refs"
            ]
          },
          "maxItems": 8,
          "type": "array"
        },
        "limit": {
          "maximum": 200,
          "minimum": 1,
          "type": "integer"
        },
        "memory": {
          "additionalProperties": false,
          "properties": {
            "key": {
              "type": "string"
            },
            "query": {
              "type": "string"
            }
          },
          "type": "object"
        },
        "native_filters": {
          "description": "Native list filters for non-query views. Supported scalar keys include title_contains, status, priority, priority_min, priority_max, assignee, parent, type, updated_after, and updated_before; label, label_any, and exclude_label accept string lists.",
          "maxProperties": 40,
          "type": "object"
        },
        "order": {
          "additionalProperties": false,
          "properties": {
            "field": {
              "enum": [
                "priority",
                "created",
                "updated",
                "closed",
                "status",
                "id",
                "title",
                "type",
                "assignee"
              ]
            },
            "reverse": {
              "type": "boolean"
            }
          },
          "type": "object"
        },
        "project_ids": {
          "items": {
            "maxLength": 128,
            "minLength": 1,
            "type": "string"
          },
          "maxItems": 32,
          "minItems": 1,
          "type": "array"
        },
        "view": {
          "enum": [
            "query",
            "ready",
            "blocked",
            "open",
            "all",
            "recent",
            "overdue",
            "deferred",
            "unassigned",
            "stale_claims",
            "epic_progress",
            "changed_since"
          ]
        }
      },
      "type": "object"
    },
    "reason": {
      "maxLength": 2000,
      "minLength": 1,
      "type": "string"
    },
    "request_id": {
      "maxLength": 128,
      "minLength": 1,
      "type": "string"
    }
  },
  "required": ["action_name", "parameters"],
  "type": "object"
}
```

Examples:

```json
{
  "action_name": "beads.query",
  "parameters": {
    "filters": {
      "priority": {
        "op": "<=",
        "value": 1
      },
      "status": "open"
    },
    "includes": ["dependencies"],
    "limit": 50,
    "project_ids": ["polylogue"],
    "view": "query"
  }
}
```

### `projects.context`

Compose orientation, triage or incident context for one canonical project, or review one queued job.

Owner route: `project_context.context`. Principals: `agent-control, observer, operator`. Typed failures: `deadline, invalid_request, not_found, owner_failed, policy_denied, response_bound, unavailable`.

Input schema:

```json
{
  "additionalProperties": false,
  "properties": {
    "actor": {
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "deadline_at": {
      "type": "number"
    },
    "idempotency_key": {
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "intent": {
      "default": "project.orientation",
      "enum": [
        "project",
        "project.orientation",
        "project.triage",
        "job.review",
        "incident"
      ]
    },
    "reason": {
      "maxLength": 2000,
      "minLength": 1,
      "type": "string"
    },
    "ref": {
      "maxLength": 2048,
      "minLength": 1,
      "pattern": "^sinnix://(?:projects/[^/]+(?:/checkouts/[^/]+)?|jobs/[^/]+)$",
      "type": "string"
    },
    "request_id": {
      "maxLength": 128,
      "minLength": 1,
      "type": "string"
    }
  },
  "required": ["ref"],
  "type": "object"
}
```

Examples:

```json
{
  "ref": "sinnix://projects/sinnix"
}
```

### `audit.events`

Read bounded audit events visible to the active principal.

Owner route: `audit.tail`. Principals: `agent-control, observer, operator`. Typed failures: `deadline, invalid_request, not_found, owner_failed, policy_denied, response_bound, unavailable`.

Input schema:

```json
{
  "additionalProperties": false,
  "properties": {
    "actor": {
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "cursor": {
      "maxLength": 4096,
      "minLength": 1,
      "type": "string"
    },
    "deadline_at": {
      "type": "number"
    },
    "idempotency_key": {
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "limit": {
      "default": 100,
      "maximum": 1000,
      "minimum": 1,
      "type": "integer"
    },
    "project_ids": {
      "items": {
        "maxLength": 128,
        "minLength": 1,
        "type": "string"
      },
      "maxItems": 16,
      "type": "array"
    },
    "reason": {
      "maxLength": 2000,
      "minLength": 1,
      "type": "string"
    },
    "request_id": {
      "maxLength": 128,
      "minLength": 1,
      "type": "string"
    }
  },
  "type": "object"
}
```

Examples:

```json
{
  "limit": 100
}
```

### `jobs.wait`

Wait for a bounded interval on one queued job reference.

Owner route: `job.wait`. Principals: `agent-control, observer, operator`. Typed failures: `deadline, invalid_request, not_found, owner_failed, policy_denied, response_bound, unavailable`.

Input schema:

```json
{
  "additionalProperties": false,
  "properties": {
    "actor": {
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "deadline_at": {
      "type": "number"
    },
    "expected": {
      "maxProperties": 8,
      "type": "object"
    },
    "idempotency_key": {
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "poll_seconds": {
      "default": 0.25,
      "maximum": 5,
      "minimum": 0.01,
      "type": "number"
    },
    "reason": {
      "maxLength": 2000,
      "minLength": 1,
      "type": "string"
    },
    "ref": {
      "maxLength": 2048,
      "minLength": 1,
      "pattern": "^sinnix://jobs/[^/]+$",
      "type": "string"
    },
    "request_id": {
      "maxLength": 128,
      "minLength": 1,
      "type": "string"
    },
    "target": {
      "default": "job_terminal",
      "enum": [
        "job_terminal",
        "bead_status",
        "bead_revision",
        "unit_state",
        "file_hash",
        "capture_freshness",
        "receipt_appearance"
      ]
    },
    "timeout_seconds": {
      "default": 30,
      "maximum": 300,
      "minimum": 1,
      "type": "integer"
    }
  },
  "required": ["ref"],
  "type": "object"
}
```

Examples:

```json
{
  "ref": "sinnix://jobs/3b0237a0-32a9-4f6b-a014-2a0ecfd2f75c",
  "timeout_seconds": 30
}
```

### `projects.change`

Apply one bounded, precondition-checked project write or patch through a canonical project or checkout reference.

Owner route: `projects.change`. Principals: `operator`. Typed failures: `conflict, deadline, idempotency_conflict, invalid_request, not_found, owner_failed, policy_denied, precondition_failed, response_bound, unavailable, unsupported_capability`.

Input schema:

```json
{
  "additionalProperties": false,
  "properties": {
    "actor": {
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "deadline_at": {
      "type": "number"
    },
    "idempotency_key": {
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "operation": {
      "enum": ["apply_patch", "write"]
    },
    "parameters": {
      "maxProperties": 32,
      "type": "object"
    },
    "preconditions": {
      "additionalProperties": false,
      "properties": {
        "dirty_sha256": {
          "pattern": "^[0-9a-f]{64}$",
          "type": "string"
        },
        "head": {
          "pattern": "^[0-9a-f]{40,64}$",
          "type": "string"
        }
      },
      "type": "object"
    },
    "reason": {
      "maxLength": 2000,
      "minLength": 1,
      "type": "string"
    },
    "ref": {
      "maxLength": 8192,
      "minLength": 1,
      "pattern": "^sinnix://projects/[^/]+(?:/checkouts/[^/]+)?$",
      "type": "string"
    },
    "request_id": {
      "maxLength": 128,
      "minLength": 1,
      "type": "string"
    }
  },
  "required": ["ref", "operation", "parameters", "idempotency_key"],
  "type": "object"
}
```

Examples:

```json
{
  "idempotency_key": "project-write-example",
  "operation": "write",
  "parameters": {
    "content": "updated content\\n",
    "path": "README.md"
  },
  "preconditions": {
    "head": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
  },
  "ref": "sinnix://projects/sinnix/checkouts/default"
}
```

### `files.change`

Apply one bounded host-file mutation through an opaque canonical file reference.

Owner route: `files.change`. Principals: `operator`. Typed failures: `conflict, deadline, idempotency_conflict, invalid_request, not_found, owner_failed, policy_denied, precondition_failed, response_bound, unavailable`.

Input schema:

```json
{
  "additionalProperties": false,
  "properties": {
    "actor": {
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "deadline_at": {
      "type": "number"
    },
    "idempotency_key": {
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "operation": {
      "enum": ["append", "copy", "mkdir", "move", "remove", "replace"]
    },
    "parameters": {
      "maxProperties": 32,
      "type": "object"
    },
    "preconditions": {
      "additionalProperties": false,
      "properties": {
        "expected_sha256": {
          "pattern": "^[0-9a-f]{64}$",
          "type": "string"
        }
      },
      "type": "object"
    },
    "reason": {
      "maxLength": 2000,
      "minLength": 1,
      "type": "string"
    },
    "ref": {
      "maxLength": 8192,
      "minLength": 1,
      "pattern": "^sinnix://files/[A-Za-z0-9_-]{1,8192}$",
      "type": "string"
    },
    "request_id": {
      "maxLength": 128,
      "minLength": 1,
      "type": "string"
    }
  },
  "required": ["ref", "operation", "parameters", "idempotency_key"],
  "type": "object"
}
```

Examples:

```json
{
  "idempotency_key": "file-replace-example",
  "operation": "replace",
  "parameters": {
    "content": "updated content\\n"
  },
  "ref": "sinnix://files/L3JlYWxtL3RtcC9maWxl"
}
```

### `beads.change`

Perform one structured, attested Beads mutation for a canonical project.

Owner route: `beads.write`. Principals: `operator`. Typed failures: `conflict, deadline, idempotency_conflict, invalid_request, not_found, owner_failed, policy_denied, precondition_failed, response_bound, unavailable`.

Input schema:

```json
{
  "additionalProperties": false,
  "properties": {
    "actor": {
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "deadline_at": {
      "type": "number"
    },
    "idempotency_key": {
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "operation": {
      "enum": [
        "claim",
        "close",
        "comment",
        "create",
        "dependency.add",
        "dependency.remove",
        "memory.forget",
        "memory.remember",
        "graph.create",
        "relate",
        "reopen",
        "unclaim",
        "unrelate",
        "update",
        "reparent"
      ]
    },
    "parameters": {
      "additionalProperties": false,
      "properties": {
        "code_revision": {
          "pattern": "^[0-9a-f]{40,64}$",
          "type": "string"
        },
        "depends_on": {
          "maxLength": 128,
          "type": "string"
        },
        "evidence_refs": {
          "items": {
            "pattern": "^sinnix://",
            "type": "string"
          },
          "maxItems": 32,
          "minItems": 1,
          "type": "array"
        },
        "force": {
          "const": true,
          "type": "boolean"
        },
        "graph": {
          "maxProperties": 256,
          "type": "object"
        },
        "id": {
          "maxLength": 128,
          "minLength": 1,
          "type": "string"
        },
        "job_ref": {
          "pattern": "^sinnix://jobs/[^/]+$",
          "type": "string"
        },
        "key": {
          "maxLength": 256,
          "type": "string"
        },
        "mode": {
          "enum": ["preview", "apply"]
        },
        "other_id": {
          "maxLength": 128,
          "type": "string"
        },
        "parent_id": {
          "maxLength": 128,
          "type": "string"
        },
        "patch": {
          "additionalProperties": false,
          "properties": {
            "labels": {
              "additionalProperties": false,
              "properties": {
                "add": {
                  "items": {
                    "type": "string"
                  },
                  "type": "array"
                },
                "remove": {
                  "items": {
                    "type": "string"
                  },
                  "type": "array"
                },
                "replace": {
                  "items": {
                    "type": "string"
                  },
                  "type": "array"
                }
              },
              "type": "object"
            },
            "metadata": {
              "additionalProperties": false,
              "properties": {
                "set": {
                  "type": "object"
                },
                "unset": {
                  "items": {
                    "type": "string"
                  },
                  "type": "array"
                }
              },
              "type": "object"
            },
            "notes": {
              "additionalProperties": false,
              "properties": {
                "mode": {
                  "enum": ["append", "replace"]
                },
                "text": {
                  "maxLength": 32000,
                  "type": "string"
                }
              },
              "required": ["text"],
              "type": "object"
            },
            "set": {
              "type": "object"
            },
            "unset": {
              "items": {
                "enum": ["due", "defer", "parent"]
              },
              "type": "array"
            }
          },
          "type": "object"
        },
        "preview_digest": {
          "pattern": "^[0-9a-f]{64}$",
          "type": "string"
        },
        "reason": {
          "maxLength": 32000,
          "type": "string"
        },
        "residuals": {
          "items": {
            "maxLength": 2000,
            "type": "string"
          },
          "maxItems": 32,
          "type": "array"
        },
        "task_etag": {
          "pattern": "^[0-9a-f]{64}$",
          "type": "string"
        },
        "task_revision": {
          "pattern": "^[0-9a-f]{64}$",
          "type": "string"
        },
        "text": {
          "maxLength": 32000,
          "type": "string"
        },
        "title": {
          "maxLength": 512,
          "type": "string"
        },
        "type": {
          "maxLength": 64,
          "type": "string"
        },
        "verdict": {
          "enum": ["accepted", "rejected", "partial"]
        }
      },
      "type": "object"
    },
    "preconditions": {
      "additionalProperties": false,
      "properties": {
        "expected_assignee": {
          "maxLength": 256,
          "type": ["string", "null"]
        },
        "expected_etag": {
          "pattern": "^[0-9a-f]{64}$",
          "type": "string"
        },
        "expected_status": {
          "maxLength": 64,
          "type": "string"
        },
        "expected_task_revision": {
          "pattern": "^[0-9a-f]{64}$",
          "type": "string"
        }
      },
      "type": "object"
    },
    "reason": {
      "maxLength": 2000,
      "minLength": 1,
      "type": "string"
    },
    "ref": {
      "maxLength": 8192,
      "minLength": 1,
      "pattern": "^sinnix://projects/[^/]+(?:/beads/[^/]+)?$",
      "type": "string"
    },
    "request_id": {
      "maxLength": 128,
      "minLength": 1,
      "type": "string"
    }
  },
  "required": ["ref", "operation", "parameters", "idempotency_key"],
  "type": "object"
}
```

Examples:

```json
{
  "idempotency_key": "bead-comment-example",
  "operation": "comment",
  "parameters": {
    "id": "sinnix-example",
    "text": "recorded by the operator"
  },
  "ref": "sinnix://projects/sinnix"
}
```

### `beads.changeset`

Preview or apply an ordered, project-partitioned Beads changeset with explicit step outcomes and no global rollback claim.

Owner route: `beads.changeset`. Principals: `operator`. Typed failures: `conflict, deadline, idempotency_conflict, invalid_request, not_found, owner_failed, policy_denied, precondition_failed, response_bound, unavailable`.

Input schema:

```json
{
  "additionalProperties": false,
  "properties": {
    "actor": {
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "deadline_at": {
      "type": "number"
    },
    "idempotency_key": {
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "operation": {
      "enum": ["apply", "preview"]
    },
    "parameters": {
      "additionalProperties": false,
      "properties": {
        "actions": {
          "items": {
            "additionalProperties": false,
            "properties": {
              "bind": {
                "maxLength": 64,
                "minLength": 1,
                "pattern": "^[A-Za-z][A-Za-z0-9_]{0,63}$",
                "type": "string"
              },
              "operation": {
                "enum": [
                  "claim",
                  "close",
                  "comment",
                  "create",
                  "dependency.add",
                  "dependency.remove",
                  "memory.forget",
                  "memory.remember",
                  "graph.create",
                  "relate",
                  "reopen",
                  "unclaim",
                  "unrelate",
                  "update",
                  "reparent"
                ]
              },
              "parameters": {
                "maxProperties": 32,
                "type": "object"
              },
              "preconditions": {
                "additionalProperties": false,
                "properties": {
                  "expected_assignee": {
                    "maxLength": 256,
                    "type": ["string", "null"]
                  },
                  "expected_etag": {
                    "pattern": "^[0-9a-f]{64}$",
                    "type": "string"
                  },
                  "expected_status": {
                    "maxLength": 64,
                    "type": "string"
                  },
                  "expected_task_revision": {
                    "pattern": "^[0-9a-f]{64}$",
                    "type": "string"
                  }
                },
                "type": "object"
              },
              "ref": {
                "maxLength": 8192,
                "minLength": 1,
                "pattern": "^sinnix://projects/[^/]+(?:/beads/[^/]+)?$",
                "type": "string"
              }
            },
            "required": ["ref", "operation", "parameters"],
            "type": "object"
          },
          "maxItems": 128,
          "minItems": 1,
          "type": "array"
        },
        "on_error": {
          "enum": ["stop", "continue"]
        },
        "preview_digest": {
          "pattern": "^[0-9a-f]{64}$",
          "type": "string"
        }
      },
      "required": ["actions"],
      "type": "object"
    },
    "preconditions": {
      "type": "object"
    },
    "reason": {
      "maxLength": 2000,
      "minLength": 1,
      "type": "string"
    },
    "ref": {
      "maxLength": 8192,
      "minLength": 1,
      "pattern": "^sinnix://projects/[^/]+$",
      "type": "string"
    },
    "request_id": {
      "maxLength": 128,
      "minLength": 1,
      "type": "string"
    }
  },
  "required": ["ref", "operation", "parameters", "idempotency_key"],
  "type": "object"
}
```

Examples:

```json
{
  "idempotency_key": "beads-changeset-example",
  "operation": "preview",
  "parameters": {
    "actions": [
      {
        "bind": "parent",
        "operation": "create",
        "parameters": {
          "title": "parent"
        },
        "ref": "sinnix://projects/sinnix"
      },
      {
        "operation": "create",
        "parameters": {
          "parent": "$parent",
          "title": "child"
        },
        "ref": "sinnix://projects/sinnix"
      }
    ]
  },
  "ref": "sinnix://projects/sinnix"
}
```

### `beads.operate`

Run one explicit Beads publication, Dolt sync, or supported backup operation. Ordinary mutations do not publish JSONL or create Git commits.

Owner route: `beads.maintenance`. Principals: `operator`. Typed failures: `conflict, deadline, idempotency_conflict, invalid_request, not_found, owner_failed, policy_denied, response_bound, unavailable`.

Input schema:

```json
{
  "additionalProperties": false,
  "properties": {
    "actor": {
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "deadline_at": {
      "type": "number"
    },
    "idempotency_key": {
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "operation": {
      "enum": [
        "backup.create",
        "backup.list",
        "backup.restore",
        "snapshot.publish",
        "sync.pull",
        "sync.push"
      ]
    },
    "parameters": {
      "additionalProperties": false,
      "properties": {
        "backup_id": {
          "maxLength": 256,
          "minLength": 1,
          "type": "string"
        }
      },
      "type": "object"
    },
    "reason": {
      "maxLength": 2000,
      "minLength": 1,
      "type": "string"
    },
    "ref": {
      "maxLength": 8192,
      "minLength": 1,
      "pattern": "^sinnix://projects/[^/]+$",
      "type": "string"
    },
    "request_id": {
      "maxLength": 128,
      "minLength": 1,
      "type": "string"
    }
  },
  "required": ["ref", "operation", "parameters", "idempotency_key"],
  "type": "object"
}
```

Examples:

```json
{
  "idempotency_key": "beads-publish-example",
  "operation": "snapshot.publish",
  "parameters": {},
  "ref": "sinnix://projects/sinnix"
}
```

### `mcp.change`

Call one brokered upstream MCP tool whose live metadata does not declare it read-only.

Owner route: `mcp.call.write`. Principals: `operator`. Typed failures: `conflict, deadline, idempotency_conflict, invalid_request, not_found, owner_failed, policy_denied, response_bound, unavailable, unsupported_capability`.

Input schema:

```json
{
  "additionalProperties": false,
  "properties": {
    "actor": {
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "deadline_at": {
      "type": "number"
    },
    "idempotency_key": {
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "operation": {
      "enum": ["call"]
    },
    "parameters": {
      "maxProperties": 32,
      "type": "object"
    },
    "reason": {
      "maxLength": 2000,
      "minLength": 1,
      "type": "string"
    },
    "ref": {
      "maxLength": 8192,
      "minLength": 1,
      "pattern": "^sinnix://mcp/[^/]+/tools/[^/]+$",
      "type": "string"
    },
    "request_id": {
      "maxLength": 128,
      "minLength": 1,
      "type": "string"
    }
  },
  "required": ["ref", "operation", "parameters", "idempotency_key"],
  "type": "object"
}
```

Examples:

```json
{
  "idempotency_key": "mcp-refresh-example",
  "operation": "call",
  "parameters": {},
  "ref": "sinnix://mcp/lynchpin/tools/refresh"
}
```

### `machine.operate`

Submit one revision-checked ops-reducer action against a canonical attested target reference.

Owner route: `ops.actions.execute`. Principals: `operator`. Typed failures: `conflict, deadline, idempotency_conflict, invalid_request, not_found, owner_failed, policy_denied, precondition_failed, response_bound, unavailable`.

Input schema:

```json
{
  "additionalProperties": false,
  "properties": {
    "action": {
      "enum": [
        "interrupt",
        "freeze",
        "thaw",
        "reset_policy",
        "set_policy",
        "park",
        "rebuild_override",
        "restart",
        "start",
        "stop"
      ]
    },
    "actor": {
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "deadline_at": {
      "type": "number"
    },
    "idempotency_key": {
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "parameters": {
      "type": "object"
    },
    "preconditions": {
      "additionalProperties": false,
      "properties": {
        "expected_revision": {
          "minimum": 0,
          "type": "integer"
        }
      },
      "required": ["expected_revision"],
      "type": "object"
    },
    "reason": {
      "maxLength": 2000,
      "minLength": 1,
      "type": "string"
    },
    "ref": {
      "maxLength": 2048,
      "minLength": 1,
      "pattern": "^sinnix://(?:jobs|machine|processes)/",
      "type": "string"
    },
    "request_id": {
      "maxLength": 128,
      "minLength": 1,
      "type": "string"
    }
  },
  "required": [
    "ref",
    "action",
    "parameters",
    "reason",
    "idempotency_key",
    "preconditions"
  ],
  "type": "object"
}
```

Examples:

```json
{
  "action": "restart",
  "idempotency_key": "restart-example",
  "parameters": {},
  "preconditions": {
    "expected_revision": 42
  },
  "reason": "apply the approved restart",
  "ref": "sinnix://machine/units/user/example.service"
}
```

### `operations.run`

Queue one project-declared operation in its declared pool, on the main checkout or a worktree.

Owner route: `job.start`. Principals: `agent-control, operator`. Typed failures: `conflict, deadline, idempotency_conflict, invalid_request, not_found, owner_failed, policy_denied, response_bound, unavailable`.

Input schema:

```json
{
  "additionalProperties": false,
  "properties": {
    "actor": {
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "deadline_at": {
      "type": "number"
    },
    "idempotency_key": {
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "operation": {
      "maxLength": 128,
      "minLength": 1,
      "type": "string"
    },
    "parameters": {
      "default": {},
      "maxProperties": 16,
      "type": "object"
    },
    "project_id": {
      "maxLength": 128,
      "minLength": 1,
      "type": "string"
    },
    "reason": {
      "maxLength": 2000,
      "minLength": 1,
      "type": "string"
    },
    "request_id": {
      "maxLength": 128,
      "minLength": 1,
      "type": "string"
    },
    "workspace_id": {
      "maxLength": 128,
      "minLength": 1,
      "type": "string"
    }
  },
  "required": ["project_id", "operation", "idempotency_key"],
  "type": "object"
}
```

Examples:

```json
{
  "idempotency_key": "declared-check-example",
  "operation": "check",
  "parameters": {},
  "project_id": "sinnix"
}
```

### `agent.for_bead`

Start a lane for one canonical Beads task: agentctl compiles the prompt, creates the worktree and queues the agent; the bead's model policy applies unless backend, model and effort are given.

Owner route: `job.agent.start`. Principals: `agent-control, operator`. Typed failures: `conflict, deadline, idempotency_conflict, invalid_request, not_found, owner_failed, policy_denied, response_bound, unavailable`.

Input schema:

```json
{
  "additionalProperties": false,
  "properties": {
    "actor": {
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "backend": {
      "enum": ["claude", "codex", "gemini", "grok", "antigravity"]
    },
    "deadline_at": {
      "type": "number"
    },
    "idempotency_key": {
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "model": {
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "reason": {
      "maxLength": 2000,
      "minLength": 1,
      "type": "string"
    },
    "reasoning_effort": {
      "maxLength": 32,
      "minLength": 1,
      "type": "string"
    },
    "ref": {
      "maxLength": 2048,
      "minLength": 1,
      "pattern": "^sinnix://projects/[^/]+/beads/[^/]+$",
      "type": "string"
    },
    "request_id": {
      "maxLength": 128,
      "minLength": 1,
      "type": "string"
    }
  },
  "required": ["ref", "idempotency_key"],
  "type": "object"
}
```

Examples:

```json
{
  "backend": "codex",
  "idempotency_key": "bead-agent-example",
  "model": "gpt-5.6-terra",
  "reasoning_effort": "high",
  "ref": "sinnix://projects/sinnix/beads/sinnix-example"
}
```

### `jobs.cancel`

Kill one phase-checked queued job and return the queue's answer without asserting terminal completion.

Owner route: `job.cancel`. Principals: `agent-control, operator`. Typed failures: `conflict, deadline, idempotency_conflict, invalid_request, not_found, owner_failed, policy_denied, precondition_failed, response_bound, unavailable`.

Input schema:

```json
{
  "additionalProperties": false,
  "properties": {
    "actor": {
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "deadline_at": {
      "type": "number"
    },
    "idempotency_key": {
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "preconditions": {
      "additionalProperties": false,
      "properties": {
        "expected_phase": {
          "maxLength": 128,
          "minLength": 1,
          "type": "string"
        }
      },
      "required": ["expected_phase"],
      "type": "object"
    },
    "reason": {
      "maxLength": 2000,
      "minLength": 1,
      "type": "string"
    },
    "ref": {
      "maxLength": 2048,
      "minLength": 1,
      "pattern": "^sinnix://jobs/[^/]+$",
      "type": "string"
    },
    "request_id": {
      "maxLength": 128,
      "minLength": 1,
      "type": "string"
    }
  },
  "required": ["ref", "idempotency_key", "preconditions"],
  "type": "object"
}
```

Examples:

```json
{
  "idempotency_key": "cancel-example",
  "preconditions": {
    "expected_phase": "running"
  },
  "ref": "sinnix://jobs/3b0237a0-32a9-4f6b-a014-2a0ecfd2f75c"
}
```

### `desktop.operate`

Operate the current desktop through the declared Hyprland owner route.

Owner route: `desktop.action`. Principals: `operator`. Typed failures: `conflict, deadline, idempotency_conflict, invalid_request, not_found, owner_failed, policy_denied, response_bound, unavailable`.

Input schema:

```json
{
  "additionalProperties": false,
  "properties": {
    "actor": {
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "deadline_at": {
      "type": "number"
    },
    "idempotency_key": {
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "operation": {
      "enum": [
        "dispatch",
        "focus_window",
        "keyword",
        "paste",
        "send_keystate",
        "send_shortcut"
      ]
    },
    "parameters": {
      "maxProperties": 32,
      "type": "object"
    },
    "reason": {
      "maxLength": 2000,
      "minLength": 1,
      "type": "string"
    },
    "ref": {
      "maxLength": 8192,
      "minLength": 1,
      "pattern": "^sinnix://desktop/current$",
      "type": "string"
    },
    "request_id": {
      "maxLength": 128,
      "minLength": 1,
      "type": "string"
    }
  },
  "required": ["ref", "operation", "parameters", "idempotency_key"],
  "type": "object"
}
```

Examples:

```json
{
  "idempotency_key": "desktop-focus-example",
  "operation": "focus_window",
  "parameters": {
    "window": "address:0xfixture"
  },
  "ref": "sinnix://desktop/current"
}
```

### `terminals.operate`

Operate one canonical Kitty terminal without accepting an arbitrary matcher.

Owner route: `terminals.action`. Principals: `operator`. Typed failures: `conflict, deadline, idempotency_conflict, invalid_request, not_found, owner_failed, policy_denied, response_bound, unavailable`.

Input schema:

```json
{
  "additionalProperties": false,
  "properties": {
    "actor": {
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "deadline_at": {
      "type": "number"
    },
    "idempotency_key": {
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "operation": {
      "enum": ["focus", "key", "run", "send"]
    },
    "parameters": {
      "maxProperties": 32,
      "type": "object"
    },
    "reason": {
      "maxLength": 2000,
      "minLength": 1,
      "type": "string"
    },
    "ref": {
      "maxLength": 8192,
      "minLength": 1,
      "pattern": "^sinnix://terminals/[^/]+$",
      "type": "string"
    },
    "request_id": {
      "maxLength": 128,
      "minLength": 1,
      "type": "string"
    }
  },
  "required": ["ref", "operation", "parameters", "idempotency_key"],
  "type": "object"
}
```

Examples:

```json
{
  "idempotency_key": "terminal-send-example",
  "operation": "send",
  "parameters": {
    "enter": true,
    "text": "printf fixture"
  },
  "ref": "sinnix://terminals/7"
}
```

### `browser.operate`

Create or operate only a gateway-owned browser target on the hidden agent workspace.

Owner route: `browser.action`. Principals: `operator`. Typed failures: `conflict, deadline, idempotency_conflict, invalid_request, not_found, owner_failed, policy_denied, response_bound, unavailable`.

Input schema:

```json
{
  "additionalProperties": false,
  "properties": {
    "actor": {
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "deadline_at": {
      "type": "number"
    },
    "idempotency_key": {
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "operation": {
      "enum": [
        "agent_window",
        "await",
        "click",
        "close",
        "evaluate",
        "fill_form",
        "inject_text",
        "navigate",
        "reload",
        "wait_selector"
      ]
    },
    "parameters": {
      "maxProperties": 32,
      "type": "object"
    },
    "reason": {
      "maxLength": 2000,
      "minLength": 1,
      "type": "string"
    },
    "ref": {
      "maxLength": 8192,
      "minLength": 1,
      "pattern": "^sinnix://browser/(?:agent-workspace|pages/[^/]+)$",
      "type": "string"
    },
    "request_id": {
      "maxLength": 128,
      "minLength": 1,
      "type": "string"
    }
  },
  "required": ["ref", "operation", "parameters", "idempotency_key"],
  "type": "object"
}
```

Examples:

```json
{
  "idempotency_key": "browser-window-example",
  "operation": "agent_window",
  "parameters": {
    "url": "https://example.test"
  },
  "ref": "sinnix://browser/agent-workspace"
}
```

### `shell.run`

Queue one argv in the interactive pool inside a checkout's declared environment and return its job handle.

Owner route: `job.shell.start`. Principals: `operator`. Typed failures: `conflict, deadline, idempotency_conflict, invalid_request, not_found, owner_failed, policy_denied, response_bound, unavailable`.

Input schema:

```json
{
  "additionalProperties": false,
  "properties": {
    "actor": {
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "argv": {
      "items": {
        "maxLength": 32768,
        "minLength": 1,
        "type": "string"
      },
      "maxItems": 128,
      "minItems": 1,
      "type": "array"
    },
    "checkout_id": {
      "maxLength": 128,
      "minLength": 1,
      "type": "string"
    },
    "cwd": {
      "default": ".",
      "maxLength": 4096,
      "minLength": 1,
      "type": "string"
    },
    "deadline_at": {
      "type": "number"
    },
    "idempotency_key": {
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "project_id": {
      "maxLength": 128,
      "minLength": 1,
      "type": "string"
    },
    "reason": {
      "maxLength": 2000,
      "minLength": 1,
      "type": "string"
    },
    "request_id": {
      "maxLength": 128,
      "minLength": 1,
      "type": "string"
    },
    "timeout_seconds": {
      "default": 3600,
      "maximum": 3600,
      "minimum": 1,
      "type": "integer"
    }
  },
  "required": ["project_id", "checkout_id", "argv", "idempotency_key"],
  "type": "object"
}
```

Examples:

```json
{
  "argv": ["git", "status", "--short"],
  "checkout_id": "default",
  "cwd": ".",
  "idempotency_key": "shell-status-example",
  "project_id": "sinnix",
  "timeout_seconds": 300
}
```

### `projects.list`

List principal-visible projects without host paths.

Owner route: `projects.list`. Principals: `agent-control, observer, operator`. Typed failures: `deadline, invalid_request, not_found, owner_failed, policy_denied, response_bound, unavailable`.

Input schema:

```json
{
  "additionalProperties": false,
  "properties": {
    "actor": {
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "deadline_at": {
      "type": "number"
    },
    "idempotency_key": {
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "parameters": {
      "additionalProperties": true,
      "type": "object"
    },
    "reason": {
      "maxLength": 2000,
      "minLength": 1,
      "type": "string"
    },
    "ref": {
      "maxLength": 2048,
      "minLength": 1,
      "type": "string"
    },
    "request_id": {
      "maxLength": 128,
      "minLength": 1,
      "type": "string"
    }
  },
  "type": "object"
}
```

Examples:

No example is declared. Discover the live schema before invoking this action.

### `projects.tree`

List a bounded canonical project tree without following symlinks.

Owner route: `projects.tree`. Principals: `agent-control, observer, operator`. Typed failures: `deadline, invalid_request, not_found, owner_failed, policy_denied, response_bound, unavailable`.

Input schema:

```json
{
  "additionalProperties": false,
  "properties": {
    "actor": {
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "deadline_at": {
      "type": "number"
    },
    "idempotency_key": {
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "parameters": {
      "additionalProperties": true,
      "type": "object"
    },
    "reason": {
      "maxLength": 2000,
      "minLength": 1,
      "type": "string"
    },
    "ref": {
      "maxLength": 2048,
      "minLength": 1,
      "type": "string"
    },
    "request_id": {
      "maxLength": 128,
      "minLength": 1,
      "type": "string"
    }
  },
  "type": "object"
}
```

Examples:

No example is declared. Discover the live schema before invoking this action.

### `projects.read`

Read a bounded project file through a canonical project or checkout ref.

Owner route: `projects.read`. Principals: `agent-control, observer, operator`. Typed failures: `deadline, invalid_request, not_found, owner_failed, policy_denied, response_bound, unavailable`.

Input schema:

```json
{
  "additionalProperties": false,
  "properties": {
    "actor": {
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "deadline_at": {
      "type": "number"
    },
    "idempotency_key": {
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "parameters": {
      "additionalProperties": true,
      "type": "object"
    },
    "reason": {
      "maxLength": 2000,
      "minLength": 1,
      "type": "string"
    },
    "ref": {
      "maxLength": 2048,
      "minLength": 1,
      "type": "string"
    },
    "request_id": {
      "maxLength": 128,
      "minLength": 1,
      "type": "string"
    }
  },
  "type": "object"
}
```

Examples:

No example is declared. Discover the live schema before invoking this action.

### `projects.diff`

Read a bounded Git diff through a canonical project or checkout ref.

Owner route: `projects.diff`. Principals: `agent-control, observer, operator`. Typed failures: `deadline, invalid_request, not_found, owner_failed, policy_denied, response_bound, unavailable`.

Input schema:

```json
{
  "additionalProperties": false,
  "properties": {
    "actor": {
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "deadline_at": {
      "type": "number"
    },
    "idempotency_key": {
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "parameters": {
      "additionalProperties": true,
      "type": "object"
    },
    "reason": {
      "maxLength": 2000,
      "minLength": 1,
      "type": "string"
    },
    "ref": {
      "maxLength": 2048,
      "minLength": 1,
      "type": "string"
    },
    "request_id": {
      "maxLength": 128,
      "minLength": 1,
      "type": "string"
    }
  },
  "type": "object"
}
```

Examples:

No example is declared. Discover the live schema before invoking this action.

### `machine.query`

Read one bounded, provenance-carrying machine section; operation=actions returns the authoritative revision required by machine.operate.

Owner route: `observe.machine_query`. Principals: `agent-control, observer, operator`. Typed failures: `deadline, invalid_request, not_found, owner_failed, policy_denied, response_bound, unavailable`.

Input schema:

```json
{
  "additionalProperties": false,
  "properties": {
    "actor": {
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "deadline_at": {
      "type": "number"
    },
    "idempotency_key": {
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "parameters": {
      "additionalProperties": true,
      "type": "object"
    },
    "reason": {
      "maxLength": 2000,
      "minLength": 1,
      "type": "string"
    },
    "ref": {
      "maxLength": 2048,
      "minLength": 1,
      "type": "string"
    },
    "request_id": {
      "maxLength": 128,
      "minLength": 1,
      "type": "string"
    }
  },
  "type": "object"
}
```

Examples:

No example is declared. Discover the live schema before invoking this action.

### `capabilities.query`

Search or exactly describe generated machine capabilities.

Owner route: `capability_index.query`. Principals: `agent-control, observer, operator`. Typed failures: `deadline, invalid_request, not_found, owner_failed, policy_denied, response_bound, unavailable`.

Input schema:

```json
{
  "additionalProperties": false,
  "properties": {
    "actor": {
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "deadline_at": {
      "type": "number"
    },
    "idempotency_key": {
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "parameters": {
      "additionalProperties": true,
      "type": "object"
    },
    "reason": {
      "maxLength": 2000,
      "minLength": 1,
      "type": "string"
    },
    "ref": {
      "maxLength": 2048,
      "minLength": 1,
      "type": "string"
    },
    "request_id": {
      "maxLength": 128,
      "minLength": 1,
      "type": "string"
    }
  },
  "type": "object"
}
```

Examples:

No example is declared. Discover the live schema before invoking this action.

### `mcp.query`

Discover brokered MCP servers or invoke a declared read-only upstream tool.

Owner route: `mcp.call.read`. Principals: `observer, operator`. Typed failures: `deadline, invalid_request, not_found, owner_failed, policy_denied, response_bound, unavailable, unsupported_capability`.

Input schema:

```json
{
  "additionalProperties": false,
  "properties": {
    "actor": {
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "deadline_at": {
      "type": "number"
    },
    "idempotency_key": {
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "parameters": {
      "additionalProperties": true,
      "type": "object"
    },
    "reason": {
      "maxLength": 2000,
      "minLength": 1,
      "type": "string"
    },
    "ref": {
      "maxLength": 2048,
      "minLength": 1,
      "type": "string"
    },
    "request_id": {
      "maxLength": 128,
      "minLength": 1,
      "type": "string"
    }
  },
  "type": "object"
}
```

Examples:

No example is declared. Discover the live schema before invoking this action.

### `desktop.query`

Read desktop state or capture output without changing focus.

Owner route: `desktop.read`. Principals: `observer, operator`. Typed failures: `deadline, invalid_request, not_found, owner_failed, policy_denied, response_bound, unavailable`.

Input schema:

```json
{
  "additionalProperties": false,
  "properties": {
    "actor": {
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "deadline_at": {
      "type": "number"
    },
    "idempotency_key": {
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "parameters": {
      "additionalProperties": true,
      "type": "object"
    },
    "reason": {
      "maxLength": 2000,
      "minLength": 1,
      "type": "string"
    },
    "ref": {
      "maxLength": 2048,
      "minLength": 1,
      "type": "string"
    },
    "request_id": {
      "maxLength": 128,
      "minLength": 1,
      "type": "string"
    }
  },
  "type": "object"
}
```

Examples:

No example is declared. Discover the live schema before invoking this action.

### `terminals.query`

List terminals or read bounded terminal evidence.

Owner route: `terminals.read`. Principals: `observer, operator`. Typed failures: `deadline, invalid_request, not_found, owner_failed, policy_denied, response_bound, unavailable`.

Input schema:

```json
{
  "additionalProperties": false,
  "properties": {
    "actor": {
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "deadline_at": {
      "type": "number"
    },
    "idempotency_key": {
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "parameters": {
      "additionalProperties": true,
      "type": "object"
    },
    "reason": {
      "maxLength": 2000,
      "minLength": 1,
      "type": "string"
    },
    "ref": {
      "maxLength": 2048,
      "minLength": 1,
      "type": "string"
    },
    "request_id": {
      "maxLength": 128,
      "minLength": 1,
      "type": "string"
    }
  },
  "type": "object"
}
```

Examples:

No example is declared. Discover the live schema before invoking this action.

### `browser.query`

Read browser state or capture only a registered gateway-owned browser target.

Owner route: `browser.read`. Principals: `observer, operator`. Typed failures: `deadline, invalid_request, not_found, owner_failed, policy_denied, response_bound, unavailable`.

Input schema:

```json
{
  "additionalProperties": false,
  "properties": {
    "actor": {
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "deadline_at": {
      "type": "number"
    },
    "idempotency_key": {
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "parameters": {
      "additionalProperties": true,
      "type": "object"
    },
    "reason": {
      "maxLength": 2000,
      "minLength": 1,
      "type": "string"
    },
    "ref": {
      "maxLength": 2048,
      "minLength": 1,
      "type": "string"
    },
    "request_id": {
      "maxLength": 128,
      "minLength": 1,
      "type": "string"
    }
  },
  "type": "object"
}
```

Examples:

No example is declared. Discover the live schema before invoking this action.

### `files.query`

Stat, list, or read a bounded principal-authorized host path.

Owner route: `files.read`. Principals: `observer, operator`. Typed failures: `deadline, invalid_request, not_found, owner_failed, policy_denied, response_bound, unavailable`.

Input schema:

```json
{
  "additionalProperties": false,
  "properties": {
    "actor": {
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "deadline_at": {
      "type": "number"
    },
    "idempotency_key": {
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "parameters": {
      "additionalProperties": true,
      "type": "object"
    },
    "reason": {
      "maxLength": 2000,
      "minLength": 1,
      "type": "string"
    },
    "ref": {
      "maxLength": 2048,
      "minLength": 1,
      "type": "string"
    },
    "request_id": {
      "maxLength": 128,
      "minLength": 1,
      "type": "string"
    }
  },
  "type": "object"
}
```

Examples:

No example is declared. Discover the live schema before invoking this action.

### `sessions.query`

List, read, or search bounded provider-scoped coding sessions.

Owner route: `sessions.query`. Principals: `observer, operator`. Typed failures: `deadline, invalid_request, not_found, owner_failed, policy_denied, response_bound, unavailable`.

Input schema:

```json
{
  "additionalProperties": false,
  "properties": {
    "actor": {
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "deadline_at": {
      "type": "number"
    },
    "idempotency_key": {
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "parameters": {
      "additionalProperties": true,
      "type": "object"
    },
    "reason": {
      "maxLength": 2000,
      "minLength": 1,
      "type": "string"
    },
    "ref": {
      "maxLength": 2048,
      "minLength": 1,
      "type": "string"
    },
    "request_id": {
      "maxLength": 128,
      "minLength": 1,
      "type": "string"
    }
  },
  "type": "object"
}
```

Examples:

No example is declared. Discover the live schema before invoking this action.

### `memory.query`

Search or retrieve semantic memory while retaining source provenance.

Owner route: `memory.query`. Principals: `observer, operator`. Typed failures: `deadline, invalid_request, not_found, owner_failed, policy_denied, response_bound, unavailable`.

Input schema:

```json
{
  "additionalProperties": false,
  "properties": {
    "actor": {
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "deadline_at": {
      "type": "number"
    },
    "idempotency_key": {
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "parameters": {
      "additionalProperties": true,
      "type": "object"
    },
    "reason": {
      "maxLength": 2000,
      "minLength": 1,
      "type": "string"
    },
    "ref": {
      "maxLength": 2048,
      "minLength": 1,
      "type": "string"
    },
    "request_id": {
      "maxLength": 128,
      "minLength": 1,
      "type": "string"
    }
  },
  "type": "object"
}
```

Examples:

No example is declared. Discover the live schema before invoking this action.

### `timeline.query`

Query available session evidence without claiming unavailable upstream coverage.

Owner route: `timeline.query`. Principals: `observer, operator`. Typed failures: `deadline, invalid_request, not_found, owner_failed, policy_denied, response_bound, unavailable`.

Input schema:

```json
{
  "additionalProperties": false,
  "properties": {
    "actor": {
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "deadline_at": {
      "type": "number"
    },
    "idempotency_key": {
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "parameters": {
      "additionalProperties": true,
      "type": "object"
    },
    "reason": {
      "maxLength": 2000,
      "minLength": 1,
      "type": "string"
    },
    "ref": {
      "maxLength": 2048,
      "minLength": 1,
      "type": "string"
    },
    "request_id": {
      "maxLength": 128,
      "minLength": 1,
      "type": "string"
    }
  },
  "type": "object"
}
```

Examples:

No example is declared. Discover the live schema before invoking this action.

### `artifacts.query`

List opaque artifact metadata or read a bounded artifact range.

Owner route: `artifacts.query`. Principals: `agent-control, observer, operator`. Typed failures: `deadline, invalid_request, not_found, owner_failed, policy_denied, response_bound, unavailable`.

Input schema:

```json
{
  "additionalProperties": false,
  "properties": {
    "actor": {
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "deadline_at": {
      "type": "number"
    },
    "idempotency_key": {
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "parameters": {
      "additionalProperties": true,
      "type": "object"
    },
    "reason": {
      "maxLength": 2000,
      "minLength": 1,
      "type": "string"
    },
    "ref": {
      "maxLength": 2048,
      "minLength": 1,
      "type": "string"
    },
    "request_id": {
      "maxLength": 128,
      "minLength": 1,
      "type": "string"
    }
  },
  "type": "object"
}
```

Examples:

No example is declared. Discover the live schema before invoking this action.

### `audit.verify`

Verify the tamper-evident audit hash chain.

Owner route: `audit.verify`. Principals: `agent-control, observer, operator`. Typed failures: `deadline, invalid_request, not_found, owner_failed, policy_denied, response_bound, unavailable`.

Input schema:

```json
{
  "additionalProperties": false,
  "properties": {
    "actor": {
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "deadline_at": {
      "type": "number"
    },
    "idempotency_key": {
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "parameters": {
      "additionalProperties": true,
      "type": "object"
    },
    "reason": {
      "maxLength": 2000,
      "minLength": 1,
      "type": "string"
    },
    "ref": {
      "maxLength": 2048,
      "minLength": 1,
      "type": "string"
    },
    "request_id": {
      "maxLength": 128,
      "minLength": 1,
      "type": "string"
    }
  },
  "type": "object"
}
```

Examples:

No example is declared. Discover the live schema before invoking this action.

### `captures.query`

List visible capture lanes or query their declared native owner roots.

Owner route: `captures.query`. Principals: `agent-control, observer, operator`. Typed failures: `deadline, invalid_request, not_found, owner_failed, policy_denied, response_bound, unavailable`.

Input schema:

```json
{
  "additionalProperties": false,
  "properties": {
    "actor": {
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "deadline_at": {
      "type": "number"
    },
    "idempotency_key": {
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "parameters": {
      "additionalProperties": true,
      "type": "object"
    },
    "reason": {
      "maxLength": 2000,
      "minLength": 1,
      "type": "string"
    },
    "ref": {
      "maxLength": 2048,
      "minLength": 1,
      "type": "string"
    },
    "request_id": {
      "maxLength": 128,
      "minLength": 1,
      "type": "string"
    }
  },
  "type": "object"
}
```

Examples:

No example is declared. Discover the live schema before invoking this action.

### `jobs.query`

List bounded queued-job summaries with canonical job references.

Owner route: `job.list`. Principals: `agent-control, observer, operator`. Typed failures: `deadline, invalid_request, not_found, owner_failed, policy_denied, response_bound, unavailable`.

Input schema:

```json
{
  "additionalProperties": false,
  "properties": {
    "actor": {
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "deadline_at": {
      "type": "number"
    },
    "idempotency_key": {
      "maxLength": 256,
      "minLength": 1,
      "type": "string"
    },
    "parameters": {
      "additionalProperties": false,
      "properties": {
        "cursor": {
          "maxLength": 512,
          "minLength": 1,
          "type": "string"
        },
        "limit": {
          "default": 100,
          "maximum": 1000,
          "minimum": 1,
          "type": "integer"
        }
      },
      "type": "object"
    },
    "reason": {
      "maxLength": 2000,
      "minLength": 1,
      "type": "string"
    },
    "request_id": {
      "maxLength": 128,
      "minLength": 1,
      "type": "string"
    }
  },
  "type": "object"
}
```

Examples:

```json
{
  "parameters": {
    "limit": 100
  }
}
```
