from __future__ import annotations
import argparse, json, re, sys
from pathlib import Path
from typing import Any, Iterable

_SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")
_DEFAULT_ROOT = Path(r"C:\SPINA_CI_REPORTS")
_LANES = ("code-quality", "security-compliance", "reliability-performance")

def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))

def _text(path: Path, heading: str) -> None:
    print(f"\n--- {heading} ---")
    if not path.exists():
        print(f"[missing] {path.name}")
        return
    print(path.read_text(encoding="utf-8", errors="replace").rstrip() or "[empty]")

def _latest(root: Path) -> str:
    items = [p for p in root.iterdir() if p.is_dir() and _SHA_RE.fullmatch(p.name)]
    if not items:
        raise FileNotFoundError(f"no saved CI reports exist under {root}")
    items.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return items[0].name.lower()

def _commit(root: Path, value: str) -> str:
    value = value.strip().lower()
    if not value or value == "latest":
        return _latest(root)
    if not _SHA_RE.fullmatch(value):
        raise ValueError("commit SHA must be exactly 40 hexadecimal characters")
    if not (root / value).is_dir():
        raise FileNotFoundError(f"no saved CI report exists for commit {value}")
    return value

def _metadata(lane_dir: Path) -> None:
    p = lane_dir / "_metadata.json"
    if p.exists():
        try:
            m = _load(p)
            print(f"metadata: workflow={m.get('workflow_name','?')} run_id={m.get('run_id','?')} persisted_at_utc={m.get('persisted_at_utc','?')}")
        except Exception as exc:
            print(f"metadata unreadable: {exc}")

def _ruff(d: Path) -> None:
    print("\n--- Ruff findings ---")
    p = d / "ruff.json"
    if not p.exists():
        print("[missing] ruff.json"); return
    try: items = _load(p)
    except Exception as exc:
        print(f"ruff.json unreadable: {exc}"); return
    if not isinstance(items, list):
        print("unexpected Ruff JSON shape"); return
    print(f"count: {len(items)}")
    for i, x in enumerate(items, 1):
        if not isinstance(x, dict): print(f"{i}. {x!r}"); continue
        loc = x.get("location") or {}
        row = loc.get("row","?") if isinstance(loc,dict) else "?"
        col = loc.get("column","?") if isinstance(loc,dict) else "?"
        msg = str(x.get("message","")).replace("\n"," ")
        fix = " fix-available" if x.get("fix") else ""
        print(f"{i}. {x.get('filename','?')}:{row}:{col} [{x.get('code','?')}]{fix} {msg}")

def _pyright(d: Path) -> None:
    print("\n--- Pyright diagnostics ---")
    p = d / "pyright.json"
    if not p.exists():
        print("[missing] pyright.json"); return
    try: data = _load(p)
    except Exception as exc:
        print(f"pyright.json unreadable: {exc}"); return
    if not isinstance(data, dict):
        print("unexpected Pyright JSON shape"); return
    print(f"summary: {data.get('summary',{})}")
    items = data.get("generalDiagnostics") or []
    if not isinstance(items,list): items = []
    print(f"diagnostic_count: {len(items)}")
    for i,x in enumerate(items,1):
        if not isinstance(x,dict): print(f"{i}. {x!r}"); continue
        start=((x.get("range") or {}).get("start") or {})
        line=int(start.get("line",-1))+1 if isinstance(start,dict) else "?"
        char=int(start.get("character",-1))+1 if isinstance(start,dict) else "?"
        msg=str(x.get("message","")).replace("\n"," ")
        print(f"{i}. {x.get('file','?')}:{line}:{char} [{x.get('severity','?')}] {msg}")

def _compress(lines: Iterable[int]) -> str:
    vals=sorted({int(v) for v in lines})
    if not vals: return "-"
    out=[]; start=prev=vals[0]
    for v in vals[1:]:
        if v==prev+1: prev=v; continue
        out.append(str(start) if start==prev else f"{start}-{prev}")
        start=prev=v
    out.append(str(start) if start==prev else f"{start}-{prev}")
    return ",".join(out)

