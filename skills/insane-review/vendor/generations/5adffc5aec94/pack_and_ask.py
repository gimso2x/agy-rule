#!/usr/bin/env python3
"""Immutable-generation Insane Review control boundary (snapshotted, never run in place)."""
from __future__ import annotations
import argparse, hashlib, json, os, shutil, stat, subprocess, sys, tarfile, tempfile, time, urllib.parse, urllib.request, uuid
from pathlib import Path, PurePosixPath
from typing import Any

MAX_PACK_BYTES=4_194_304; MAX_PACK_TOKENS=100_000; REQUIRED_MODEL="GPT-5.6 Sol"; REQUIRED_TIER="Pro"
def die(s: str)->None: raise RuntimeError(s)
def digest_bytes(data: bytes)->str: return hashlib.sha256(data).hexdigest()
def sha256(path: Path)->str:
    with path.open("rb") as f: return digest_bytes(f.read())
def ancestors_safe(path: Path)->None:
    for parent in reversed((path, *path.parents)):
        info=parent.lstat()
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode): die(f"unsafe ancestor: {parent}")
def root(path: Path)->Path:
    path.mkdir(mode=0o700, parents=True, exist_ok=True); ancestors_safe(path)
    if stat.S_IMODE(path.stat().st_mode)!=0o700: die("private root must be 0700")
    return path
def directory_fd(path: Path)->int:
    path=path.absolute(); fd=os.open(path.anchor,os.O_RDONLY|os.O_DIRECTORY|os.O_CLOEXEC)
    try:
        for component in path.parts[1:]:
            next_fd=os.open(component,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=fd)
            os.close(fd); fd=next_fd
        return fd
    except BaseException:
        os.close(fd); raise
def private_write(root_path: Path, suffix: str, payload: bytes)->Path:
    root(root_path); name=f"{time.time_ns()}-{uuid.uuid4().hex}{suffix}"; p=root_path/name; parent_fd=directory_fd(root_path)
    try: fd=os.open(name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o600,dir_fd=parent_fd)
    finally: os.close(parent_fd)
    try:
        with os.fdopen(fd,"wb") as f: f.write(payload); f.flush(); os.fsync(f.fileno())
    except BaseException: p.unlink(missing_ok=True); raise
    return p
def canonical(v: str)->str:
    p=PurePosixPath(v)
    if not v or p.is_absolute() or ".." in p.parts or str(p)!=v: die("invalid manifest path")
    return v
def manifest(path: Path)->list[dict[str,str]]:
    try: data=json.loads(path.read_text()); files=data["files"] if isinstance(data,dict) else data
    except Exception as e: raise RuntimeError("malformed manifest") from e
    if not isinstance(files,list) or not files: die("manifest must be nonempty")
    out=[]; seen=set()
    for item in files:
        if not isinstance(item,dict) or set(item)!={"path","sha256"}: die("invalid manifest entry")
        name,d=canonical(item["path"]),item["sha256"]
        if name in seen or not isinstance(d,str) or len(d)!=64 or any(c not in "0123456789abcdef" for c in d): die("invalid manifest digest")
        seen.add(name); out.append({"path":name,"sha256":d})
    return sorted(out,key=lambda x:x["path"])
def secure_source(repo: Path, relative: str)->Path:
    ancestors_safe(repo); p=repo
    for part in PurePosixPath(relative).parts:
        p=p/part
        try: info=p.lstat()
        except OSError as error: raise RuntimeError(f"missing source: {relative}") from error
        if stat.S_ISLNK(info.st_mode): die(f"symlinked source: {relative}")
    if not p.is_file(): die(f"missing source: {relative}")
    return p
