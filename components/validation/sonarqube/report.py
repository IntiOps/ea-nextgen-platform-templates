"""Offline Sonar report assessment, NOT a live/provider-authenticated connector."""

def assess(task, gate, analysis, *, expected_project, expected_commit, expected_analysis_id):
    # Inputs are separately captured native responses. The caller must fetch the
    # gate by analysisId, never project 'latest'; platform provenance is still pending.
    current = task.get('task', {})
    if current.get('status') != 'SUCCESS':
        return {'status': 'tool_error', 'reason': 'compute_task_not_successful', 'origin_verified': False}
    if (not expected_analysis_id or current.get('analysisId') != expected_analysis_id or
        current.get('componentKey') != expected_project or analysis.get('key') != expected_analysis_id or
        analysis.get('revision') != expected_commit):
        return {'status': 'tool_error', 'reason': 'analysis_context_mismatch', 'origin_verified': False}
    state = gate.get('projectStatus', {}).get('status')
    status = {'OK': 'passed', 'ERROR': 'failed', 'NONE': 'no_evidence'}.get(state, 'tool_error')
    return {'status': status, 'analysis_id': expected_analysis_id, 'origin_verified': False,
            'reason': 'captured_report_only', 'deployment_authorized': False}
