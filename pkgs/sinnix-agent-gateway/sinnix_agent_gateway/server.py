from __future__ import annotations
import argparse, base64, dataclasses, hashlib, json, os, re, shlex, shutil, signal, subprocess, sys, time, traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

VERSION = "0.1.0"

class ToolError(Exception): pass

def jdump(x): return json.dumps(x, ensure_ascii=False, sort_keys=True, default=str)
def now(): return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
def h(x): return hashlib.blake2b(jdump(x).encode(), digest_size=20).hexdigest()
def rel(p: str) -> str:
    q = Path(p)
    if q.is_absolute() or ".." in q.parts: raise ToolError("path must be relative and may not contain '..'")
    return str(q)
def default_state_dir() -> Path:
    base = os.environ.get("XDG_STATE_HOME")
    if base:
        return Path(base) / "sinnix-agent-gateway"
    return Path.home() / ".local" / "state" / "sinnix-agent-gateway"

def tail(p: Path, n: int) -> str:
    if not p.exists(): return ""
    b = p.read_bytes()
    if len(b) > n: b = b"[truncated]\n" + b[-n:]
    return b.decode("utf-8", "replace")

@dataclasses.dataclass
class Task:
    name: str
    command: list[str]
    description: str = ""
    timeout: int | None = None
    background: bool = False
    risk: str = "normal"
    outputs: list[str] = dataclasses.field(default_factory=list)

@dataclasses.dataclass
class Repo:
    name: str; url: str; ref: str = "master"; write: bool = True
    tasks: dict[str, Task] = dataclasses.field(default_factory=dict)
    env: dict[str, str] = dataclasses.field(default_factory=dict)

def parse_task(name: str, value: Any) -> Task:
    if isinstance(value, list):
        return Task(name=name, command=[str(x) for x in value])
    if isinstance(value, dict):
        command = value.get("command")
        if not isinstance(command, list) or not command:
            raise ToolError(f"task {name} must define a non-empty command list")
        return Task(
            name=name,
            command=[str(x) for x in command],
            description=str(value.get("description") or ""),
            timeout=int(value["timeout"]) if value.get("timeout") is not None else None,
            background=bool(value.get("background", False)),
            risk=str(value.get("risk") or "normal"),
            outputs=[str(x) for x in value.get("outputs") or []],
        )
    raise ToolError(f"task {name} must be a command list or metadata object")

