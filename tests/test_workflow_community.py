import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from backend import main
from backend.database import Base, User, CommunityWorkflow
from backend.security import hash_secret, issue_token

@pytest.fixture()
def community_client():
    engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session=sessionmaker(bind=engine,autoflush=False,expire_on_commit=False)
    with Session() as db:
        owner=User(email='owner@example.test',password_hash=hash_secret('not-a-real-password'),role='admin')
        reader=User(email='reader@example.test',password_hash=hash_secret('not-a-real-password'),role='technician')
        db.add_all([owner,reader]);db.commit();db.refresh(owner);db.refresh(reader)
        owner_token=issue_token(str(owner.id),owner.role);reader_token=issue_token(str(reader.id),reader.role);owner_id=owner.id
    def override_db():
        with Session() as db: yield db
    main.app.dependency_overrides[main.db_session]=override_db
    try:
        with TestClient(main.app) as client: yield client,owner_token,reader_token,Session,owner_id
    finally:
        main.app.dependency_overrides.pop(main.db_session,None);Base.metadata.drop_all(engine);engine.dispose()

def workflow(is_public=False,local_only=True):
    return {'schema_version':1,'coordinate_space':'normalized_0_to_1','name':'Private reset','tags':['support'],'notes':'safe summary','is_public':is_public,'privacy':{'typed_text_recorded':False,'clipboard_recorded':False,'local_only':local_only},'steps':[{'action':'mouse_down','x':0.5,'y':0.5}]}

def test_private_workflow_rejected_before_database_write(community_client):
    client,token,_,Session,_=community_client
    response=client.post('/api/workflows/publish',headers={'Authorization':'Bearer '+token},json={'workflow':workflow(False,True)})
    assert response.status_code==403
    with Session() as db: assert db.scalar(select(CommunityWorkflow)) is None

def test_local_only_flag_cannot_be_overridden(community_client):
    client,token,_,Session,_=community_client
    response=client.post('/api/workflows/publish',headers={'Authorization':'Bearer '+token},json={'workflow':workflow(True,True)})
    assert response.status_code==403
    with Session() as db: assert db.scalar(select(CommunityWorkflow)) is None

def test_public_workflow_visible_and_import_is_local(community_client):
    client,owner,reader,_,_=community_client
    response=client.post('/api/workflows/publish',headers={'Authorization':'Bearer '+owner},json={'workflow':workflow(True,False)})
    assert response.status_code==200
    wid=response.json()['id']
    listed=client.get('/api/workflows/community',headers={'Authorization':'Bearer '+reader})
    assert listed.status_code==200 and listed.json()[0]['id']==wid
    imported=client.post('/api/workflows/import/'+str(wid),headers={'Authorization':'Bearer '+reader},json={})
    assert imported.status_code==200 and imported.json()['workflow']['is_public'] is False
    assert imported.json()['workflow']['privacy']['local_only'] is True

def test_nonpublic_rows_never_listed_or_imported(community_client):
    client,_,reader,Session,owner_id=community_client
    with Session() as db:
        db.add(CommunityWorkflow(owner_id=owner_id,name='private',description='',tags=[],workflow=workflow(False,True),is_public=False));db.commit()
        wid=db.scalar(select(CommunityWorkflow.id))
    listed=client.get('/api/workflows/community',headers={'Authorization':'Bearer '+reader})
    assert listed.status_code==200 and all(x['id']!=wid for x in listed.json())
    assert client.post('/api/workflows/import/'+str(wid),headers={'Authorization':'Bearer '+reader},json={}).status_code==404

def test_sensitive_fields_and_unauthenticated_requests_rejected(community_client):
    client,token,_,_,_=community_client
    bad=workflow(True,False);bad['steps'][0]['typed_text']='secret'
    assert client.post('/api/workflows/publish',headers={'Authorization':'Bearer '+token},json={'workflow':bad}).status_code==422
    assert client.get('/api/workflows/community').status_code==401