def secretlint(repo: Path, config: Path, files:list[str])->dict[str,Any]:
    if not config.is_file() or config.is_symlink(): die("secretlint configuration is required")
    try:
        config_data=json.loads(config.read_text())
    except (OSError,ValueError) as error:
        raise RuntimeError("secretlint configuration must be JSON") from error
    if not isinstance(config_data,dict) or any(key in config_data for key in ("ignore","ignores","ignorePatterns")):
        die("secretlint ignore rules are forbidden for required files")
    with tempfile.NamedTemporaryFile(mode="w", prefix="mygjc-secretlint-ignore-", delete=True) as ignore:
        ignore.flush()
        absolute_files=[str(repo/path) for path in files]
        try: r=subprocess.run(["secretlint","--format","json","--secretlintrc",str(config),"--secretlintignore",ignore.name,*absolute_files],cwd=repo.anchor,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=120,check=False)
        except (OSError,subprocess.TimeoutExpired) as e: raise RuntimeError("secretlint mandatory and unavailable") from e
    result={"exit_code":r.returncode,"stdout_sha256":digest_bytes(r.stdout.encode()),"stderr_sha256":digest_bytes(r.stderr.encode()),"excluded":[],"scanned_files":sorted(files)}
    try:
        parsed=json.loads(r.stdout) if r.stdout.strip() else []
    except ValueError as error:
        raise RuntimeError("secretlint returned non-JSON evidence") from error
    if not isinstance(parsed,(list,dict)) or r.returncode: die("secretlint rejected transfer")
    if set(result["excluded"]) & set(files): die("required manifest file excluded by secretlint")
    return result
def token_count(pack: Path)->int:
    # ponytail: one byte is a conservative token upper bound; replace with a
    # pinned tokenizer only if the 100 KiB effective ceiling becomes limiting.
    return pack.stat().st_size
def node_env()->dict[str,str]:
    env=os.environ.copy()
    try:
        root=subprocess.run(["npm","root","-g"],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True,timeout=10,check=True).stdout.strip()
    except (OSError,subprocess.SubprocessError):
        root=""
    if root: env["NODE_PATH"]=root
    return env
def packed_manifest(pack: Path)->list[dict[str,str]]:
    try:
        with tarfile.open(pack) as a:
            out=[]
            for m in a.getmembers():
                if not m.isfile(): die("pack contains non-regular entry")
                f=a.extractfile(m)
                if f is None: die("pack parse failed")
                out.append({"path":canonical(m.name),"sha256":digest_bytes(f.read())})
            return sorted(out,key=lambda x:x["path"])
    except (tarfile.TarError,OSError) as e: raise RuntimeError("pack parse failed") from e
def prepare(args: argparse.Namespace)->dict[str,Any]:
    repo=Path(args.repo).absolute(); intended=manifest(Path(args.intended).absolute()); sources=[]
    for item in intended:
        p=secure_source(repo,item["path"])
        if sha256(p)!=item["sha256"]: die("source manifest drift")
        sources.append(p)
    if sum(path.stat().st_size for path in sources)>MAX_PACK_TOKENS:
        die("pack token limit")
    lint=secretlint(repo,Path(args.secretlint_config).absolute(),[x["path"] for x in intended]); out=root(Path(args.artifact_root).absolute())
    fd,tmp=tempfile.mkstemp(dir=out,prefix="staging-",suffix=".tar"); os.close(fd); staging=Path(tmp)
    try:
        os.chmod(staging,0o600)
        with tarfile.open(staging,"w") as a:
            for item,p in zip(intended,sources): a.add(p,arcname=item["path"],recursive=False)
        actual=packed_manifest(staging)
        if actual!=intended: die("intended and actual manifest differ")
        if staging.stat().st_size==0 or staging.stat().st_size>MAX_PACK_BYTES: die("pack byte limit")
        tokens=token_count(staging)
        if tokens>MAX_PACK_TOKENS: die("pack token limit")
        actual_path=private_write(out,".actual-manifest.json",json.dumps({"files":actual},sort_keys=True,separators=(",",":")).encode())
        intended_path=private_write(out,".intended-manifest.json",json.dumps({"files":intended},sort_keys=True,separators=(",",":")).encode())
        pack=private_write(out,".pack.tar",staging.read_bytes())
    finally: staging.unlink(missing_ok=True)
    receipt={"pack":str(pack),"pack_sha256":sha256(pack),"manifest":str(actual_path),"manifest_sha256":sha256(actual_path),"intended_manifest":str(intended_path),"bytes":pack.stat().st_size,"tokens":tokens,"tokenizer":"byte-upper-bound","secretlint":lint}
    receipt["receipt"]=str(private_write(out,".prepare.json",json.dumps(receipt,sort_keys=True).encode())); return receipt