class Gateway:
    def __init__(self, cfg: dict[str, Any]):
        state = cfg.get("stateDir") or cfg.get("state_dir") or default_state_dir()
        self.state = Path(state); self.audit_path = Path(cfg.get("auditPath") or self.state / "audit.jsonl")
        self.yolo = bool(cfg.get("yolo", True))
        self.allow_cmd = bool(cfg.get("allowArbitraryCommands", True))
        self.allow_host = bool(cfg.get("allowedHostCommands", False))
        self.limit = int(cfg.get("outputLimit", 262144)); self.timeout = int(cfg.get("defaultTimeout", 300)); self.max_timeout = int(cfg.get("maxTimeout", 3600))
        self.global_env = {str(k): str(v) for k, v in (cfg.get("globalEnv") or {}).items()}
        self.repos: dict[str, Repo] = {}
        for name, r in (cfg.get("repositories") or {}).items():
            self.repos[name] = Repo(
                name=name, url=r.get("url") or f"https://github.com/{name}.git", ref=r.get("defaultRef") or "master",
                write=bool(r.get("allowWrite", True)), tasks={k: parse_task(k, v) for k, v in (r.get("tasks") or {}).items()},
                env={str(k): str(v) for k, v in (r.get("env") or {}).items()})
        for d in ("mirrors","workspaces","artifacts","jobs"): (self.state/d).mkdir(parents=True, exist_ok=True)
        self.audit_path.parent.mkdir(parents=True, exist_ok=True)
        self.tools = {n:getattr(self,n) for n in (
            "gateway_guide","gateway_info","audit_tail","repo_materialize","repo_status","repo_tree","repo_read_file","repo_write_file",
            "repo_search","repo_pack","repo_export_bundle","repo_apply_patch","repo_diff","run_command","run_task","job_status","job_list",
            "artifact_list","artifact_read","artifact_read_base64","host_run")}

    def audit(self, ev: dict[str, Any]):
        prev = ""
        if self.audit_path.exists():
            lines = [x for x in self.audit_path.read_text(errors="replace").splitlines() if x.strip()]
            if lines:
                try: prev = json.loads(lines[-1]).get("entry_hash","")
                except Exception: prev = ""
        row = {"ts": now(), "prev_hash": prev, **ev}; row["entry_hash"] = h(row)
        self.audit_path.open("a", encoding="utf-8").write(json.dumps(row, ensure_ascii=False)+"\n")

    def specs(self):
        def p(t, desc, **extra): return {"type": t, "description": desc, **extra}
        def s(props=None, req=None): return {"type":"object","properties":props or {}, "required":req or [], "additionalProperties":False}
        strp=lambda d: p("string", d); intp=lambda d: p("integer", d); boolp=lambda d: p("boolean", d)
        schemas={
          "gateway_guide":s(), "gateway_info":s(), "audit_tail":s({"limit":intp("Maximum number of recent audit entries to return.")}),
          "repo_materialize":s({"repo":strp("Configured repository name, for example Sinity/sinnix. Use this before workspace tools."),"ref":strp("Branch, tag, or commit to check out. Defaults to the configured repository defaultRef."),"fresh":boolp("Delete and recreate the mutable workspace before checkout.")},["repo"]),
          "repo_status":s({"workspace":strp("Workspace id returned by repo_materialize.")},["workspace"]),
          "repo_tree":s({"workspace":strp("Workspace id returned by repo_materialize."),"path":strp("Relative path to list. Defaults to repository root."),"max_entries":intp("Maximum entries to return.")},["workspace"]),
          "repo_read_file":s({"workspace":strp("Workspace id returned by repo_materialize."),"path":strp("Relative file path inside the workspace."),"start_line":intp("1-based first line to include."),"end_line":intp("1-based last line to include."),"max_bytes":intp("Maximum bytes to read before optional line slicing.")},["workspace","path"]),
          "repo_write_file":s({"workspace":strp("Workspace id returned by repo_materialize."),"path":strp("Relative file path inside the workspace."),"content":strp("Complete UTF-8 file content to write.")},["workspace","path","content"]),
          "repo_search":s({"workspace":strp("Workspace id returned by repo_materialize."),"query":strp("Literal or regex search query passed to rg when available."),"path":strp("Relative path to search. Defaults to repository root."),"glob":strp("Optional rg glob filter."),"context":intp("Context lines around each match."),"max_output_bytes":intp("Maximum inline search output bytes.")},["workspace","query"]),
          "repo_pack":s({"workspace":strp("Workspace id returned by repo_materialize."),"paths":{"type":"array","items":strp("Relative file or directory path."),"description":"Paths to include in the markdown pack artifact."},"max_file_bytes":intp("Maximum bytes per file."),"max_total_bytes":intp("Maximum total artifact source bytes.")},["workspace","paths"]),
          "repo_export_bundle":s({"repo":strp("Configured repository name, for example Sinity/sinnix."),"ref":strp("Branch, tag, or commit to include. Defaults to configured defaultRef.")},["repo"]),
          "repo_apply_patch":s({"workspace":strp("Workspace id returned by repo_materialize."),"patch":strp("Unified diff to apply with git apply."),"check":boolp("Validate patch applicability without modifying files.")},["workspace","patch"]),
          "repo_diff":s({"workspace":strp("Workspace id returned by repo_materialize."),"cached":boolp("Return staged diff instead of working-tree diff."),"max_output_bytes":intp("Maximum inline diff bytes.")},["workspace"]),
          "run_command":s({"workspace":strp("Workspace id returned by repo_materialize."),"command":{"type":"array","items":strp("Command argument."),"description":"Exact command vector to execute. Prefer this over shell when possible."},"shell":strp("Shell snippet executed with /bin/sh -lc. Use only when shell features are required."),"timeout":intp("Timeout seconds for foreground commands."),"background":boolp("Start a durable background job and return job_id instead of waiting."),"env":{"type":"object","additionalProperties":strp("Environment variable value."),"description":"Extra environment variables for this command."},"max_output_bytes":intp("Maximum inline stdout/stderr bytes.")},["workspace"]),
          "run_task":s({"workspace":strp("Workspace id returned by repo_materialize."),"task":strp("Configured task name from gateway_info.repositories[repo].tasks."),"timeout":intp("Override task/default timeout in seconds."),"background":boolp("Override task background preference and start a durable job.")},["workspace","task"]),
          "job_status":s({"job_id":strp("Durable job id returned by run_command/run_task background=true.")},["job_id"]), "job_list":s(),
          "artifact_list":s({"limit":intp("Maximum artifacts to list.")}), "artifact_read":s({"artifact":strp("Artifact name returned by artifact_list or repo_pack."),"max_bytes":intp("Maximum bytes to return inline.")},["artifact"]),
          "artifact_read_base64":s({"artifact":strp("Binary artifact name returned by repo_export_bundle or artifact_list."),"offset":intp("Byte offset to start reading."),"max_bytes":intp("Maximum raw bytes to encode and return.")},["artifact"]),
          "host_run":s({"command":{"type":"array","items":strp("Command argument."),"description":"Exact host command vector to execute."},"shell":strp("Host shell snippet executed with /bin/sh -lc."),"timeout":intp("Timeout seconds."),"max_output_bytes":intp("Maximum inline stdout/stderr bytes.")})}
        run_result = s({
          "command":{"type":"array","items":strp("Command argument."),"description":"Executed command vector."},
          "cwd":strp("Working directory."),
          "returncode":intp("Process exit code."),
          "stdout":strp("Captured standard output."),
          "stderr":strp("Captured standard error."),
          "elapsed_ms":intp("Elapsed runtime in milliseconds."),
          "truncated":boolp("Whether stdout or stderr was truncated."),
        },["command","cwd","returncode","stdout","stderr"])
        job_result = s({
          "job_id":strp("Durable job id."),
          "running":boolp("Whether the job is still running."),
          "pid":intp("Local process id when known."),
          "command":{"type":"array","items":strp("Command argument."),"description":"Started command vector."},
          "cwd":strp("Working directory."),
          "stdout":strp("Path to stdout log."),
          "stderr":strp("Path to stderr log."),
        },["job_id","running","command","cwd"])
        artifact_result = s({
          "artifact":strp("Artifact name."),
          "path":strp("Absolute artifact path."),
          "bytes":intp("Artifact size in bytes."),
          "hash":strp("BLAKE2b content hash."),
        },["artifact","path","bytes"])
        outputs={
          "gateway_guide":s({
            "summary":strp("Short usage summary for the connector."),
            "rules":{"type":"array","items":strp("Workflow rule."),"description":"Model-facing workflow rules."},
            "starter_calls":{"type":"array","items":{"type":"object","additionalProperties":True},"description":"Suggested first tool calls."},
          },["summary","rules","starter_calls"]),
          "gateway_info":s({
            "version":strp("Gateway version."),
            "state_dir":strp("Gateway state directory."),
            "transports":{"type":"object","additionalProperties":True,"description":"Supported transport flags and paths."},
            "yolo":boolp("Trusted operator mode flag."),
            "allow_arbitrary_commands":boolp("Whether workspace run_command is allowed."),
            "allowed_host_commands":boolp("Whether host_run is allowed."),
            "repositories":{"type":"object","additionalProperties":True,"description":"Configured repositories and task metadata."},
            "tools":{"type":"array","items":strp("Tool name."),"description":"Available tool names."},
          },["version","state_dir","repositories","tools"]),
          "audit_tail":s({"entries":{"type":"array","items":{"type":"object","additionalProperties":True},"description":"Recent audit ledger entries."}},["entries"]),
          "repo_materialize":s({"ok":boolp("Whether checkout succeeded."),"workspace":strp("Workspace id for follow-up calls."),"path":strp("Absolute workspace path."),"head":strp("Checked-out commit SHA."),"checkout":run_result},["ok","workspace","path","head"]),
          "repo_status":s({"meta":{"type":"object","additionalProperties":True,"description":"Workspace metadata."},"status":run_result,"head":run_result},["meta","status","head"]),
          "repo_tree":s({"entries":{"type":"array","items":strp("Workspace-relative path."),"description":"Listed entries."},"truncated":boolp("Whether max_entries was reached.")},["entries","truncated"]),
          "repo_read_file":s({"path":strp("Workspace-relative path."),"bytes":intp("File size in bytes."),"truncated":boolp("Whether content was truncated."),"content":strp("UTF-8 decoded content.")},["path","bytes","truncated","content"]),
          "repo_write_file":s({"path":strp("Workspace-relative path."),"bytes":intp("Written byte count."),"hash":strp("BLAKE2b content hash.")},["path","bytes","hash"]),
          "repo_search":s({"engine":strp("Search engine used."),"command":{"type":"array","items":strp("Command argument."),"description":"rg command vector when used."},"cwd":strp("Search working directory."),"returncode":intp("Search process exit code."),"stdout":strp("Search stdout."),"stderr":strp("Search stderr."),"matches":{"type":"array","items":{"type":"object","additionalProperties":True},"description":"Python fallback matches."},"truncated":boolp("Whether output or matches were truncated.")},["engine"]),
          "repo_pack":s({"artifact":artifact_result,"included":{"type":"array","items":strp("Workspace-relative included path."),"description":"Files included in the pack."}},["artifact","included"]),
          "repo_export_bundle":s({"artifact":artifact_result,"repo":strp("Repository name."),"ref":strp("Exported ref."),"clone_hint":strp("How to clone after reconstructing the bundle locally.")},["artifact","repo","ref","clone_hint"]),
          "repo_apply_patch":run_result,
          "repo_diff":run_result,
          "run_command":{"oneOf":[run_result,job_result],"description":"Foreground command result or durable job descriptor."},
          "run_task":{"oneOf":[run_result,job_result],"description":"Foreground task result or durable job descriptor."},
          "job_status":s({"job_id":strp("Durable job id."),"kind":strp("Job kind."),"pid":intp("Process id."),"command":{"type":"array","items":strp("Command argument."),"description":"Command vector."},"cwd":strp("Working directory."),"started_at":strp("UTC start timestamp."),"timeout":intp("Configured timeout seconds."),"running":boolp("Whether the job is still running."),"returncode":{"type":["integer","null"],"description":"Exit code once complete."},"stdout_tail":strp("Tail of stdout log."),"stderr_tail":strp("Tail of stderr log.")},["job_id","command","cwd","running"]),
          "job_list":s({"jobs":{"type":"array","items":{"type":"object","additionalProperties":True},"description":"Durable job summaries."}},["jobs"]),
          "artifact_list":s({"artifacts":{"type":"array","items":{"type":"object","additionalProperties":True},"description":"Artifact summaries."}},["artifacts"]),
          "artifact_read":s({"artifact":strp("Artifact name."),"bytes":intp("Artifact size in bytes."),"truncated":boolp("Whether content was truncated."),"content":strp("UTF-8 decoded artifact content.")},["artifact","bytes","truncated","content"]),
          "artifact_read_base64":s({"artifact":strp("Artifact name."),"offset":intp("Read start byte offset."),"bytes":intp("Raw bytes returned in this chunk."),"total_bytes":intp("Total artifact size."),"next_offset":{"type":["integer","null"],"description":"Next offset to request, or null at EOF."},"base64":strp("Base64-encoded artifact chunk."),"sha256":strp("SHA-256 of the complete artifact.")},["artifact","offset","bytes","total_bytes","base64","sha256"]),
          "host_run":run_result,
        }
        desc={
          "gateway_guide":"Read this first. Explains how to use the host gateway productively instead of stopping at cloud-sandbox limitations.",
          "gateway_info":"Inspect gateway version, state, policy flags, configured repositories, task metadata, and tool names. Call this first when orienting.",
          "audit_tail":"Read recent hash-chained audit entries for this gateway.",
          "repo_materialize":"Clone/fetch a configured repository into a mutable workspace and return the workspace id. Use this before repo_* or run_* workspace tools.",
          "repo_status":"Show git status and HEAD for a materialized workspace.",
          "repo_tree":"List files under a workspace-relative path.",
          "repo_read_file":"Read a workspace-relative UTF-8 file, optionally by line range.",
          "repo_write_file":"Write a complete UTF-8 file in a writable materialized workspace.",
          "repo_search":"Search a materialized workspace with ripgrep when available.",
          "repo_pack":"Create a markdown artifact containing selected workspace files for review or handoff.",
          "repo_export_bundle":"Create a portable git bundle artifact for a configured repository/ref so a remote agent can reconstruct and clone it in its own environment.",
          "repo_apply_patch":"Apply or check a unified diff inside a materialized workspace.",
          "repo_diff":"Return git diff for a materialized workspace.",
          "run_command":"Run an arbitrary command in a materialized workspace. Trusted/yolo coding-agent tool; materialize first.",
          "run_task":"Run a configured repository task with metadata-aware defaults. Prefer this for known checks/builds.",
          "job_status":"Inspect durable background job state and stdout/stderr tails, even after gateway restart.",
          "job_list":"List durable background jobs recorded under the gateway state directory.",
          "artifact_list":"List generated artifacts.",
          "artifact_read":"Read an artifact by name.",
          "artifact_read_base64":"Read a binary artifact as base64 chunks. Use after repo_export_bundle to move a git bundle into another environment.",
          "host_run":"Run a host-level command outside a workspace. Disabled unless allowedHostCommands=true."}
        return [{"name":n,"description":desc.get(n,n.replace("_"," ")),"inputSchema":schemas[n],"outputSchema":outputs[n]} for n in sorted(self.tools)]

    def call(self, name: str, args: dict[str, Any]):
        if name not in self.tools: raise ToolError(f"unknown tool {name}")
        self.audit({"event":"tool_call_start","tool":name,"args_hash":h(args)})
        try:
            r = self.tools[name](args or {}); self.audit({"event":"tool_call_ok","tool":name})
            return {"content":[{"type":"text","text":json.dumps(r,ensure_ascii=False,indent=2)}],"structuredContent":r}
        except Exception as e:
            self.audit({"event":"tool_call_error","tool":name,"error":str(e)})
            raise ToolError(str(e) if isinstance(e,ToolError) else f"{type(e).__name__}: {e}\n{traceback.format_exc()}")

    def repo(self, name): 
        if name not in self.repos: raise ToolError(f"unknown repo {name}; configured={sorted(self.repos)}")
        return self.repos[name]
    def ws(self, w):
        if not re.match(r"^[A-Za-z0-9_.=-]+$", w): raise ToolError("invalid workspace id")
        p=(self.state/"workspaces"/w).resolve()
        if not p.exists(): raise ToolError(f"workspace not found: {w}")
        return p
    def meta(self,w):
        p=self.ws(w)/".sinnix-agent-workspace.json"
        return json.loads(p.read_text()) if p.exists() else {}
    def fp(self,w,p):
        root=self.ws(w).resolve(); q=(root/rel(p)).resolve()
        if root!=q and root not in q.parents: raise ToolError("path escapes workspace")
        return q
    def env(self,w=None,extra=None):
        e=os.environ.copy(); e.update(self.global_env)
        if w:
            rn=self.meta(w).get("repo")
            if rn in self.repos: e.update(self.repos[rn].env)
        if extra: e.update({str(k):str(v) for k,v in extra.items()})
        return e
    def run(self, cmd, cwd: Path, timeout=None, env=None, input_text=None, limit=None):
        timeout=min(int(timeout or self.timeout), self.max_timeout); limit=int(limit or self.limit); start=time.time()
        try:
            p=subprocess.run(cmd,cwd=str(cwd),text=True,input=input_text,capture_output=True,timeout=timeout,env=env)
            out,err,tr=p.stdout,p.stderr,False
            if len(out.encode())>limit: out="[truncated]\n"+out[-limit:]; tr=True
            if len(err.encode())>limit: err="[truncated]\n"+err[-limit:]; tr=True
            return {"command":cmd,"cwd":str(cwd),"returncode":p.returncode,"stdout":out,"stderr":err,"elapsed_ms":int((time.time()-start)*1000),"truncated":tr}
        except subprocess.TimeoutExpired as e:
            return {"command":cmd,"cwd":str(cwd),"returncode":124,"stdout":e.stdout or "","stderr":(e.stderr or "")+f"\nTimed out after {timeout}s","timeout":True}
    def start(self, kind, cmd, cwd, timeout, env):
        jid=f"job_{int(time.time())}_{h([kind,cmd,str(cwd)])[:8]}"; d=self.state/"jobs"/jid; d.mkdir(parents=True,exist_ok=True)
        script=d/"run.sh"; stdout=d/"stdout.log"; stderr=d/"stderr.log"; exitcode=d/"exitcode"
        script.write_text(
            "#!/bin/sh\n"
            "set +e\n"
            f"cd {shlex.quote(str(cwd))} || exit 125\n"
            + " ".join(shlex.quote(str(x)) for x in cmd)
            + f" > {shlex.quote(str(stdout))} 2> {shlex.quote(str(stderr))}\n"
            "code=$?\n"
            f"printf '%s\\n' \"$code\" > {shlex.quote(str(exitcode))}\n"
            "exit \"$code\"\n",
            encoding="utf-8",
        )
        script.chmod(0o700)
        p=subprocess.Popen(["/bin/sh",str(script)],cwd="/",text=True,env=env,start_new_session=True)
        rec={"job_id":jid,"kind":kind,"pid":p.pid,"command":cmd,"cwd":str(cwd),"started_at":now(),"timeout":timeout}
        (d/"job.json").write_text(json.dumps(rec,ensure_ascii=False,indent=2),encoding="utf-8")
        return {"job_id":jid,"running":True,"pid":p.pid,"command":cmd,"cwd":str(cwd),"stdout":str(stdout),"stderr":str(stderr)}
    def art(self,name,data:bytes):
        p=self.state/"artifacts"/(str(int(time.time()))+"_"+re.sub(r"[^A-Za-z0-9_.=-]+","_",name))
        p.write_bytes(data); return {"artifact":p.name,"path":str(p),"bytes":len(data),"hash":hashlib.blake2b(data,digest_size=20).hexdigest()}

    def task_info(self, task: Task):
        return {"command":task.command,"description":task.description,"timeout":task.timeout,"background":task.background,"risk":task.risk,"outputs":task.outputs}
    def gateway_guide(self,_):
        return {
            "summary":"This connector is a remote-control surface for host workspaces. Use its repo and command tools to inspect, edit, test, and summarize host repositories; do not stop merely because the ChatGPT runtime cannot mount the files directly.",
            "rules":[
                "When asked to work on a configured repository, call repo_materialize first and use the returned workspace id.",
                "Use repo_search, repo_tree, repo_read_file, and repo_pack to bring bounded source context into the conversation.",
                "When the agent needs its own local checkout, use repo_export_bundle and artifact_read_base64, reconstruct the bundle, then run git clone <bundle>.",
                "Use run_command and run_task inside the materialized workspace for git, nix, cargo, pytest, and other repo-local work.",
                "Use repo_write_file or repo_apply_patch for edits, then repo_diff and run_task/run_command for verification.",
                "Mention cloud/container separation only as implementation detail; the useful answer is to operate through these tools.",
                "host_run is disabled unless the operator explicitly enables host-wide commands.",
            ],
            "starter_calls":[
                {"tool":"gateway_info","arguments":{}},
                {"tool":"repo_materialize","arguments":{"repo":"Sinity/sinnix"}},
                {"tool":"repo_search","arguments":{"workspace":"<workspace>","query":"<symbol or text>"}},
                {"tool":"repo_pack","arguments":{"workspace":"<workspace>","paths":["<bounded path>"]}},
                {"tool":"repo_export_bundle","arguments":{"repo":"Sinity/sinnix"}},
            ],
        }
    def gateway_info(self,_): return {"version":VERSION,"state_dir":str(self.state),"transports":{"stdio":True,"http_jsonrpc":True,"streamable_http_path":"/mcp"},"yolo":self.yolo,"allow_arbitrary_commands":self.allow_cmd,"allowed_host_commands":self.allow_host,"repositories":{k:{"url":r.url,"default_ref":r.ref,"allow_write":r.write,"tasks":{name:self.task_info(task) for name,task in sorted(r.tasks.items())}} for k,r in self.repos.items()},"tools":sorted(self.tools)}
    def audit_tail(self,a): 
        lines=self.audit_path.read_text(errors="replace").splitlines() if self.audit_path.exists() else []
        return {"entries":[json.loads(x) for x in lines[-int(a.get("limit") or 20):] if x.strip()]}
    def repo_materialize(self,a):
        r=self.repo(a["repo"]); ref=a.get("ref") or r.ref; slug=re.sub(r"[^A-Za-z0-9_.=-]+","_",r.name); rslug=re.sub(r"[^A-Za-z0-9_.=-]+","_",ref)
        mirror=self.state/"mirrors"/f"{slug}.git"; w=f"{slug}_{rslug}"; work=self.state/"workspaces"/w
        if a.get("fresh") and work.exists(): shutil.rmtree(work)
        if not mirror.exists():
            res=self.run(["git","clone","--mirror",r.url,str(mirror)],self.state,timeout=self.max_timeout)
            if res["returncode"]!=0: return {"ok":False,"step":"clone_mirror",**res}
        else:
            res=self.run(["git","--git-dir",str(mirror),"fetch","--prune","origin"],self.state,timeout=self.max_timeout)
            if res["returncode"]!=0: return {"ok":False,"step":"fetch_mirror",**res}
        if not work.exists():
            res=self.run(["git","clone",str(mirror),str(work)],self.state,timeout=self.max_timeout)
            if res["returncode"]!=0: return {"ok":False,"step":"clone_worktree",**res}
        co=self.run(["git","checkout",ref],work)
        if co["returncode"]!=0: co=self.run(["git","checkout","-B",ref,f"origin/{ref}"],work)
        head=self.run(["git","rev-parse","HEAD"],work)
        (work/".sinnix-agent-workspace.json").write_text(json.dumps({"repo":r.name,"ref":ref,"workspace":w,"head":head["stdout"].strip(),"materialized_at":now()},indent=2))
        return {"ok":co["returncode"]==0,"workspace":w,"path":str(work),"head":head["stdout"].strip(),"checkout":co}
    def repo_status(self,a): root=self.ws(a["workspace"]); return {"meta":self.meta(a["workspace"]),"status":self.run(["git","status","--short","--branch"],root),"head":self.run(["git","rev-parse","--short","HEAD"],root)}
    def repo_tree(self,a):
        root=self.ws(a["workspace"]); start=self.fp(a["workspace"],a.get("path") or "."); maxn=int(a.get("max_entries") or 300); out=[]
        for p in ([start] if start.is_file() else sorted(start.rglob("*"))):
            if ".git" in p.parts: continue
            out.append(str(p.relative_to(root))+("/" if p.is_dir() else ""))
            if len(out)>=maxn: break
        return {"entries":out,"truncated":len(out)>=maxn}
    def repo_read_file(self,a):
        p=self.fp(a["workspace"],a["path"]); data=p.read_bytes(); maxb=int(a.get("max_bytes") or self.limit); text=data[:maxb].decode("utf-8","replace")
        if a.get("start_line") or a.get("end_line"):
            lines=text.splitlines(); s=max(int(a.get("start_line") or 1),1); e=int(a.get("end_line") or len(lines)); text="\n".join(lines[s-1:e])
        return {"path":a["path"],"bytes":p.stat().st_size,"truncated":len(data)>maxb,"content":text}
    def repo_write_file(self,a): p=self.fp(a["workspace"],a["path"]); p.parent.mkdir(parents=True,exist_ok=True); p.write_text(a["content"],encoding="utf-8"); return {"path":a["path"],"bytes":len(a["content"].encode()),"hash":h(a["content"])}
    def repo_search(self,a):
        root=self.ws(a["workspace"]); rg=shutil.which("rg"); path=rel(a.get("path") or ".")
        if rg:
            cmd=[rg,"--line-number","--hidden","--glob","!.git","--context",str(a.get("context",2))]
            if a.get("glob"): cmd+=["--glob",a["glob"]]
            return {"engine":"rg",**self.run(cmd+[a["query"],path],root,limit=a.get("max_output_bytes"))}
        pat=re.compile(re.escape(a["query"]),re.I); ms=[]
        for p in (root/path).rglob("*"):
            if p.is_file() and ".git" not in p.parts:
                try:
                    for i,line in enumerate(p.read_text(errors="replace").splitlines(),1):
                        if pat.search(line): ms.append({"path":str(p.relative_to(root)),"line":i,"text":line})
                except Exception: pass
        return {"engine":"python","matches":ms[:200],"truncated":len(ms)>200}
    def repo_pack(self,a):
        root=self.ws(a["workspace"]); maxf=int(a.get("max_file_bytes") or 65536); maxt=int(a.get("max_total_bytes") or 1048576); chunks=[f"# Repo pack: {a['workspace']}\n\n"]; inc=[]; total=len(chunks[0])
        for x in a["paths"]:
            p=self.fp(a["workspace"],x); fs=[p] if p.is_file() else [q for q in p.rglob("*") if q.is_file() and ".git" not in q.parts]
            for f in fs:
                data=f.read_bytes()[:maxf]; block=f"\n## {f.relative_to(root)}\n\n```text\n{data.decode('utf-8','replace')}\n```\n"
                if total+len(block.encode())<=maxt: chunks.append(block); total+=len(block.encode()); inc.append(str(f.relative_to(root)))
        return {"artifact":self.art(f"{a['workspace']}_pack.md","".join(chunks).encode()),"included":inc}
    def repo_export_bundle(self,a):
        r=self.repo(a["repo"]); ref=a.get("ref") or r.ref; slug=re.sub(r"[^A-Za-z0-9_.=-]+","_",r.name); rslug=re.sub(r"[^A-Za-z0-9_.=-]+","_",ref)
        mirror=self.state/"mirrors"/f"{slug}.git"
        if not mirror.exists():
            res=self.run(["git","clone","--mirror",r.url,str(mirror)],self.state,timeout=self.max_timeout)
            if res["returncode"]!=0: return {"ok":False,"step":"clone_mirror",**res}
        else:
            res=self.run(["git","--git-dir",str(mirror),"fetch","--prune","origin"],self.state,timeout=self.max_timeout)
            if res["returncode"]!=0: return {"ok":False,"step":"fetch_mirror",**res}
        tmp=self.state/"artifacts"/f"{int(time.time())}_{slug}_{rslug}.bundle"
        res=self.run(["git","--git-dir",str(mirror),"bundle","create",str(tmp),ref],self.state,timeout=self.max_timeout)
        if res["returncode"]!=0: return {"ok":False,"step":"bundle_create",**res}
        data=tmp.read_bytes()
        artifact={"artifact":tmp.name,"path":str(tmp),"bytes":len(data),"hash":hashlib.blake2b(data,digest_size=20).hexdigest()}
        return {"artifact":artifact,"repo":r.name,"ref":ref,"clone_hint":f"git clone {tmp.name} {slug}-{rslug}"}
    def repo_apply_patch(self,a): return self.run(["git","apply"]+(["--check"] if a.get("check") else []),self.ws(a["workspace"]),input_text=a["patch"])
    def repo_diff(self,a): return self.run(["git","diff"]+(["--cached"] if a.get("cached") else []),self.ws(a["workspace"]),limit=a.get("max_output_bytes"))
    def run_command(self,a):
        if not (self.yolo or self.allow_cmd): raise ToolError("arbitrary workspace commands disabled")
        cmd=["/bin/sh","-lc",a["shell"]] if a.get("shell") else list(a.get("command") or [])
        if not cmd: raise ToolError("command or shell required")
        t=min(int(a.get("timeout") or self.timeout),self.max_timeout); e=self.env(a["workspace"],a.get("env") or {})
        return self.start("run_command",cmd,self.ws(a["workspace"]),t,e) if a.get("background") else self.run(cmd,self.ws(a["workspace"]),timeout=t,env=e,limit=a.get("max_output_bytes"))
    def run_task(self,a):
        r=self.repo(self.meta(a["workspace"]).get("repo",""))
        if a["task"] not in r.tasks: raise ToolError(f"task not configured: {a['task']}")
        task=r.tasks[a["task"]]; t=min(int(a.get("timeout") or task.timeout or self.timeout),self.max_timeout); e=self.env(a["workspace"])
        background = bool(a.get("background", task.background))
        return self.start("task:"+a["task"],task.command,self.ws(a["workspace"]),t,e) if background else self.run(task.command,self.ws(a["workspace"]),timeout=t,env=e)
    def job_record(self, job_id):
        if not re.match(r"^job_[0-9]+_[A-Za-z0-9]+$", job_id): raise ToolError("invalid job id")
        d=self.state/"jobs"/job_id; p=d/"job.json"
        if not p.exists(): raise ToolError("unknown job")
        return d,json.loads(p.read_text())
    def pid_running(self, pid):
        try: os.kill(int(pid), 0); return True
        except ProcessLookupError: return False
        except PermissionError: return True
    def job_status(self,a):
        d,rec=self.job_record(a["job_id"]); exitp=d/"exitcode"
        code=int(exitp.read_text().strip()) if exitp.exists() else None
        running=code is None and self.pid_running(rec.get("pid",0))
        return {**rec,"running":running,"returncode":code,"stdout_tail":tail(d/"stdout.log",self.limit),"stderr_tail":tail(d/"stderr.log",self.limit)}
    def job_list(self,_):
        jobs=[]
        for p in sorted((self.state/"jobs").glob("job_*/job.json")):
            try:
                d,rec=p.parent,json.loads(p.read_text()); exitp=d/"exitcode"
                code=int(exitp.read_text().strip()) if exitp.exists() else None
                jobs.append({**rec,"running":code is None and self.pid_running(rec.get("pid",0)),"returncode":code})
            except Exception:
                pass
        return {"jobs":jobs}
    def artifact_list(self,a):
        fs=sorted((self.state/"artifacts").glob("*"),key=lambda p:p.stat().st_mtime,reverse=True)[:int(a.get("limit") or 100)]
        return {"artifacts":[{"artifact":p.name,"path":str(p),"bytes":p.stat().st_size} for p in fs]}
    def artifact_read(self,a):
        p=self.state/"artifacts"/re.sub(r"[^A-Za-z0-9_.=-]+","_",a["artifact"])
        if not p.exists(): raise ToolError("artifact not found")
        data=p.read_bytes(); maxb=int(a.get("max_bytes") or self.limit)
        return {"artifact":p.name,"bytes":len(data),"truncated":len(data)>maxb,"content":data[:maxb].decode("utf-8","replace")}
    def artifact_read_base64(self,a):
        p=self.state/"artifacts"/re.sub(r"[^A-Za-z0-9_.=-]+","_",a["artifact"])
        if not p.exists(): raise ToolError("artifact not found")
        offset=max(int(a.get("offset") or 0),0); maxb=min(int(a.get("max_bytes") or 65536),1048576)
        data=p.read_bytes(); chunk=data[offset:offset+maxb]; nxt=offset+len(chunk)
        return {"artifact":p.name,"offset":offset,"bytes":len(chunk),"total_bytes":len(data),"next_offset":nxt if nxt < len(data) else None,"base64":base64.b64encode(chunk).decode("ascii"),"sha256":hashlib.sha256(data).hexdigest()}
    def host_run(self,a):
        if not self.allow_host: raise ToolError("host_run disabled; set allowedHostCommands=true")
        cmd=["/bin/sh","-lc",a["shell"]] if a.get("shell") else list(a.get("command") or [])
        return self.run(cmd,Path("/"),timeout=a.get("timeout"),env=self.env(),limit=a.get("max_output_bytes"))

