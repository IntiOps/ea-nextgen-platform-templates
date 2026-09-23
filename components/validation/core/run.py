"""Fixed local test suites; no shell commands or paths supplied by a manifest."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
from evidence import bounded_read, make_evidence, evaluate

ROOT = Path(__file__).resolve().parents[3]
SUITES = {
    'catalog': ['tests/test_architecture_catalog.py'],
    'application': ['templates/azure/app-service/python-fastapi/tests/test_demo.py', 'tests/test_components.py'],
    'policy': ['tests/test_runtime_policy.py', 'tests/test_retail_pricing.py', 'tests/test_quality_validation.py'],
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    parser.add_argument('--commit', required=True)
    parser.add_argument('--repository', required=True)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--attempt', default='1')
    args = parser.parse_args()
    context = {'repository': args.repository, 'commit': args.commit, 'run_id': args.run_id,
               'attempt': args.attempt, 'environment': 'ci-local'}
    profile = json.loads((ROOT/'components/validation/profiles/local-source.json').read_text())
    from evidence import validate_context, validate_profile
    validate_context(context); validate_profile(profile)
    actual = subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    if subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip():
        parser.error('source checkout must be clean before collecting evidence')
    if actual != args.commit:
        parser.error('checked-out commit differs from context')
    output = Path(args.output).resolve()
    if output.is_relative_to(ROOT):
        parser.error('evidence output must be outside the source checkout')
    # Fresh directory prevents stale reports from previous attempts becoming evidence.
    output.mkdir(parents=True, exist_ok=False)
    results=[]
    for name, paths in SUITES.items():
        report = output/(name+'.xml')
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
        try:
            result = subprocess.run([sys.executable,'-m','pytest','-p','no:cacheprovider',*paths,'-q',f'--junitxml={report}'],
                                    cwd=ROOT,env=env,timeout=300,check=False)
            code = result.returncode
        except subprocess.TimeoutExpired:
            code = 124
        try:
            payload = bounded_read(report) if report.is_file() else None
        except (OSError, ValueError):
            payload = None; code = 2
        results.append(make_evidence(profile,context,name,payload,code))
    # Freshness is evaluated after all suites complete.
    gate = evaluate(profile,context,results,datetime.now(timezone.utc))
    (output/'evidence.json').write_text(json.dumps({'context':context,'evidence':results,'gate':gate},indent=2)+'\n')
    print(json.dumps(gate,indent=2))
    return 0 if gate['ci_gate_passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