def _coverage(d: Path) -> None:
    print("\n--- Coverage details ---")
    p=d/"coverage.json"
    if not p.exists():
        print("[missing] coverage.json"); return
    try: data=_load(p)
    except Exception as exc:
        print(f"coverage.json unreadable: {exc}"); return
    if not isinstance(data,dict):
        print("unexpected coverage JSON shape"); return
    print(f"totals: {data.get('totals',{})}")
    rows=[]
    files=data.get("files") or {}
    if isinstance(files,dict):
        for name,detail in files.items():
            if not isinstance(detail,dict): continue
            s=detail.get("summary") or {}
            rows.append((float(s.get("percent_covered",0.0)),name,detail))
    rows.sort(key=lambda x:(x[0],x[1].lower()))
    print(f"file_count: {len(rows)}")
    for pct,name,detail in rows:
        s=detail.get("summary") or {}
        print(f"{pct:6.2f}% {name} covered={s.get('covered_lines','?')}/{s.get('num_statements','?')} missing={_compress(detail.get('missing_lines') or [])}")

def _bandit(d: Path) -> None:
    print("\n--- Bandit findings ---")
    p=d/"bandit.json"
    if not p.exists():
        print("[missing] bandit.json"); return
    try: data=_load(p)
    except Exception as exc:
        print(f"bandit.json unreadable: {exc}"); return
    if not isinstance(data,dict):
        print("unexpected Bandit JSON shape"); return
    metrics=data.get("metrics") or {}
    if isinstance(metrics,dict): print(f"metrics: {metrics.get('_totals',{})}")
    items=data.get("results") or []
    if not isinstance(items,list): items=[]
    print(f"count: {len(items)}")
    for i,x in enumerate(items,1):
        if not isinstance(x,dict): print(f"{i}. {x!r}"); continue
        issue=str(x.get("issue_text","")).replace("\n"," ")
        print(f"{i}. {x.get('filename','?')}:{x.get('line_number','?')} [{x.get('test_id','?')}] severity={x.get('issue_severity','?')} confidence={x.get('issue_confidence','?')} {issue}")

def _audit_vulns(data: Any):
    deps = data.get("dependencies") or data.get("packages") or [] if isinstance(data,dict) else data
    if not isinstance(deps,list): return
    for dep in deps:
        if not isinstance(dep,dict): continue
        vulns=dep.get("vulns") or dep.get("vulnerabilities") or []
        if not isinstance(vulns,list): continue
        for v in vulns:
            if isinstance(v,dict): yield str(dep.get("name","?")),str(dep.get("version","?")),v

def _audit(d: Path) -> None:
    print("\n--- pip-audit vulnerabilities ---")
    p=d/"pip-audit.json"
    if not p.exists():
        print("[missing] pip-audit.json"); return
    try: data=_load(p)
    except Exception as exc:
        print(f"pip-audit.json unreadable: {exc}"); return
    items=list(_audit_vulns(data))
    print(f"count: {len(items)}")
    for i,(name,version,v) in enumerate(items,1):
        desc=str(v.get("description","")).replace("\n"," ")
        if len(desc)>500: desc=desc[:497]+"..."
        print(f"{i}. {name}=={version} id={v.get('id') or v.get('aliases') or '?'} fix_versions={v.get('fix_versions') or v.get('fixes') or []} {desc}".rstrip())

def render(d: Path, lane: str) -> None:
    print(f"\n\n========== {lane.upper()} =========="); _metadata(d)
    if lane=="code-quality":
        _text(d/"summary.md","Code Quality summary"); _ruff(d); _text(d/"ruff-format.txt","Ruff format output"); _pyright(d); _coverage(d)
    elif lane=="security-compliance":
        _text(d/"summary.md","Security & Compliance summary"); _bandit(d); _audit(d)
        print("\n--- Gitleaks ---\nRaw secret values are intentionally not persisted or replayed. Use the Security & Compliance job log/summary for the redacted Gitleaks outcome.")
    else:
        _text(d/"pytest-durations.txt","Reliability / performance regression output")

def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--root",default=str(_DEFAULT_ROOT))
    ap.add_argument("--commit-sha",default="latest")
    ap.add_argument("--lane",default="all",choices=("all",)+_LANES)
    a=ap.parse_args()
    root=Path(a.root)
    if not root.is_dir():
        print(f"SPINA CI report root does not exist: {root}",file=sys.stderr); return 2
    try: sha=_commit(root,a.commit_sha)
    except (FileNotFoundError,ValueError) as exc:
        print(f"SPINA CI deep review failed: {exc}",file=sys.stderr); return 2
    print("SPINA CI DEEP REVIEW"); print(f"report_root: {root}"); print(f"commit_sha: {sha}")
    lanes=_LANES if a.lane=="all" else (a.lane,)
    found=0
    for lane in lanes:
        d=root/sha/lane
        if not d.is_dir():
            print(f"\n========== {lane.upper()} ==========\n[missing] no saved local report at {d}")
            continue
        found+=1; render(d,lane)
    return 0 if found else 1

if __name__=="__main__":
    raise SystemExit(main())
