## Project Environment

### Paths (defined in foundation.nix)
```nix
config.sinnix.paths = {
  realmRoot = "/realm";
  dataRoot = "/realm/data";
  capturesRoot = "/realm/data/captures";
  exportsRoot = "/realm/data/exports";
  projectRoot = "/realm/project/sinnix";
  dotsRoot = "/realm/project/sinnix/dots";
};

config.sinnix.projects = {
  root = "/realm/project";
  sinnix = "/realm/project/sinnix";
  sinex = "/realm/project/sinex";
  lynchpin = "/realm/project/sinity-lynchpin";
  polylogue = "/realm/project/polylogue";
  knowledgebase = "/realm/project/knowledgebase";
};
```

### Environment Variables (exported globally)
```bash
SINNIX_ROOT=/realm/project/sinnix
SINEX_ROOT=/realm/project/sinex
LYNCHPIN_REPO_ROOT=/realm/project/sinity-lynchpin
POLYLOGUE_ROOT=/realm/project/polylogue
KNOWLEDGEBASE_ROOT=/realm/project/knowledgebase
```
