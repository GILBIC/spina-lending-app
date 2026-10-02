import base64
import json
from datetime import datetime,timezone
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from gilbic_backend.treasury_api import create_treasury_router,treasury_actor,treasury_repository_dependency
from treasury_test_support import treasury,PDF,version


def client(f,actor=None):
    app=FastAPI()
    app.include_router(create_treasury_router())
    app.dependency_overrides[treasury_actor]=lambda:actor or f['client_actor']
    app.dependency_overrides[treasury_repository_dependency]=lambda:f['service']
    return TestClient(app)


def headers(f,request_id=None):
    metadata=dict(request_id=str(request_id or uuid4()),account_id=str(f['account_id']),account_version=version(f),client_id=str(f['client_id']),
        loan_ids=[str(f['loan_id'])],amount='400.00',reference='000009',claimed_at='2026-10-02T00:00:00Z',sender_note='Relative payer is allowed')
    return {'Content-Type':'application/pdf','X-Treasury-Metadata':base64.b64encode(json.dumps(metadata).encode()).decode()},metadata


def test_raw_own_claim_alias_recovery_and_private_content(treasury):
    f=treasury
    browser=client(f)
    upload_headers,metadata=headers(f)
    response=browser.post('/api/v1/treasury/claims',headers=upload_headers,content=PDF)
    assert response.status_code==201,response.text
    result=response.json()['data']
    assert result['action']=='claim_submit'
    assert result['result']['claim']['official_payment_posted'] is False
    assert browser.get('/api/mobile/v1/treasury/requests/'+metadata['request_id']).json()['data']==result
    claim=result['result']['claim']
    content=browser.get(f"/api/v1/treasury/claims/{claim['id']}/versions/1/content")
    assert content.content==PDF and content.headers['cache-control']=='no-store'
    # A claim uploader has no recipient-side verification authority.
    assert browser.post('/api/v1/treasury/evidence',params={'account_id':str(f['account_id']),'request_id':str(uuid4())},
                        headers={'Content-Type':'application/pdf'},content=PDF).status_code==403


def test_workspace_client_upload_projection_hides_private_wallet(treasury):
    response=client(treasury).get('/api/v1/treasury/workspace')
    assert response.status_code==200,response.text
    workspace=response.json()['data']
    selected=next(row for row in workspace['accounts'] if row['id']==str(treasury['account_id']))
    assert selected['balance'] is None
    assert selected['actions']==['claim_submit','claim_version']
    assert workspace['capabilities']['claim_submit'] is True
    assert workspace['source_choices']==[]
    assert client(treasury).get(f"/api/v1/treasury/accounts/{treasury['account_id']}/events").status_code==403


def test_claim_upload_invalid_media_metadata_and_wrong_record_are_denied(treasury):
    browser=client(treasury)
    upload_headers,metadata=headers(treasury)
    assert browser.post('/api/v1/treasury/claims',headers=upload_headers|{'Content-Type':'text/plain'},content=PDF).status_code==415
    malformed=metadata|{'verified_by_user_id':str(uuid4())}
    assert browser.post('/api/v1/treasury/claims',headers=upload_headers|{
        'X-Treasury-Metadata':base64.b64encode(json.dumps(malformed).encode()).decode()},content=PDF).status_code==422
    assert browser.get('/api/v1/treasury/claims/'+str(uuid4())).status_code==403
    assert browser.get('/api/v1/treasury/requests/'+str(uuid4())).json()=={'success':True,'data':None}


def test_owner_receipt_choices_and_opening_recovery_are_scoped(treasury):
    f=treasury
    browser=client(f,f['owner'])
    workspace=browser.get('/api/v1/treasury/workspace').json()['data']
    choice=next(row for row in workspace['borrower_choices'] if row['client_id']==str(f['client_id']))
    assert str(f['account_id']) in choice['allowed_account_ids']
    assert any(row['loan_id']==str(f['loan_id']) for row in choice['loans'])
    assert any(row['user_id']==str(f['owner'].user_id) for row in workspace['staff_choices'])
    response=browser.get(f"/api/v1/treasury/accounts/{f['account_id']}/openings")
    assert response.status_code==200,response.text
    assert response.json()['data']['total_count']==0
    own_workspace=client(f).get('/api/v1/treasury/workspace').json()['data']
    assert own_workspace['staff_choices']==[]
    assert client(f).get(f"/api/v1/treasury/accounts/{f['account_id']}/openings").status_code==403
