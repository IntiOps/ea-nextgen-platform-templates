"""Offline ZAP JSON assessment. Does not scan or authorize a target."""
from urllib.parse import urlsplit


def origin(url):
    value = urlsplit(url)
    if value.scheme not in {'http','https'} or not value.hostname or value.username or value.password:
        raise ValueError('invalid target origin')
    if value.path not in {'','/'} or value.query or value.fragment:
        raise ValueError('use an explicit origin without a path/query')
    return value.scheme, value.hostname.lower(), value.port or (443 if value.scheme == 'https' else 80)


def assess(report, *, expected_origin, max_allowed_risk=1):
    if type(max_allowed_risk) is not int or max_allowed_risk not in range(4):
        raise ValueError('invalid risk threshold')
    target = origin(expected_origin)
    sites = report.get('site')
    if not isinstance(sites,list) or not sites:
        return {'status':'no_evidence','origin_verified':False}
    counts = {str(i):0 for i in range(4)}
    for site in sites:
        if origin(site.get('@name','')) != target:
            raise ValueError('unexpected report target')
        alerts=site.get('alerts')
        if not isinstance(alerts,list):
            raise ValueError('missing alert collection')
        for alert in alerts:
            risk=str(alert.get('riskcode',''))
            if risk not in counts: raise ValueError('unknown ZAP risk level')
            counts[risk]+=1
    return {'status':'failed' if any(counts[str(i)] for i in range(max_allowed_risk+1,4)) else 'passed',
            'risk_counts':counts,'origin_verified':False,'deployment_authorized':False,
            'coverage_verified':False}