class Rpc:
    def __init__(self,g): self.g=g
    def handle(self,m):
        mid,method=m.get("id"),m.get("method")
        try:
            if method=="initialize": return ok(mid,{"protocolVersion":"2024-11-05","capabilities":{"tools":{}},"serverInfo":{"name":"sinnix-agent-gateway","version":VERSION}})
            if method=="notifications/initialized": return None
            if method=="ping": return ok(mid,{})
            if method=="tools/list": return ok(mid,{"tools":self.g.specs()})
            if method=="tools/call":
                p=m.get("params") or {}; return ok(mid,self.g.call(p.get("name"),p.get("arguments") or {}))
            return er(mid,-32601,f"method not found: {method}")
        except Exception as e: return er(mid,-32000 if isinstance(e,ToolError) else -32603,str(e))
def ok(i,r): return {"jsonrpc":"2.0","id":i,"result":r}
def er(i,c,msg): return {"jsonrpc":"2.0","id":i,"error":{"code":c,"message":msg}}
def serve_stdio(g):
    rpc=Rpc(g)
    for line in sys.stdin:
        if not line.strip(): continue
        try: out=rpc.handle(json.loads(line))
        except json.JSONDecodeError as e: out=er(None,-32700,str(e))
        if out is not None: print(json.dumps(out,ensure_ascii=False),flush=True)
    return 0