def open_private(path: Path, expected: str)->int:
    path=path.absolute()
    parts=path.parts
    parent_fd=os.open(path.anchor,os.O_RDONLY|os.O_DIRECTORY|os.O_CLOEXEC)
    try:
        for component in parts[1:-1]:
            next_fd=os.open(component,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=parent_fd)
            os.close(parent_fd); parent_fd=next_fd
        fd=os.open(parts[-1],os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=parent_fd)
    except OSError as error:
        raise RuntimeError("unsafe private artifact") from error
    finally:
        os.close(parent_fd)
    info=os.fstat(fd)
    if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode)!=0o600: os.close(fd); die("unsafe private artifact")
    data=os.read(fd,info.st_size); os.lseek(fd,0,os.SEEK_SET)
    if not data or len(data)>MAX_PACK_BYTES or digest_bytes(data)!=expected: os.close(fd); die("artifact identity changed")
    return fd
def fd_digest(fd:int)->str:
    position=os.lseek(fd,0,os.SEEK_CUR); os.lseek(fd,0,os.SEEK_SET); chunks=[]
    while True:
        chunk=os.read(fd,1<<20)
        if not chunk: break
        chunks.append(chunk)
    os.lseek(fd,position,os.SEEK_SET)
    return digest_bytes(b"".join(chunks))
def endpoint(url:str)->str:
    p=urllib.parse.urlparse(url)
    if p.scheme!="http" or p.hostname not in {"127.0.0.1","localhost"} or not p.port: die("localhost CDP required")
    try:
        with urllib.request.urlopen(url.rstrip("/")+"/json/version",timeout=5) as r: data=json.load(r)
    except Exception as e: raise RuntimeError("CDP unavailable") from e
    if not isinstance(data.get("webSocketDebuggerUrl"),str): die("invalid CDP")
    return url
def profile(path:Path)->None:
    ancestors_safe(path.parent); i=path.lstat()
    if stat.S_ISLNK(i.st_mode) or not stat.S_ISDIR(i.st_mode) or stat.S_IMODE(i.st_mode)!=0o700: die("unsafe dedicated profile")
def profile_bound(endpoint_url: str, profile_dir: Path)->int:
    port=urllib.parse.urlparse(endpoint_url).port
    try:
        processes=subprocess.run(["ps","-eo","pid=,args="],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=5,check=True).stdout.splitlines()
    except (OSError,subprocess.SubprocessError) as e: raise RuntimeError("cannot verify CDP profile binding") from e
    expected=f"--user-data-dir={profile_dir}"
    for line in processes:
        if (f"--remote-debugging-port={port}" in line or f"--remote-debugging-port {port}" in line) and expected in line:
            return int(line.strip().split(maxsplit=1)[0])
    die("CDP endpoint is not bound to the dedicated profile")
def listener_owned(pid:int,port:int)->None:
    socket_inodes=set()
    for table in ("/proc/net/tcp","/proc/net/tcp6"):
        try:
            for line in Path(table).read_text().splitlines()[1:]:
                fields=line.split()
                if int(fields[1].rsplit(":",1)[1],16)==port and fields[3]=="0A":
                    socket_inodes.add(fields[9])
        except (OSError,ValueError,IndexError):
            continue
    try: links=[item.readlink().name for item in (Path("/proc")/str(pid)/"fd").iterdir() if item.is_symlink()]
    except OSError as error: raise RuntimeError("cannot verify CDP listener owner") from error
    if not any(link.startswith("socket:[") and link[8:-1] in socket_inodes for link in links):
        die("dedicated browser does not own the CDP listener")
