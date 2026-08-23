# The capability index — one derived answer to "what can this machine do, and
# how do I invoke it?"
#
# Sinnix already forces every capability to describe itself at the point it is
# declared: script frontmatter must carry `description` or evaluation fails,
# mkFeatureModule/mkServiceModule take one as a required argument, the devshell
# command registry carries help text, skills carry SKILL.md frontmatter, and the
# MCP registry now carries a description per server. Those descriptions were
# write-only — each reachable through a different file, none of them in one
# place a person or an agent could read.
#
# This builder merges them. Every row comes from a declaration that already
# existed; nothing here is a second list to keep in sync (the aiServices lesson:
# a hand-maintained parallel roster silently omitted two backends for months).
# Where a source genuinely has no prose of its own — capture lanes, agent CLI
# lanes — the description is RENDERED from that source's own structured fields
# rather than invented, so it cannot drift either.
#
# Row shape:
#   kind         feature | service | ai-backend | script | command | skill
#                | capture-lane | mcp-server | agent-lane
#                (hub-page rows are added at render time by the ops-reducer,
#                which owns the route table)
#   name         the identifier the operator would use
#   description  one line, from the declaration
#   invoke       shell command / URL that reaches it, or null
#   enabled      true/false where the host decides it, null where meaningless
#   owner        repo-relative file that declares it
#   docs         repo-relative doc that names it, or null
#   plus per-kind extras: unit, path, tier, endpoint, transport, category
{ lib }:
let
  inherit (lib)
    attrByPath
    concatLists
    concatStringsSep
    drop
    filter
    findFirst
    hasPrefix
    imap0
    mapAttrsToList
    naturalSort
    optionalAttrs
    removePrefix
    removeSuffix
    splitString
    trim
    ;

  # `lib.mkEnableOption "X"` renders as "Whether to enable X."; the factories
  # feed it the required `description` argument verbatim, so unwrapping that
  # sentence recovers exactly what the module author wrote. A description that
  # does not fit the shape (a hand-rolled option) is passed through untouched.
  unwrapEnableDescription =
    text:
    let
      stripped = removePrefix "Whether to enable " text;
    in
    if stripped == text then text else removeSuffix "." stripped;

  # ── skills: SKILL.md YAML frontmatter ────────────────────────────────────
  frontmatterLines =
    text:
    (builtins.foldl'
      (
        acc: line:
        if acc.done then
          acc
        else if trim line == "---" then
          acc
          // {
            done = acc.started;
            started = true;
          }
        else if acc.started then
          acc // { lines = acc.lines ++ [ line ]; }
        else
          acc
      )
      {
        started = false;
        done = false;
        lines = [ ];
      }
      (splitString "\n" text)
    ).lines;

  # `key: one line` and the folded/literal `key: >` forms both appear in
  # dots/_ai/skills; this is not a general YAML parser and does not pretend
  # to be one. Returns null when the key is absent.
  frontmatterField =
    key: lines:
    let
      prefix = "${key}:";
      indexed = imap0 (i: line: { inherit i line; }) lines;
      hit = findFirst (entry: hasPrefix prefix entry.line) null indexed;
    in
    if hit == null then
      null
    else
      let
        inline = trim (removePrefix prefix hit.line);
        folded =
          (builtins.foldl'
            (
              acc: line:
              if acc.done then
                acc
              else if trim line == "" then
                acc
              else if hasPrefix "  " line then
                acc // { parts = acc.parts ++ [ (trim line) ]; }
              else
                acc // { done = true; }
            )
            {
              done = false;
              parts = [ ];
            }
            (drop (hit.i + 1) lines)
          ).parts;
      in
      if
        builtins.elem inline [
          ""
          ">"
          "|"
          ">-"
          "|-"
        ]
      then
        concatStringsSep " " folded
      else
        inline;

  frontmatterDescription = frontmatterField "description";
  # Optional `docs: docs/foo.md` frontmatter passthrough, consumed in place
  # of (falling back to) the filename convention. Absent unless a skill's
  # SKILL.md names one -- no ceremony required.
  frontmatterDocs = frontmatterField "docs";

  mkCapabilityIndex =
    {
      # The evaluated host, for enable state and declared surfaces.
      config,
      # The option tree, for each capability's declaration file and its
      # description (see unwrapEnableDescription).
      options,
      # `toString inputs.self`: the flake source root, stripped off declaration
      # paths so `owner` reads as a repo path rather than a store path.
      sourceRoot,
      # flake/script-discovery.nix's registry: name -> { description, tier, ... }
      scriptRegistry,
      # flake/command-registry.nix's commandDocs: the devshell verbs.
      commandDocs,
      # helpers.data.mcpRegistry
      mcpRegistry,
      # helpers.data.agentLanes
      agentLanes,
      # dots/_ai/skills, and flake/data/shared-agent-skills.nix's roster.
      skillsRoot,
      sharedSkills,
    }:
    let
      relative =
        path:
        let
          text = toString path;
          prefix = "${sourceRoot}/";
        in
        if hasPrefix prefix text then removePrefix prefix text else text;

      declaringFile =
        option:
        let
          declarations = option.declarations or [ ];
        in
        if declarations == [ ] then null else relative (builtins.head declarations);

      # A doc names a capability when it is named after it. Deliberately a
      # filename convention rather than a grep over prose: a substring hit in a
      # 400-line document is not evidence that the document is about the thing.
      docsFor =
        name:
        let
          candidate = "docs/${name}.md";
        in
        if builtins.pathExists "${sourceRoot}/${candidate}" then candidate else null;

      mkRow =
        {
          kind,
          name,
          description,
          invoke ? null,
          enabled ? null,
          owner ? null,
          docs ? null,
          extra ? { },
        }:
        {
          inherit
            kind
            name
            description
            invoke
            enabled
            owner
            ;
          docs = if docs != null then docs else docsFor name;
        }
        // extra;

      # ── features ──────────────────────────────────────────────────────────
      featureRows = concatLists (
        mapAttrsToList (
          domain: features:
          mapAttrsToList (
            name: feature:
            let
              option = attrByPath [ domain name "enable" ] { } (options.sinnix.features or { });
            in
            mkRow {
              kind = "feature";
              name = "${domain}.${name}";
              description = unwrapEnableDescription (option.description or name);
              enabled = feature.enable or false;
              owner = declaringFile option;
              docs = feature.docs or null;
            }
          ) (lib.filterAttrs (_: feature: builtins.isAttrs feature && feature ? enable) features)
        ) (config.sinnix.features or { })
      );

      services = lib.filterAttrs (_: service: builtins.isAttrs service && service ? enable) (
        config.sinnix.services or { }
      );

      # A service's units are not reliably named after it: `polylogue` owns
      # `polylogued`, `tailscale` owns `tailscaled`, sinex's bridge owns eight.
      # Prefer the same-named surface, then the surfaces the same module file
      # declared -- which the module system already records, so this is a
      # lookup and not a naming convention.
      surfacesDeclaredIn =
        file:
        if file == null then
          [ ]
        else
          builtins.attrNames (lib.filterAttrs (_: owner: owner == file) surfaceOwners);

      surfaceOf =
        name: file:
        let
          siblings = surfacesDeclaredIn file;
        in
        if config.sinnix.runtime.surfaces ? ${name} then
          config.sinnix.runtime.surfaces.${name}
        else if builtins.length siblings == 1 then
          config.sinnix.runtime.surfaces.${builtins.head siblings}
        else
          null;

      unitInvoke =
        surface:
        if surface == null then
          null
        else
          "systemctl ${lib.optionalString (surface.manager == "user") "--user "}status ${surface.unit}";

      serviceDescription =
        name:
        unwrapEnableDescription (
          (attrByPath [ name "enable" ] { } (options.sinnix.services or { })).description or name
        );

      # ── services, and the AI backends among them ─────────────────────────
      # An AI backend is a service that used mkAiService, which stamps meta.ai.
      # It gets its own kind rather than a duplicate row: the /ai/ page, the
      # `sinnix ai` verbs and the admission mesh all treat it as its own thing.
      serviceRows = mapAttrsToList (
        name: service:
        let
          option = attrByPath [ name "enable" ] { } (options.sinnix.services or { });
          owner = declaringFile option;
          surface = surfaceOf name owner;
          ai = attrByPath [ "meta" "ai" ] null service;
          endpoint = if surface == null then null else surface.activation.publicEndpoint or null;
          # Every surface this module declared, for the live-state probe and
          # for the usage census, which keys services by surface name.
          surfaces = map (surfaceName: {
            name = surfaceName;
            inherit (config.sinnix.runtime.surfaces.${surfaceName}) unit manager;
          }) (naturalSort (surfacesDeclaredIn owner));
        in
        mkRow {
          kind = if ai != null then "ai-backend" else "service";
          inherit name owner;
          description = serviceDescription name;
          enabled = service.enable or false;
          invoke = if ai != null then "sinnix ai start ${name}" else unitInvoke surface;
          docs = service.docs or null;
          extra =
            optionalAttrs (surface != null) {
              inherit (surface) unit manager;
            }
            // optionalAttrs (surfaces != [ ]) { inherit surfaces; }
            // optionalAttrs (endpoint != null) { inherit endpoint; }
            // optionalAttrs (ai != null) {
              backendKind = ai.backendKind or "native";
              requiresCuda = ai.requiresCuda or false;
            };
        }
      ) services;

      # ── scripts ──────────────────────────────────────────────────────────
      # `sinnix <short>` is the front door for every packaged script
      # (flake/cli-dispatcher.nix), so that is the invocation worth printing.
      scriptRows = mapAttrsToList (
        name: entry:
        mkRow {
          kind = "script";
          inherit name;
          inherit (entry) description;
          invoke = "sinnix ${removePrefix "sinnix-" name}";
          # Registry entries not discovered under scripts/ (sinnix-steer)
          # carry their own owner in flake/scripts.nix.
          owner = entry.owner or "scripts/${name}";
          docs = if entry.docs or null != null then entry.docs else docsFor (removePrefix "sinnix-" name);
          extra = {
            inherit (entry) tier;
          };
        }
      ) scriptRegistry;

      # ── devshell commands ────────────────────────────────────────────────
      commandRows = map (
        command:
        mkRow {
          kind = "command";
          inherit (command) name description;
          invoke = command.name;
          owner = "flake/command-registry.nix";
          extra = {
            inherit (command) category;
          };
        }
      ) commandDocs;

      # ── skills ───────────────────────────────────────────────────────────
      skillNames = naturalSort (
        builtins.attrNames (lib.filterAttrs (_: kind: kind == "directory") (builtins.readDir skillsRoot))
      );
      skillRows = map (
        name:
        let
          file = "${skillsRoot}/${name}/SKILL.md";
          lines =
            if !builtins.pathExists file then
              throw "capability-index: dots/_ai/skills/${name} has no SKILL.md"
            else
              frontmatterLines (builtins.readFile file);
          description = frontmatterDescription lines;
        in
        mkRow {
          kind = "skill";
          inherit name;
          description =
            if description == null || description == "" then
              throw "capability-index: dots/_ai/skills/${name}/SKILL.md frontmatter has no description"
            else
              description;
          # In the shared roster ⇒ linked into every agent's skill tree.
          enabled = builtins.elem name sharedSkills;
          owner = "dots/_ai/skills/${name}/SKILL.md";
          docs = frontmatterDocs lines;
        }
      ) skillNames;

      # ── capture lanes ────────────────────────────────────────────────────
      # A lane carries freshness budgets, not prose. Its description is
      # rendered from the surface that owns it, so it stays true by
      # construction; a standalone lane (sinnix.runtime.captures) says so.
      laneCadence =
        lane:
        if lane.eventDriven or false then
          "event-driven"
        else if (lane.cadenceSeconds or null) != null then
          "every ${toString lane.cadenceSeconds}s"
        else
          "no declared cadence";

      # Which file declared each surface / standalone lane. The module system
      # already tracks this per definition, so a lane's owner is looked up
      # rather than guessed from a naming convention that surfaces like
      # `config-drift` and `phone-dispatcher` do not follow.
      definitionFiles =
        option: reduce:
        builtins.foldl' (acc: definition: acc // reduce (relative definition.file) definition.value) { } (
          option.definitionsWithLocations or [ ]
        );

      surfaceOwners = definitionFiles (options.sinnix.runtime.surfaces or { }) (
        file: surfaces: lib.mapAttrs (_: _: file) surfaces
      );

      standaloneLaneOwners = definitionFiles (options.sinnix.runtime.captures or { }) (
        file: lanes: lib.listToAttrs (map (lane: lib.nameValuePair lane.name file) lanes)
      );

      mkLaneRow =
        owner: lane:
        mkRow {
          kind = "capture-lane";
          inherit (lane) name;
          description =
            if owner == null then
              "Capture lane with no owning unit, ${laneCadence lane}"
            else if (options.sinnix.services or { }) ? ${owner} then
              "${serviceDescription owner} — capture lane, ${laneCadence lane}"
            else
              "Capture lane of the ${owner} surface, ${laneCadence lane}";
          enabled = true;
          owner =
            if owner == null then standaloneLaneOwners.${lane.name} or null else surfaceOwners.${owner} or null;
          extra = {
            inherit (lane) path;
          };
        };

      surfaceLaneRows = concatLists (
        mapAttrsToList (
          surfaceName: surface: map (mkLaneRow surfaceName) surface.captures
        ) config.sinnix.runtime.surfaces
      );
      standaloneLaneRows = map (mkLaneRow null) config.sinnix.runtime.captures;

      # ── MCP servers ──────────────────────────────────────────────────────
      mcpRows = mapAttrsToList (
        name: server:
        mkRow {
          kind = "mcp-server";
          inherit name;
          inherit (server) description;
          invoke =
            if server.transport == "http" then
              server.url
            else
              concatStringsSep " " ([ server.command ] ++ (server.args or [ ]));
          owner = "flake/data/mcp-registry.nix";
          extra = {
            inherit (server) tier transport;
            clients = server.clients or [ ];
          };
        }
      ) mcpRegistry.registry;

      # ── agent CLI lanes ──────────────────────────────────────────────────
      # No prose in the registry, and none wanted: what distinguishes a lane IS
      # its client, MCP profile and backend, so the row renders those.
      laneBackend =
        lane:
        if lane ? model then
          " on ${lane.model}"
        else if lane ? env then
          " on an alternate backend"
        else
          "";

      claudeLaneRows = mapAttrsToList (
        _name: lane:
        mkRow {
          kind = "agent-lane";
          name = lane.binName;
          description = "Claude Code, ${lane.mcpProfile} MCP profile${laneBackend lane}";
          invoke = lane.binName;
          owner = "flake/data/agent-lanes.nix";
          extra = {
            client = "claude";
            inherit (lane) mcpProfile;
          };
        }
      ) agentLanes.claudeLanes;

      codexLaneRows = mapAttrsToList (
        _name: lane:
        mkRow {
          kind = "agent-lane";
          name = lane.binName;
          description = "Codex CLI, ${lane.mcpProfile} profile${laneBackend lane}";
          invoke = lane.binName;
          owner = "flake/data/agent-lanes.nix";
          extra = {
            client = "codex";
            inherit (lane) mcpProfile;
          };
        }
      ) agentLanes.codexLanes;

      hermesLaneRows = mapAttrsToList (
        name: profile:
        mkRow {
          kind = "agent-lane";
          name = "hermes-${name}";
          description = "Hermes ${name} profile, ${profile.mcpProfile or "evidence"} MCP profile, ${
            profile.reasoningEffort or "medium"
          } reasoning";
          invoke = "hermes-${name}";
          owner = "flake/data/agent-lanes.nix";
          extra = {
            client = "hermes";
            mcpProfile = profile.mcpProfile or "evidence";
          };
        }
      ) agentLanes.hermesProfiles;

      rows =
        featureRows
        ++ serviceRows
        ++ scriptRows
        ++ commandRows
        ++ skillRows
        ++ surfaceLaneRows
        ++ standaloneLaneRows
        ++ mcpRows
        ++ claudeLaneRows
        ++ codexLaneRows
        ++ hermesLaneRows;

      undescribed = filter (row: row.description == null || trim row.description == "") rows;
    in
    if undescribed != [ ] then
      throw "capability-index: rows without a description: ${
        concatStringsSep ", " (map (row: "${row.kind}/${row.name}") undescribed)
      }"
    else
      {
        schema = "sinnix-capability-index-v1";
        host = config.networking.hostName;
        revision = config.system.configurationRevision;
        rows = lib.sort (a: b: if a.kind == b.kind then a.name < b.name else a.kind < b.kind) rows;
      };
in
{
  inherit
    mkCapabilityIndex
    frontmatterDescription
    frontmatterDocs
    frontmatterLines
    unwrapEnableDescription
    ;
}