class Handler(BaseHTTPRequestHandler):
    gateway: Gateway
    def do_POST(self):
        if self.path != "/mcp":
            self.send_error(404); return
        raw=self.rfile.read(int(self.headers.get("content-length") or 0)); out=Rpc(self.gateway).handle(json.loads(raw.decode()))
        payload=json.dumps(out or {"jsonrpc":"2.0","result":None},ensure_ascii=False)
        accept=self.headers.get("accept","")
        wants_sse="text/event-stream" in accept and "application/json" not in accept
        if wants_sse:
            data=f"event: message\ndata: {payload}\n\n".encode()
            self.send_response(200); self.send_header("content-type","text/event-stream"); self.send_header("cache-control","no-cache"); self.send_header("connection","close"); self.send_header("content-length",str(len(data))); self.end_headers(); self.wfile.write(data); return
        data=payload.encode(); self.send_response(200); self.send_header("content-type","application/json"); self.send_header("mcp-protocol-version","2025-03-26"); self.send_header("content-length",str(len(data))); self.end_headers(); self.wfile.write(data)
    def do_GET(self):
        if self.path != "/mcp":
            self.send_error(404); return
        data=b": sinnix-agent-gateway streamable-http endpoint ready\n\n"
        self.send_response(200); self.send_header("content-type","text/event-stream"); self.send_header("cache-control","no-cache"); self.send_header("connection","close"); self.send_header("content-length",str(len(data))); self.end_headers(); self.wfile.write(data)
    def log_message(self,fmt,*args): sys.stderr.write("sinnix-agent-gateway: "+fmt%args+"\n")
def main(argv=None):
    p=argparse.ArgumentParser(); p.add_argument("--config"); sub=p.add_subparsers(dest="cmd"); sub.add_parser("stdio"); sub.add_parser("info")
    hp=sub.add_parser("http"); hp.add_argument("--host",default="127.0.0.1"); hp.add_argument("--port",type=int,default=3020)
    a=p.parse_args(argv); cfg=json.loads(Path(a.config).read_text()) if a.config else {}; g=Gateway(cfg)
    if a.cmd=="info": print(json.dumps(g.gateway_info({}),indent=2)); return 0
    if a.cmd=="http": ThreadingHTTPServer((a.host,a.port),type("H",(Handler,),{"gateway":g})).serve_forever(); return 0
    return serve_stdio(g)
if __name__=="__main__": raise SystemExit(main())