def upload(fd:int, endpoint_url:str, prompt:str, timeout:int, profile_dir:Path)->str:
    script=r'''const {chromium}=require("playwright");const fs=require("fs");const x=JSON.parse(fs.readFileSync(0,"utf8"));(async()=>{const b=await chromium.connectOverCDP(x.endpoint);const c=b.contexts().find(c=>c.pages().some(p=>p.url().includes("chatgpt.com")));if(!c)throw Error("manual login unavailable");const p=c.pages().find(p=>p.url().includes("chatgpt.com"));const model=p.locator('[data-testid="model-switcher-button"],[data-testid="model-switcher-dropdown-button"]').first();await model.waitFor();if((await model.innerText()).trim()!==x.model)throw Error("exact model/tier unavailable");const before=await p.locator('[data-message-author-role="assistant"]').count();const attachments=p.getByTestId("attachment-pill");const attachmentBefore=await attachments.count();const input=p.getByTestId("file-upload-input");await input.setInputFiles({name:x.packName,mimeType:"application/x-tar",buffer:fs.readFileSync(x.pack)});const pill=attachments.nth(attachmentBefore);await pill.waitFor();if(!(await pill.innerText()).includes(x.packName))throw Error("approved attachment name mismatch");const box=p.locator("textarea");await box.fill(x.prompt);await box.press("Enter");const stop=p.getByTestId("stop-button");await stop.waitFor({state:"visible",timeout:x.timeout});const turn=p.locator('[data-message-author-role="assistant"]').nth(before);await turn.waitFor({state:"visible",timeout:x.timeout});await stop.waitFor({state:"hidden",timeout:x.timeout});const out=(await turn.innerText()).trim();if(!out||out===x.prompt||/sign in|log in|access denied/i.test(out))throw Error("invalid assistant turn");console.log(out);await b.close()})().catch(e=>{console.error(e.message);process.exit(1)});'''
    payload=json.dumps({"endpoint":endpoint_url,"pack":f"/proc/self/fd/{fd}","packName":f"mygjc-{fd_digest(fd)[:16]}.tar","prompt":prompt,"timeout":timeout*1000,"model":f"{REQUIRED_MODEL} {REQUIRED_TIER}","profile":str(profile_dir)})
    r=subprocess.run(["node","-e",script],input=payload,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=timeout+15,pass_fds=(fd,),env=node_env(),check=False)
    if r.returncode or not r.stdout.strip(): die("CDP model/attachment/assistant completion failed")
    return r.stdout
def failure_receipt(out: Path, stage: str, error: BaseException)->None:
    # Never retain prompt, source, cookie, or response content in a failure receipt.
    private_write(out,".failure.json",json.dumps({"stage":stage,"error":str(error)[:256]},sort_keys=True).encode())
def send(args:argparse.Namespace)->dict[str,Any]:
    out=root(Path(args.artifact_root).absolute()); mfd=pfd=None; started=time.monotonic(); stage="validation"
    try:
        profile_path=Path(args.profile_dir).absolute(); profile(profile_path)
        mfd=open_private(Path(args.manifest).absolute(),args.approved_manifest_sha); pfd=open_private(Path(args.pack).absolute(),args.approved_pack_sha)
        if packed_manifest(Path(f"/proc/self/fd/{pfd}"))!=manifest(Path(f"/proc/self/fd/{mfd}")): die("approved manifest differs from pack")
        from cdp_lock import CdpLease
        verified_endpoint=endpoint(args.cdp_endpoint); browser_pid=profile_bound(verified_endpoint,profile_path); listener_owned(browser_pid,urllib.parse.urlparse(verified_endpoint).port or 0)
        approval_path=private_write(out,".approval.json",json.dumps({"pack_sha256":args.approved_pack_sha,"manifest_sha256":args.approved_manifest_sha,"model":f"{REQUIRED_MODEL} {REQUIRED_TIER}","endpoint":verified_endpoint,"browser_pid":browser_pid},sort_keys=True).encode())
        stage="external-send"
        with CdpLease(out,urllib.parse.urlparse(verified_endpoint).port or 0): response=upload(pfd,verified_endpoint,args.prompt,args.timeout,profile_path)
        stage="post-upload-persistence"
        response_path=private_write(out,".response.md",response.encode())
        success_path=private_write(out,".send-success.json",json.dumps({"approval":str(approval_path),"response":str(response_path),"pack_sha256":args.approved_pack_sha,"manifest_sha256":args.approved_manifest_sha,"elapsed_ms":round((time.monotonic()-started)*1000)},sort_keys=True).encode())
    except BaseException as error:
        failure_receipt(out,stage,error)
        raise
    finally:
        if mfd is not None: os.close(mfd)
        if pfd is not None: os.close(pfd)
    return {"response":str(response_path),"success_receipt":str(success_path),"approval_receipt":str(approval_path),"pack_sha256":args.approved_pack_sha,"manifest_sha256":args.approved_manifest_sha,"model":f"{REQUIRED_MODEL} {REQUIRED_TIER}"}
