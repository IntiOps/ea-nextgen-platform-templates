from concurrent.futures import ThreadPoolExecutor
import importlib.util
import io
import json
from pathlib import Path
import shutil
import sys
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'components/application/python-request-service'))
from service import Store, Conflict
from app import application
spec = importlib.util.spec_from_file_location('catalog_tool', ROOT/'tools/catalog.py')
catalog = importlib.util.module_from_spec(spec)
spec.loader.exec_module(catalog)


def test_all_models_have_valid_typed_relationships():
    result = catalog.validate()
    assert len(result['blueprints']) == 12
    assert len(result['components']) == 3
    assert result['blueprints']['rag-knowledge-assistant']['gaps']


@pytest.mark.parametrize('mutation', ['endpoint', 'digest', 'escape', 'unknown_type'])
def test_invalid_catalog_is_rejected(tmp_path, mutation):
    copy = tmp_path/'repo'
    shutil.copytree(ROOT, copy, ignore=shutil.ignore_patterns('__pycache__','.pytest_cache','.git','node_modules'))
    if mutation == 'endpoint':
        p = copy/'blueprints/solution/web-api-data/blueprint.json'
        value = json.loads(p.read_text());value['relationships'][0]['target'] = 'database'
    elif mutation == 'unknown_type':
        p = copy/'blueprints/solution/web-api-data/blueprint.json'
        value = json.loads(p.read_text());value['nodes'][0]['type'] = 'invented_type'
    else:
        p = copy/'components/manifests/request-service.json'
        value = json.loads(p.read_text())
        if mutation == 'digest': value['files'][0]['sha256'] = '0'*64
        else: value['files'][0]['path'] = '../outside'
    p.write_text(json.dumps(value))
    with pytest.raises(ValueError): catalog.validate(copy)


def test_persistence_and_missing_request(tmp_path):
    file = tmp_path/'data.sqlite'
    first = Store(file).create_request('Purchase approval')
    assert Store(file).get_request(first['id']) == first
    assert Store(file).get_request("' OR 1=1 --") is None


def test_duplicate_job_and_conflict(tmp_path):
    store = Store(tmp_path/'data.sqlite')
    first = store.enqueue('key','hello')
    assert store.enqueue('key','hello') == first
    with pytest.raises(Conflict): store.enqueue('key','different')
    assert store.work_once()['result'] == 'HELLO'
    assert store.work_once() is None
    assert store.get_job(first['id'])['status'] == 'complete'


def test_parallel_workers_process_each_job_once(tmp_path):
    store = Store(tmp_path/'data.sqlite')
    ids = {store.enqueue(str(i),str(i))['id'] for i in range(8)}
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: store.work_once(), range(12)))
    completed = [row['id'] for row in results if row]
    assert len(completed) == len(set(completed)) == 8
    assert set(completed) == ids


def test_http_create_read_and_bad_payload(tmp_path):
    app = application(Store(tmp_path/'data.sqlite'))
    def call(method,path,body=b'',**headers):
        response=[]
        data=app({'REQUEST_METHOD':method,'PATH_INFO':path,'CONTENT_LENGTH':str(len(body)),
                  'wsgi.input':io.BytesIO(body),**headers},lambda status,h:response.append(status))
        return response[0],json.loads(b''.join(data))
    status,item=call('POST','/requests',b'{"title":"Demo"}')
    assert status == '201 Created'
    assert call('GET','/requests/'+item['id'])[1] == item
    assert call('POST','/requests',b'[]')[0] == '400 Bad Request'
    assert call('POST','/jobs',b'{"text":"hello"}')[0] == '400 Bad Request'
    assert call('GET','/requests/missing')[0] == '404 Not Found'


def test_blueprint_json_schema():
    from jsonschema import Draft202012Validator
    schema = json.loads((ROOT/'schemas/blueprint.schema.json').read_text())
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    for file in ROOT.glob('blueprints/*/*/blueprint.json'):
        validator.validate(json.loads(file.read_text()))


def test_demo_cannot_silently_follow_changed_architecture(tmp_path):
    copy = tmp_path/'repo'
    shutil.copytree(ROOT, copy, ignore=shutil.ignore_patterns('__pycache__','.pytest_cache','.git','node_modules'))
    path = copy/'blueprints/solution/web-api-data/blueprint.json'
    doc = json.loads(path.read_text()); doc['purpose'] = 'Changed business intent'
    path.write_text(json.dumps(doc))
    with pytest.raises(ValueError, match='blueprint digest'):
        catalog.validate(copy)
