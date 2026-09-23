from pathlib import Path
import importlib.util
import json

ROOT=Path(__file__).resolve().parents[1]


def test_vendored_components_match_canonical_sources():
    for package in ['azure/app-service/python-fastapi','aws/lambda/python-http']:
        for name in ['runtime_policy.py','retail_pricing.py','estimate.py','requirements.txt']:
            assert (ROOT/'components/lifecycle-finops'/name).read_bytes() == (ROOT/'templates'/package/'operations'/name).read_bytes()


def test_lambda_health_reports_exact_revision(monkeypatch):
    file=ROOT/'templates/aws/lambda/python-http/app/handler.py'
    spec=importlib.util.spec_from_file_location('lambda_app',file)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setenv('SOURCE_REVISION','a'*40)
    response=module.handler({},None)
    assert response['statusCode']==200
    assert json.loads(response['body'])=={'status':'ok','revision':'a'*40}
