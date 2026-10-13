"""Temporary CI-only diagnostic: exact synthetic schema and one changed GUC."""
import json
import os
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from uuid import uuid4

import psycopg
from psycopg import sql
import run_stage5d17_disposable_postgres_validation as bootstrap
import run_accounting_adapters_disposable_validation as adapters

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "ci-artifacts/jit-diagnostic"

def main():
    assert os.environ.get("GITHUB_ACTIONS") == "true"
    assert os.environ.get("SPINA_ALLOW_DISPOSABLE_DATABASE") == "1"
    params = bootstrap._safe_local_connection_params(os.environ["ACCOUNTING_CONTROLS_DATABASE_URL"])
    assert params["dbname"] == "postgres"
    assert params["host"] == "127.0.0.1"
    assert not {"options", "passfile"}.intersection(params)
    OUT.mkdir(parents=True, exist_ok=False)
    bootstrap._clear_endpoint_environment()
    bootstrap.BOOTSTRAP_THROUGH = 148
    name = "spina_treasury_validation_" + uuid4().hex[:24]
    admin_url = bootstrap._conninfo_for_database(params, "postgres")
    test_url = bootstrap._conninfo_for_database(params, name)
    created = False
    results = []
    try:
        with psycopg.connect(admin_url, autocommit=True) as admin:
            admin.execute(sql.SQL("CREATE DATABASE {} TEMPLATE template0").format(sql.Identifier(name)))
        created = True
        bootstrap._install_supabase_auth_prerequisite(test_url)
        bootstrap._bootstrap_database(test_url)
        with psycopg.connect(test_url) as connection:
            connection.execute((ROOT / "gilbic_backend/sql/0150_add_reporting_evidence.sql").read_text())
        with psycopg.connect(test_url) as connection:
            settings = connection.execute("SELECT version(),current_setting('jit'),pg_jit_available(),current_setting('jit_above_cost')").fetchone()
            print("POSTGRES_DIAGNOSTIC_SETTINGS", json.dumps(settings), flush=True)
        env = {k:v for k,v in os.environ.items() if not k.startswith(("GILBIC_", "SPINA_", "SUPABASE_", "PG")) and k not in {"DATABASE_URL","POSTGRES_URL","POSTGRES_URL_NON_POOLING","ACCOUNTING_CONTROLS_DATABASE_URL"}}
        env.update(GILBIC_DATABASE_URL=test_url,GILBIC_TEST_DATABASE_URL=test_url,SPINA_ALLOW_DISPOSABLE_DATABASE="1",SPINA_CURRENT_SCHEMA_THROUGH="148",PYTHONDONTWRITEBYTECODE="1",PYTHONPATH=os.pathsep.join(str(ROOT / x) for x in ("gilbic_backend/src","spina_backend_mobile/src","gilbic_backend/tests","tools",".")))
        focus = ["test_period_close_postgres.py::test_formal_period_close_moves_profit_to_retained_earnings_and_locks_period"]
        for label, jit, tests, timeout in (("focused-on","on",focus,100),("focused-off","off",focus,100),("full-off","off",adapters.TESTS,300)):
            env["PGOPTIONS"] = "-c jit=" + jit + " -c statement_timeout=45000 -c lock_timeout=5000"
            started = time.monotonic()
            junit = OUT / (label+".xml")
            command = [sys.executable,"-B","-m","pytest","-vv","-p","no:cacheprovider","-o","faulthandler_timeout=40","--durations=15","--junitxml",str(junit),*[str(ROOT / "gilbic_backend/tests" / test) for test in tests]]
            with (OUT / (label+".log")).open("xb") as output:
                try:
                    result = subprocess.run(command,cwd=ROOT,env=env,stdout=output,stderr=subprocess.STDOUT,timeout=timeout,check=False)
                    code = result.returncode
                except subprocess.TimeoutExpired:
                    code = "timeout"
            counts = [dict(s.attrib) for s in ET.parse(junit).getroot().iter("testsuite")] if junit.exists() else []
            row = {"label":label,"jit":jit,"returncode":code,"seconds":round(time.monotonic()-started,3),"counts":counts}
            results.append(row)
            print("DIAGNOSTIC_RESULT",json.dumps(row),flush=True)
            print((OUT / (label+".log")).read_text()[-14000:],flush=True)
    finally:
        if created:
            with psycopg.connect(admin_url,autocommit=True) as admin:
                assert name.startswith("spina_treasury_validation_") and len(name.rsplit("_",1)[1]) == 24
                admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))
        (OUT / "results.json").write_text(json.dumps({"results":results,"owned_database_removed":created},indent=2)+"\n")

if __name__ == "__main__":
    main()