def check_env(args:argparse.Namespace)->dict[str,Any]:
    state={"python":sys.version.split()[0],"secretlint":bool(shutil.which("secretlint")),"node":bool(shutil.which("node")),"playwright":False,"cdp":"unobserved","profile":"unobserved","login":"unobserved","model":"unobserved","reason":None,"ready":False}
    if not state["node"]: return state
    state["playwright"]=subprocess.run(["node","-e","require.resolve('playwright')"],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,env=node_env()).returncode==0
    if getattr(args,"cdp_endpoint",None) and getattr(args,"profile_dir",None):
        try:
            profile(Path(args.profile_dir).absolute()); state["profile"]="valid"; endpoint(args.cdp_endpoint); profile_bound(args.cdp_endpoint,Path(args.profile_dir).absolute()); state["cdp"]="reachable"
            probe='''const {chromium}=require("playwright");const fs=require("fs");const x=JSON.parse(fs.readFileSync(0,"utf8"));(async()=>{const b=await chromium.connectOverCDP(x.endpoint);const p=b.contexts().flatMap(c=>c.pages()).find(p=>p.url().includes("chatgpt.com"));if(!p){console.log(JSON.stringify({login:"missing",model:"unobserved",reason:"no_chatgpt_page"}));await b.close();return}if(await p.getByTestId("login-button").count()>0||await p.locator("textarea").count()===0){console.log(JSON.stringify({login:"missing",model:"unobserved",reason:"authentication_required"}));await b.close();return}let label;try{const m=p.locator('[data-testid="model-switcher-button"],[data-testid="model-switcher-dropdown-button"]').first();await m.waitFor({timeout:5000});label=(await m.innerText()).trim()}catch{console.log(JSON.stringify({login:"ready",model:"unobservable",reason:"model_selector_unavailable"}));await b.close();return}console.log(JSON.stringify({login:"ready",model:label===x.model?"ready":"mismatch",reason:label===x.model?null:"model_mismatch"}));await b.close()})().catch(e=>{console.log(JSON.stringify({login:"unobservable",model:"unobservable",reason:"probe_error:"+e.message}));});'''
            probe_result=subprocess.run(["node","-e",probe],input=json.dumps({"endpoint":args.cdp_endpoint,"model":f"{REQUIRED_MODEL} {REQUIRED_TIER}"}),text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=10,env=node_env(),check=False)
            if probe_result.returncode==0:
                lines=[line for line in probe_result.stdout.splitlines() if line.strip()]
                observed=None
                for line in reversed(lines):
                    try: observed=json.loads(line); break
                    except ValueError: continue
                if not isinstance(observed,dict): raise ValueError("missing probe JSON")
                state.update(login=observed["login"],model=observed["model"],reason=observed["reason"])
                state["ready"]=bool(state["secretlint"] and state["playwright"] and state["login"]=="ready" and state["model"]=="ready")
            else: state["reason"]="probe_process_failed"
        except RuntimeError as error:
            state["reason"]=str(error)
        except (subprocess.SubprocessError,ValueError,KeyError):
            state["reason"]="probe_unparseable"
    return state
def main()->int:
    p=argparse.ArgumentParser(); sub=p.add_subparsers(dest="cmd",required=True)
    a=sub.add_parser("prepare"); [a.add_argument(x,required=True) for x in ("--repo","--intended","--secretlint-config")]; a.add_argument("--artifact-root",default=".insane-review")
    a=sub.add_parser("send"); [a.add_argument(x,required=True) for x in ("--pack","--manifest","--approved-pack-sha","--approved-manifest-sha","--cdp-endpoint","--profile-dir","--prompt")]; a.add_argument("--timeout",type=int,default=120); a.add_argument("--artifact-root",default=".insane-review")
    a=sub.add_parser("check-env"); a.add_argument("--cdp-endpoint"); a.add_argument("--profile-dir")
    args=p.parse_args()
    try: print(json.dumps(prepare(args) if args.cmd=="prepare" else send(args) if args.cmd=="send" else check_env(args),sort_keys=True)); return 0
    except RuntimeError as e: print(f"insane-review: {e}",file=sys.stderr); return 1
if __name__=="__main__": raise SystemExit(main())
