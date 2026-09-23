from datetime import datetime, timedelta, timezone
import importlib.util
import json
from pathlib import Path
import sys
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'components/validation/core'))
from evidence import junit,make_evidence,evaluate,validate_profile
PROFILE=json.loads((ROOT/'components/validation/profiles/local-source.json').read_text())
CONTEXT={'repository':'example/repo','commit':'a'*40,'run_id':'42','attempt':'1','environment':'ci-local'}
PASS=b'<testsuite tests="1"><testcase name="private name"/></testsuite>'
NOW=datetime(2026,9,24,tzinfo=timezone.utc)


def rows():
    return [make_evidence(PROFILE,CONTEXT,c['id'],PASS,0,NOW) for c in PROFILE['controls']]


def load(path,name):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


@pytest.mark.parametrize('xml,expected',[
    (PASS,'passed'),(b'<testsuite/>','no_evidence'),
    (b'<testsuite><testcase><skipped/></testcase></testsuite>','no_evidence'),
    (b'<testsuite><testcase><failure/></testcase></testsuite>','failed'),
    (b'<testsuite errors="1"/>','tool_error')])
def test_junit_classification(xml,expected):
    assert junit(xml)[0]==expected


@pytest.mark.parametrize('xml',[b'<!DOCTYPE x [<!ENTITY a SYSTEM "file:///etc/passwd">]><testsuite/>',
                               b'<testsuite>\x00</testsuite>', b'<html/>', b'x'*2_000_001],
                         ids=['dtd','nul','unsupported-root','oversized'])
def test_reject_untrusted_xml(xml):
    with pytest.raises(ValueError):junit(xml)


def test_gate_context_age_profile_and_missing_fail_closed():
    assert evaluate(PROFILE,CONTEXT,rows(),NOW)['ci_gate_passed']
    assert not evaluate(PROFILE,CONTEXT,rows()[:1],NOW)['ci_gate_passed']
    for field,value in [('commit','b'*40),('environment','production'),('attempt','2'),('repository','other/repo')]:
        evidence=rows();evidence[0]['context'][field]=value
        assert not evaluate(PROFILE,CONTEXT,evidence,NOW)['ci_gate_passed']
    for field,value in [('profile_digest','wrong'),('recorded_at',(NOW-timedelta(hours=2)).isoformat()),
                        ('recorded_at',(NOW+timedelta(minutes=1)).isoformat()),('status','unknown')]:
        evidence=rows();evidence[0][field]=value
        assert not evaluate(PROFILE,CONTEXT,evidence,NOW)['ci_gate_passed']
    assert not evaluate(PROFILE,CONTEXT,rows()+rows(),NOW)['ci_gate_passed']


def test_exit_code_overrides_stale_success_and_no_sensitive_output():
    item=make_evidence(PROFILE,CONTEXT,'catalog',PASS,124,NOW)
    assert item['status']=='tool_error'
    assert 'private name' not in json.dumps(item)
    assert item['origin_verified_by_platform'] is False
    assert evaluate(PROFILE,CONTEXT,rows(),NOW)['deployment_authorized'] is False


def test_duplicate_controls_rejected():
    profile={**PROFILE,'controls':PROFILE['controls']*2}
    with pytest.raises(ValueError):validate_profile(profile)


def test_sonar_analysis_identity_and_unknown_gate():
    sonar=load('components/validation/sonarqube/report.py','sonar_report')
    kwargs={'expected_project':'project','expected_commit':'a'*40,'expected_analysis_id':'analysis'}
    task={'task':{'status':'SUCCESS','analysisId':'analysis','componentKey':'project'}}
    analysis={'key':'analysis','revision':'a'*40}
    assert sonar.assess(task,{'projectStatus':{'status':'OK'}},analysis,**kwargs)['status']=='passed'
    assert sonar.assess(task,{'projectStatus':{'status':'UNKNOWN'}},analysis,**kwargs)['status']=='tool_error'
    assert sonar.assess(task,{'projectStatus':{'status':'OK'}},{**analysis,'revision':'b'*40},**kwargs)['status']=='tool_error'


def test_zap_scope_and_risk_are_explicit():
    zap=load('components/validation/dast-zap/report.py','zap_report')
    report={'site':[{'@name':'https://sandbox.example','alerts':[{'riskcode':'3'}]}]}
    assert zap.assess(report,expected_origin='https://sandbox.example')['status']=='failed'
    with pytest.raises(ValueError):zap.assess(report,expected_origin='https://production.example')
    report['site'][0]['alerts'][0]['riskcode']='unexpected'
    with pytest.raises(ValueError):zap.assess(report,expected_origin='https://sandbox.example')


def test_quality_catalog_pins_and_adapters():
    tool=load('tools/validate_quality_catalog.py','quality_catalog')
    result=tool.validate()
    assert len(result['bindings'])==3
    assert result['adapters']['sonarqube']=='offline_report_only'
    assert result['adapters']['zap']=='offline_report_only'


@pytest.mark.parametrize('failure',['dirty','wrong_commit','existing_output'])
def test_runner_rejects_unreliable_source_and_reused_reports(tmp_path,monkeypatch,failure):
    runner=load('components/validation/core/run.py','quality_runner')
    root=tmp_path/'repo'
    profile=root/'components/validation/profiles/local-source.json'
    profile.parent.mkdir(parents=True);profile.write_text(json.dumps(PROFILE))
    monkeypatch.setattr(runner,'ROOT',root)
    def git(command,**kwargs):
        if command[1]=='rev-parse':return ('b'*40 if failure=='wrong_commit' else 'a'*40)+'\n'
        return ' M app.py\n' if failure=='dirty' else ''
    monkeypatch.setattr(runner.subprocess,'check_output',git)
    output=tmp_path/'reports'
    if failure=='existing_output': output.mkdir()
    monkeypatch.setattr(sys,'argv',['run.py','--output',str(output),'--commit','a'*40,'--repository','example/repo','--run-id','1'])
    with pytest.raises(FileExistsError if failure=='existing_output' else SystemExit):runner.main()
