"""Temporary exact restore-test comparison on historical and final schemas."""
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

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"ci-artifacts/jit-diagnostic"

def main():
    assert os.environ.get("GITHUB_ACTIONS")=="true"
    assert os.environ.get("SPINA_ALLOW_DISPOSABLE_DATABASE")=="1"
    params=bootstrap._safe_local_connection_params(os.environ["ACCOUNTING_CONTROLS_DATABASE_URL"])
    assert params["dbname"]=="postgres" and params["host"]=="127.0.0.1"
    assert not {"options","passfile"}.intersection(params)
    pg_bin=os.environ["SPINA_POSTGRES_BIN"]
    bootstrap._clear_endpoint_environment()
    OUT.mkdir(parents=True,exist_ok=False)
    results=[]
    for through in (152,171):
        name="spina_treasury_validation_"+uuid4().hex[:24]
        admin_url=bootstrap._conninfo_for_database(params,"postgres")
        test_url=bootstrap._conninfo_for_database(params,name)
        created=False
        try:
            with psycopg.connect(admin_url,autocommit=True) as admin:
                admin.execute(sql.SQL("CREATE DATABASE {} TEMPLATE template0").format(sql.Identifier(name)))
            created=True
            bootstrap.BOOTSTRAP_THROUGH=through
            bootstrap._install_supabase_auth_prerequisite(test_url)
            bootstrap._bootstrap_database(test_url)
            env={k:v for k,v in os.environ.items() if not k.startswith(("GILBIC_","SPINA_","SUPABASE_","PG")) and k not in {"DATABASE_URL","POSTGRES_URL","POSTGRES_URL_NON_POOLING","ACCOUNTING_CONTROLS_DATABASE_URL"}}
            env.update(GILBIC_DATABASE_URL=test_url,GILBIC_TEST_DATABASE_URL=test_url,SPINA_ALLOW_DISPOSABLE_DATABASE="1",SPINA_CURRENT_SCHEMA_THROUGH=str(through),SPINA_POSTGRES_BIN=pg_bin,PYTHONDONTWRITEBYTECODE="1",PGOPTIONS="-c jit=off",PYTHONPATH=os.pathsep.join(str(ROOT/x) for x in ("gilbic_backend/src","spina_backend_mobile/src","gilbic_backend/tests","tools",".")))
            junit=OUT/(str(through)+".xml")
            started=time.monotonic()
            with (OUT/(str(through)+".log")).open("xb") as output:
                try:
                    result=subprocess.run([sys.executable,"-B","-m","pytest","-vv","-p","no:cacheprovider","--junitxml",str(junit),str(ROOT/"gilbic_backend/tests/test_current_schema_accounting_cycle_postgres.py")+"::test_current_schema_populated_private_evidence_restores_exactly"],cwd=ROOT,env=env,stdout=output,stderr=subprocess.STDOUT,timeout=900,check=False)
                    code=result.returncode
                except subprocess.TimeoutExpired:
                    code="timeout900"
            counts=[dict(s.attrib) for s in ET.parse(junit).getroot().iter("testsuite")] if junit.exists() else []
            row={"schema":through,"returncode":code,"seconds":round(time.monotonic()-started,3),"counts":counts}
            results.append(row)
            (OUT/"restore-results.json").write_text(json.dumps(results,indent=2)+"\n")
            print("RESTORE_RESULT",json.dumps(row),flush=True)
            print((OUT/(str(through)+".log")).read_text()[-14000:],flush=True)
        finally:
            if created:
                with psycopg.connect(admin_url,autocommit=True) as admin:
                    assert name.startswith("spina_treasury_validation_") and len(name.rsplit("_",1)[1])==24
                    admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))
        if code=="timeout900":
            break

if __name__=="__main__":
    main()
