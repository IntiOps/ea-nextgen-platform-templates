"""Local CI evidence contract. Never authorizes a platform/cloud operation."""
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree

MAX_REPORT_BYTES = 2_000_000
STATUSES = {'passed', 'failed', 'tool_error', 'no_evidence', 'not_applicable'}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def bounded_read(path):
    with Path(path).open('rb') as stream:
        data = stream.read(MAX_REPORT_BYTES + 1)
    if len(data) > MAX_REPORT_BYTES:
        raise ValueError('report exceeds size limit')
    return data


def junit(data):
    # UTF-8 only, no DTD/entity declarations; never resolve external resources.
    if len(data) > MAX_REPORT_BYTES:
        raise ValueError('report exceeds size limit')
    text = data.decode('utf-8')
    if '\x00' in text or '<!DOCTYPE' in text.upper() or '<!ENTITY' in text.upper():
        raise ValueError('DTD/entities/alternate encodings are not accepted')
    root = ElementTree.fromstring(text)
    if root.tag not in {'testsuite', 'testsuites'}:
        raise ValueError('unsupported JUnit root')
    cases = list(root.iter('testcase'))
    counts = {'tests': len(cases), 'failures': 0, 'errors': 0, 'skipped': 0}
    for case in cases:
        for key, tag in [('failures', 'failure'), ('errors', 'error'), ('skipped', 'skipped')]:
            counts[key] += int(case.find(tag) is not None)
    # Suite-level setup failures must not disappear when there are no testcase nodes.
    suite_failure = any(int(s.attrib.get('failures', '0')) > 0 for s in root.iter('testsuite'))
    suite_error = any(int(s.attrib.get('errors', '0')) > 0 for s in root.iter('testsuite'))
    state = ('tool_error' if counts['errors'] or suite_error else
             'failed' if counts['failures'] or suite_failure else
             'no_evidence' if not cases or counts['skipped'] == len(cases) else 'passed')
    # Never include case names, stdout, exception text or properties in normalized output.
    return state, counts


def validate_context(context):
    required = {'repository', 'commit', 'run_id', 'attempt', 'environment'}
    if set(context) != required:
        raise ValueError('unexpected or missing context fields')
    if not all(isinstance(context[k], str) and 0 < len(context[k]) <= 512 for k in required):
        raise ValueError('context values must be bounded nonempty strings')
    if not re.fullmatch(r'[a-f0-9]{40}', context['commit']):
        raise ValueError('a full commit SHA is required')
    if not context['attempt'].isdigit() or int(context['attempt']) < 1:
        raise ValueError('invalid run attempt')


def validate_profile(profile):
    if set(profile) != {'schema_version', 'id', 'phase', 'max_age_seconds', 'controls'} or profile['schema_version'] != '1.0':
        raise ValueError('unsupported profile contract')
    if profile['phase'] not in {'build', 'pre_promotion', 'post_deploy'}:
        raise ValueError('unknown phase')
    if type(profile['max_age_seconds']) is not int or not 1 <= profile['max_age_seconds'] <= 86400:
        raise ValueError('invalid evidence validity')
    controls = profile['controls']
    if not isinstance(controls, list) or not controls or len(controls) > 100:
        raise ValueError('controls must be explicit and bounded')
    if not any(c.get('required') is True for c in controls):
        raise ValueError('profile must require at least one control')
    ids = set()
    for control in controls:
        if set(control) != {'id', 'category', 'required', 'min_executed'} or type(control['required']) is not bool:
            raise ValueError('invalid control contract')
        if not re.fullmatch(r'[a-z][a-z0-9-]{0,63}', control['id']) or control['id'] in ids:
            raise ValueError('invalid/duplicate control')
        if type(control['min_executed']) is not int or control['min_executed'] < 0:
            raise ValueError('invalid minimum tests')
        ids.add(control['id'])


def make_evidence(profile, context, control_id, report, exit_code, now=None):
    validate_profile(profile); validate_context(context)
    if control_id not in {c['id'] for c in profile['controls']}:
        raise ValueError('control not in profile')
    state, metrics, report_digest = 'tool_error', {}, None
    if report is not None:
        report_digest = hashlib.sha256(report).hexdigest()
        try:
            state, metrics = junit(report)
        except (ValueError, UnicodeError, ElementTree.ParseError):
            pass
    if exit_code != 0:
        state = 'failed' if exit_code == 1 else 'tool_error'
    return {'schema_version': '1.0', 'control_id': control_id, 'context': dict(context),
            'profile_digest': digest(profile), 'status': state, 'metrics': metrics,
            'report_sha256': report_digest, 'recorded_at': (now or datetime.now(timezone.utc)).isoformat(),
            'source': 'local-ci-runner', 'origin_verified_by_platform': False}


def evaluate(profile, context, evidence, now=None):
    validate_profile(profile); validate_context(context)
    now = now or datetime.now(timezone.utc)
    expected = digest(profile)
    grouped = {}
    allowed = {c['id'] for c in profile['controls']}
    for row in evidence:
        if row.get('control_id') not in allowed:
            raise ValueError('unknown control evidence')
        grouped.setdefault(row['control_id'], []).append(row)
    outcomes = []
    for control in profile['controls']:
        rows = grouped.get(control['id'], [])
        reason = 'missing_evidence'
        if len(rows) > 1:
            reason = 'ambiguous_evidence'
        elif len(rows) == 1:
            row = rows[0]
            reason = 'context_mismatch'
            if row.get('context') == context and row.get('profile_digest') == expected:
                try:
                    at = datetime.fromisoformat(row['recorded_at'])
                    age = (now-at).total_seconds()
                    fresh = 0 <= age <= profile['max_age_seconds']
                except (ValueError, TypeError, KeyError):
                    fresh = False
                reason = 'stale_or_invalid_time'
                if fresh:
                    reason = row.get('status', 'tool_error')
                    if reason not in STATUSES: reason = 'tool_error'
                    if reason == 'passed':
                        metrics = row.get('metrics', {})
                        tests, skipped = metrics.get('tests', 0), metrics.get('skipped', 0)
                        if type(tests) is not int or type(skipped) is not int or tests < skipped or skipped < 0:
                            reason = 'invalid_metrics'
                        elif tests-skipped < control['min_executed']:
                            reason = 'insufficient_executed_tests'
        outcomes.append({'control_id': control['id'], 'required': control['required'], 'reason': reason})
    return {'profile_id': profile['id'], 'profile_digest': expected,
            'ci_gate_passed': all(o['reason'] == 'passed' for o in outcomes if o['required']),
            'deployment_authorized': False, 'outcomes': outcomes}
