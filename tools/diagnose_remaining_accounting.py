"""Temporary synthetic CI diagnosis of the unchanged remaining release checks."""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "ci-artifacts/jit-diagnostic"
RUNNERS = (
    "run_accounting_current_schema_validation.py",
    "run_accounting_transfer_review_validation.py",
    "run_accounting_lending_validation.py",
    "run_accounting_regular_application_validation.py",
    "run_accounting_native_origin_validation.py",
    "run_accounting_collector_application_validation.py",
    "run_accounting_disclosure_validation.py",
    "run_accounting_final_schema_validation.py",
)

def main():
    assert os.environ.get("GITHUB_ACTIONS") == "true"
    assert os.environ.get("SPINA_ALLOW_DISPOSABLE_DATABASE") == "1"
    OUT.mkdir(parents=True,exist_ok=False)
    results = []
    for runner in RUNNERS:
        started=time.monotonic()
        with (OUT / (runner+".log")).open("xb") as output:
            try:
                result=subprocess.run([sys.executable,"-B",str(ROOT/"tools"/runner)],cwd=ROOT,stdout=output,stderr=subprocess.STDOUT,timeout=2400,check=False)
                code=result.returncode
            except subprocess.TimeoutExpired:
                code="outer_timeout2400"
        row={"runner":runner,"returncode":code,"seconds":round(time.monotonic()-started,3)}
        results.append(row)
        (OUT/"remaining-results.json").write_text(json.dumps(results,indent=2)+"\n")
        print("REMAINING_RESULT",json.dumps(row),flush=True)
        print((OUT/(runner+".log")).read_text()[-16000:],flush=True)
        if code == "outer_timeout2400":
            # An interrupted runner may leave its nested pytest alive. Stop
            # here so later results cannot overlap an orphaned workload.
            break
    # Each runner's status must be inspected; retaining every later result is
    # diagnostic behavior only and never substitutes for required release CI.

if __name__=="__main__":
    main()
