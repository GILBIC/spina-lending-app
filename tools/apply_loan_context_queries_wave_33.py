from __future__ import annotations
import ast, hashlib, json, subprocess, textwrap
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
DESKTOP=ROOT/'OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py'
MODULE=ROOT/'spina_app'/'loan_context_queries.py'
TEST=ROOT/'tools'/'test_loan_context_queries_wave_33.py'
BOOT=ROOT/'.github'/'workflows'/'loan-context-queries-wave-33-bootstrap.yml'
PERM=ROOT/'.github'/'workflows'/'loan-context-queries-wave-33.yml'
EXPECTED_BASE='d2406bdf087b80c437835805f7c42d4174b04b33'
TARGETS=('_set_last_error','get_last_error','set_default_loan_type','_effective_lt','get_audit_new_loan_rows','get_all_areas')
ALLOWED={'.github/workflows/loan-context-queries-wave-33-bootstrap.yml','tools/apply_loan_context_queries_wave_33.py'}
def run(*a): return subprocess.check_output(a,cwd=ROOT,text=True).strip()
def norm(s): return textwrap.dedent(s).strip()+'\n'
def sha(s): return hashlib.sha256(s.encode()).hexdigest()
def main():
 subprocess.run(['git','fetch','origin','main','--quiet'],cwd=ROOT,check=True)
 mb=run('git','merge-base','HEAD','origin/main')
 if mb!=EXPECTED_BASE: raise SystemExit(f'Unexpected main base {mb}')
 changed={x.strip() for x in run('git','diff','--name-only',f'{EXPECTED_BASE}..HEAD').splitlines() if x.strip()}
 if changed-ALLOWED: raise SystemExit(f'Unexpected files: {sorted(changed-ALLOWED)}')
 text=DESKTOP.read_text(encoding='utf-8-sig'); tree=ast.parse(text)
 cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='LoanDB')
 methods={n.name:n for n in cls.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name in TARGETS}
 missing=[n for n in TARGETS if n not in methods]
 if missing: raise SystemExit(f'Missing: {missing}')
 src={}; hashes={}; total=0
 for name in TARGETS:
  n=methods[name]; seg=ast.get_source_segment(text,n)
  if not seg: raise SystemExit(name)
  src[name]=norm(seg); hashes[name]=sha(src[name]); total+=(n.end_lineno or n.lineno)-n.lineno+1
 if not 50<=total<=400: raise SystemExit(f'Unexpected size {total}')
 header='''"""LoanDB context and read-only area/audit helpers extracted in Wave 33."""\nfrom __future__ import annotations\n_LOAN_CONTEXT_DEPENDENCIES={}\n_PROTECTED_GLOBALS={"__builtins__","__cached__","__doc__","__file__","__loader__","__name__","__package__","__spec__","_LOAN_CONTEXT_DEPENDENCIES","_PROTECTED_GLOBALS","configure_loan_context_dependencies"}\ndef configure_loan_context_dependencies(namespace):\n    _LOAN_CONTEXT_DEPENDENCIES.clear()\n    _LOAN_CONTEXT_DEPENDENCIES.update(namespace)\n    for name,value in namespace.items():\n        if name not in _PROTECTED_GLOBALS:\n            globals()[name]=value\n\n'''
 MODULE.write_text(header+'LOAN_CONTEXT_SOURCE_SHA256 = '+json.dumps(hashes,indent=4,sort_keys=True)+'\n\n'+'\n\n'.join(src[n].rstrip() for n in TARGETS)+'\n',encoding='utf-8')
 imports=',\n    '.join(f'{n} as _loan_context_{n}' for n in TARGETS)
 assigns='\n'.join(f'LoanDB.{n} = _loan_context_{n}' for n in TARGETS)
 wiring=f'''\n# Wave 33: LoanDB context and read-only area/audit helpers.\nfrom spina_app.loan_context_queries import (\n    configure_loan_context_dependencies as _configure_loan_context_wave33_dependencies,\n    {imports},\n)\n_configure_loan_context_wave33_dependencies(globals())\n{assigns}\n\n'''
 lines=text.splitlines(keepends=True); spans={n.lineno:(n.end_lineno or n.lineno) for n in methods.values()}; out=[]; i=1; inserted=False; class_end=cls.end_lineno or cls.lineno
 while i<=len(lines):
  if i in spans: out.append('\n'); i=spans[i]+1; continue
  if i==class_end+1 and not inserted: out.append(wiring); inserted=True
  out.append(lines[i-1]); i+=1
 if not inserted: out.append(wiring)
 rewritten=''.join(out); ast.parse(rewritten); DESKTOP.write_text(rewritten,encoding='utf-8')
 test=f'''from __future__ import annotations\nimport ast,hashlib,textwrap\nfrom pathlib import Path\nROOT=Path(__file__).resolve().parents[1]\nDESKTOP=ROOT/"OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"\nMODULE=ROOT/"spina_app"/"loan_context_queries.py"\nTARGETS={TARGETS!r}\nEXPECTED={hashes!r}\nTOTAL={total}\ndef h(s): return hashlib.sha256((textwrap.dedent(s).strip()+"\\n").encode()).hexdigest()\ndef main():\n mt=MODULE.read_text(); t=ast.parse(mt); fs={{n.name:n for n in t.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}}\n assert set(TARGETS)<=set(fs)\n assert sum((fs[n].end_lineno or fs[n].lineno)-fs[n].lineno+1 for n in TARGETS)==TOTAL\n for n in TARGETS:\n  seg=ast.get_source_segment(mt,fs[n]); assert seg and h(seg)==EXPECTED[n]\n dt=DESKTOP.read_text(); d=ast.parse(dt); cls=next(n for n in d.body if isinstance(n,ast.ClassDef) and n.name=="LoanDB")\n assert not(set(TARGETS)&{{n.name for n in cls.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}})\n pos=[]\n for x in ast.walk(d):\n  if isinstance(x,ast.Assign) and len(x.targets)==1 and isinstance(x.targets[0],ast.Attribute) and isinstance(x.targets[0].value,ast.Name) and x.targets[0].value.id=="LoanDB" and x.targets[0].attr in TARGETS: pos.append((x.targets[0].attr,x.lineno))\n assert {{n for n,_ in pos}}==set(TARGETS) and all(l>(cls.end_lineno or cls.lineno) for _,l in pos)\n forbidden=("INSERT INTO","DELETE FROM","CREATE TABLE","ALTER TABLE","DROP TABLE",".COMMIT(",".ROLLBACK(","WRITE_TEXT(","WRITE_BYTES(",".UNLINK(")\n for n in TARGETS:\n  seg=(ast.get_source_segment(mt,fs[n]) or "").upper()\n  for token in forbidden: assert token not in seg,(n,token)\n print(f"Wave 33 loan-context regression passed: {{len(TARGETS)}} methods / {{TOTAL}} lines.")\nif __name__=="__main__": main()\n'''
 TEST.write_text(test,encoding='utf-8')
 PERM.write_text('''name: Loan context queries Wave 33\non: [pull_request]\npermissions:\n  contents: read\njobs:\n  validate:\n    if: github.head_ref == 'agent/loan-context-queries-wave-33'\n    runs-on: [self-hosted, Windows, X64]\n    timeout-minutes: 35\n    steps:\n      - uses: actions/checkout@v4\n        with:\n          ref: ${{ github.event.pull_request.head.sha }}\n          fetch-depth: 0\n      - shell: cmd\n        run: |\n          python -m py_compile OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py\n          python -m py_compile spina_app\\loan_context_queries.py\n          python -m py_compile tools\\test_loan_context_queries_wave_33.py\n          python -m compileall -q spina_app\n      - shell: cmd\n        run: python -m tools.test_loan_context_queries_wave_33\n      - uses: ./.github/actions/architecture-map-check\n      - shell: cmd\n        run: |\n          if not exist artifacts mkdir artifacts\n          python tools\\redundancy_audit.py OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py --json artifacts/wave-33-redundancy.json\n          python tools\\spina_quality_audit.py OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py --json artifacts/wave-33-quality.json\n      - uses: actions/upload-artifact@v4\n        with:\n          name: loan-context-queries-wave-33-reports\n          path: |\n            artifacts/wave-33-redundancy.json\n            artifacts/wave-33-quality.json\n            architecture-map.json\n            docs/architecture\n          if-no-files-found: error\n''',encoding='utf-8')
 if BOOT.exists(): BOOT.unlink()
 Path(__file__).unlink()
 print(f'Wave 33 extracted {len(TARGETS)} methods ({total} lines).')
if __name__=='__main__': main()
