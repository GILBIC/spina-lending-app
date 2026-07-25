from __future__ import annotations
import ast
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
DESKTOP=ROOT/"OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
MODULE=ROOT/"spina_app"/"loan_context_queries.py"
TARGETS=('_set_last_error', 'get_last_error', 'set_default_loan_type', '_effective_lt', 'get_audit_new_loan_rows', 'get_all_areas')
def main():
 mt=MODULE.read_text(); t=ast.parse(mt); fs={n.name:n for n in t.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
 assert set(TARGETS)<=set(fs), set(TARGETS)-set(fs)
 dt=DESKTOP.read_text(); d=ast.parse(dt); cls=next(n for n in d.body if isinstance(n,ast.ClassDef) and n.name=="LoanDB")
 remain={n.name for n in cls.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
 assert not(set(TARGETS)&remain), set(TARGETS)&remain
 pos=[]
 for x in ast.walk(d):
  if isinstance(x,ast.Assign) and len(x.targets)==1 and isinstance(x.targets[0],ast.Attribute) and isinstance(x.targets[0].value,ast.Name) and x.targets[0].value.id=="LoanDB" and x.targets[0].attr in TARGETS: pos.append((x.targets[0].attr,x.lineno))
 assert {n for n,_ in pos}==set(TARGETS), pos
 assert all(l>(cls.end_lineno or cls.lineno) for _,l in pos), pos
 print(f"Wave 33 loan-context structural regression passed: {len(TARGETS)} methods.")
if __name__=="__main__": main()
