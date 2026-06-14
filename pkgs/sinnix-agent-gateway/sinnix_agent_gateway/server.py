from __future__ import annotations
import argparse, dataclasses, hashlib, json, os, re, shutil, subprocess, sys, time, traceback
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
def tail(p: Path, n: int) -> str:
    if not p.exists(): return ""
    b = p.read_bytes()
    if len(b) > n: b = b"[truncated]\n" + b[-n:]
    return b.decode("utf-8", "replace")

@dataclasses.dataclass
class Repo:
    name: str; url: str; ref: str = "master"; write: bool = True
    tasks: dict[str, list[str]] = dataclasses.field(default_factory=dict)
    env: dict[str, str] = dataclasses.field(default_factory=dict)

class Gateway:
    def __init__(self, cfg: dict[str, Any]):
        state = cfg.get("stateDir") or cfg.get("state_dir") or "/var/lib/sinnix-agent-gateway"
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
                write=bool(r.get("allowWrite", True)), tasks={k: list(v) for k, v in (r.get("tasks") or {}).items()},
                env={str(k): str(v) for k, v in (r.get("env") or {}).items()})
        for d in ("mirrors","workspaces","artifacts","jobs"): (self.state/d).mkdir(parents=True, exist_ok=True)
        self.audit_path.parent.mkdir(parents=True, exist_ok=True)
        self.jobs: dict[str, tuple[subprocess.Popen[str], Path, list[str], str]] = {}
        self.tools = {n:getattr(self,n) for n in (
            "gateway_info","audit_tail","repo_materialize","repo_status","repo_tree","repo_read_file","repo_write_file",
            "repo_search","repo_pack","repo_apply_patch","repo_diff","run_command","run_task","job_status","job_list",
            "artifact_list","artifact_read","host_run")}

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
        def s(props=None, req=None): return {"type":"object","properties":props or {}, "required":req or [], "additionalProperties":False}
        strp={"type":"string"}; intp={"type":"integer"}; boolp={"type":"boolean"}
        schemas={
          "gateway_info":s(), "audit_tail":s({"limit":intp}),
          "repo_materialize":s({"repo":strp,"ref":strp,"fresh":boolp},["repo"]),
          "repo_status":s({"workspace":strp},["workspace"]),
          "repo_tree":s({"workspace":strp,"path":strp,"max_entries":intp},["workspace"]),
          "repo_read_file":s({"workspace":strp,"path":strp,"start_line":intp,"end_line":intp,"max_bytes":intp},["workspace","path"]),
          "repo_write_file":s({"workspace":strp,"path":strp,"content":strp},["workspace","path","content"]),
          "repo_search":s({"workspace":strp,"query":strp,"path":strp,"glob":strp,"context":intp,"max_output_bytes":intp},["workspace","query"]),
          "repo_pack":s({"workspace":strp,"paths":{"type":"array","items":strp},"max_file_bytes":intp,"max_total_bytes":intp},["workspace","paths"]),
          "repo_apply_patch":s({"workspace":strp,"patch":strp,"check":boolp},["workspace","patch"]),
          "repo_diff":s({"workspace":strp,"cached":boolp,"max_output_bytes":intp},["workspace"]),
          "run_command":s({"workspace":strp,"command":{"type":"array","items":strp},"shell":strp,"timeout":intp,"background":boolp,"env":{"type":"object","additionalProperties":strp},"max_output_bytes":intp},["workspace"]),
          "run_task":s({"workspace":strp,"task":strp,"timeout":intp,"background":boolp},["workspace","task"]),
          "job_status":s({"job_id":strp},["job_id"]), "job_list":s(),
          "artifact_list":s({"limit":intp}), "artifact_read":s({"artifact":strp,"max_bytes":intp},["artifact"]),
          "host_run":s({"command":{"type":"array","items":strp},"shell":strp,"timeout":intp,"max_output_bytes":intp})}
        desc={"run_command":"Run an arbitrary command in a materialized workspace. Trusted/yolo coding-agent tool.",
              "host_run":"Run a host-level command outside a workspace. Disabled unless allowedHostCommands=true."}
        return [{"name":n,"description":desc.get(n,n.replace("_"," ")),"inputSchema":schemas[n]} for n in sorted(self.tools)]

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
        out=(d/"stdout.log").open("w"); err=(d/"stderr.log").open("w")
        p=subprocess.Popen(cmd,cwd=str(cwd),text=True,stdout=out,stderr=err,env=env); out.close(); err.close()
        self.jobs[jid]=(p,d,cmd,str(cwd)); return {"job_id":jid,"running":True,"command":cmd,"cwd":str(cwd)}
    def art(self,name,data:bytes):
        p=self.state/"artifacts"/(str(int(time.time()))+"_"+re.sub(r"[^A-Za-z0-9_.=-]+","_",name))
        p.write_bytes(data); return {"artifact":p.name,"path":str(p),"bytes":len(data),"hash":hashlib.blake2b(data,digest_size=20).hexdigest()}

    def gateway_info(self,_): return {"version":VERSION,"state_dir":str(self.state),"yolo":self.yolo,"allow_arbitrary_commands":self.allow_cmd,"allowed_host_commands":self.allow_host,"repositories":{k:{"url":r.url,"default_ref":r.ref,"allow_write":r.write,"tasks":sorted(r.tasks)} for k,r in self.repos.items()},"tools":sorted(self.tools)}
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
        cmd=r.tasks[a["task"]]; t=min(int(a.get("timeout") or self.timeout),self.max_timeout); e=self.env(a["workspace"])
        return self.start("task:"+a["task"],cmd,self.ws(a["workspace"]),t,e) if a.get("background") else self.run(cmd,self.ws(a["workspace"]),timeout=t,env=e)
    def job_status(self,a):
        p,d,cmd,cwd=self.jobs.get(a["job_id"]) or (_ for _ in ()).throw(ToolError("unknown job"))
        return {"job_id":a["job_id"],"running":p.poll() is None,"returncode":p.poll(),"command":cmd,"cwd":cwd,"stdout_tail":tail(d/"stdout.log",self.limit),"stderr_tail":tail(d/"stderr.log",self.limit)}
    def job_list(self,_): return {"jobs":[{"job_id":j,"running":p.poll() is None,"returncode":p.poll(),"command":cmd,"cwd":cwd} for j,(p,_d,cmd,cwd) in self.jobs.items()]}
    def artifact_list(self,a):
        fs=sorted((self.state/"artifacts").glob("*"),key=lambda p:p.stat().st_mtime,reverse=True)[:int(a.get("limit") or 100)]
        return {"artifacts":[{"artifact":p.name,"path":str(p),"bytes":p.stat().st_size} for p in fs]}
    def artifact_read(self,a):
        p=self.state/"artifacts"/re.sub(r"[^A-Za-z0-9_.=-]+","_",a["artifact"])
        if not p.exists(): raise ToolError("artifact not found")
        data=p.read_bytes(); maxb=int(a.get("max_bytes") or self.limit)
        return {"artifact":p.name,"bytes":len(data),"truncated":len(data)>maxb,"content":data[:maxb].decode("utf-8","replace")}
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
        raw=self.rfile.read(int(self.headers.get("content-length") or 0)); out=Rpc(self.gateway).handle(json.loads(raw.decode()))
        data=json.dumps(out or {"jsonrpc":"2.0","result":None}).encode(); self.send_response(200); self.send_header("content-type","application/json"); self.send_header("content-length",str(len(data))); self.end_headers(); self.wfile.write(data)
    def log_message(self,fmt,*args): sys.stderr.write("sinnix-agent-gateway: "+fmt%args+"\n")
def main(argv=None):
    p=argparse.ArgumentParser(); p.add_argument("--config"); sub=p.add_subparsers(dest="cmd"); sub.add_parser("stdio"); sub.add_parser("info")
    hp=sub.add_parser("http"); hp.add_argument("--host",default="127.0.0.1"); hp.add_argument("--port",type=int,default=3020)
    a=p.parse_args(argv); cfg=json.loads(Path(a.config).read_text()) if a.config else {}; g=Gateway(cfg)
    if a.cmd=="info": print(json.dumps(g.gateway_info({}),indent=2)); return 0
    if a.cmd=="http": ThreadingHTTPServer((a.host,a.port),type("H",(Handler,),{"gateway":g})).serve_forever(); return 0
    return serve_stdio(g)
if __name__=="__main__": raise SystemExit(main())
