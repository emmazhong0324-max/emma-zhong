import os
os.environ.pop("OPENAI_API_KEY",None)
from fastapi.testclient import TestClient
from app.main import app

client=TestClient(app)

def test_health():
    assert client.get('/health').json()=={'status':'ok'}

def test_judge_fallback():
    r=client.post('/api/judge',data={'dataset_type':'立项申请书','intent':'判断创新程度是否足够'},files=[('files',('x.txt','本项目具有首创技术突破，已申请专利。','text/plain'))])
    assert r.status_code==200
    body=r.json()['results'][0]
    assert body['label'] in ['通过','不通过']
    assert body['dataset_type']=='立项申请书'

def test_reject_bad_type():
    r=client.post('/api/judge',data={'dataset_type':'未知','intent':'判断'},files=[('files',('x.txt','内容','text/plain'))])
    assert r.status_code==400

