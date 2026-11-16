from pathlib import Path
import importlib.util
import json
from fnmatch import fnmatch

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


AI_KIT = [entry['path'].removeprefix('components/ai-kit/')
          for entry in json.loads((ROOT/'components/manifests/ai-kit.json').read_text())['files']
          if not entry['path'].endswith('/README.md')]


def test_ai_kit_copies_match_canonical_sources():
    for package in ['azure/app-service/python-fastapi-split']:
        for name in AI_KIT:
            assert (ROOT/'components/ai-kit'/name).read_bytes() == (ROOT/'templates'/package/name).read_bytes(), name


def test_ai_kit_protected_paths_agree_everywhere():
    kit = ROOT/'components/ai-kit'
    listed = {line.strip() for line in (kit/'.eanextgen.d/rules/protected-paths.txt').read_text().splitlines()
              if line.strip() and not line.startswith('#')}
    denied = {rule[rule.index('(')+1:-1].replace('/**', '/*')
              for rule in json.loads((kit/'.claude/settings.json').read_text())['permissions']['deny']
              if rule.startswith(('Edit(', 'Write('))}
    uncovered = {d for d in denied - listed if not any(fnmatch(d, pattern) for pattern in listed)}
    assert listed <= denied and not uncovered, 'protected-paths.txt and the Claude deny list must name the same paths'
    agents = (kit/'AGENTS.md').read_text()
    assert '.eanextgen.d/rules/protected-paths.txt' in agents
    for path in listed - {'tests/test_split_delivery.py'}:
        assert f'`{path.rstrip("*").rstrip("/") if path.endswith("/*") else path}' in agents, path


def test_ai_kit_checker_is_clean_on_the_template_and_catches_a_layer_violation(tmp_path):
    import shutil
    import subprocess
    import sys
    copy = tmp_path/'service'
    shutil.copytree(ROOT/'templates/azure/app-service/python-fastapi-split', copy,
                    ignore=shutil.ignore_patterns('__pycache__', '.pytest_cache'))
    run = lambda: subprocess.run([sys.executable, 'tools/check_architecture.py', '--json'], cwd=copy,
                                 capture_output=True, text=True)
    clean = run()
    assert clean.returncode == 0 and json.loads(clean.stdout)['violations'] == []
    with (copy/'app/service/domain/greeting.py').open('a') as f:
        f.write('\nfrom service.infrastructure.clock import SystemClock  # deliberate\n')
    dirty = run()
    [violation] = json.loads(dirty.stdout)['violations']
    assert dirty.returncode == 1 and violation['rule'] == 'ARCH-001' and violation['imports'] == 'service.infrastructure.clock'


def test_ai_kit_hooks_call_the_guardrail():
    hooks = json.loads((ROOT/'components/ai-kit/.claude/settings.json').read_text())['hooks']
    assert 'guardrail.py post-edit' in hooks['PostToolUse'][0]['hooks'][0]['command']
    assert 'guardrail.py stop' in hooks['Stop'][0]['hooks'][0]['command']
