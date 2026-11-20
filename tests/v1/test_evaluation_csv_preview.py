import csv
import io
import json

from sqlalchemy import func, select

from service import models_v1 as m
from service.evaluation.csv_preview import preview_cases
from tests.v1.test_workspace import headers, mutate, workspace


def _csv(preset):
    buffer = io.StringIO(newline='')
    writer = csv.writer(buffer)
    writer.writerow(('case_id', 'claim_days', 'case_context'))
    for case in preset['case_inputs']:
        writer.writerow((case['case_id'], case['claim_days'], json.dumps(case['case_context'], indent=2)))
    return buffer.getvalue().encode('utf-8')


def _preview(client, identity, content, actor='analyst', revision=1, content_type='text/csv'):
    return client.post(
        f'/api/v1/changes/{identity}/evaluation-runs/preview-csv', content=content,
        headers=headers(actor) | {'Content-Type': content_type, 'X-Expected-Revision': str(revision)},
    )


def test_csv_preview_uses_pinned_cases_and_does_not_write(workspace):
    client, factory, _ = workspace
    preset = client.get('/api/v1/workspace', headers=headers()).json()['data']['presets'][0]
    change = mutate(client, '', preset['create_body'])
    identity = change['change_id']

    def counts():
        with factory() as db:
            return tuple(db.scalar(select(func.count()).select_from(table))
                         for table in (m.EvaluationRun, m.AuditEvent, m.IdempotencyRecord))

    before = counts()
    response = _preview(client, identity, b'\xef\xbb\xbf' + _csv(preset))
    assert response.status_code == 200, response.text
    preview = response.json()['data']
    assert preview['ready'] is True
    assert preview['revision'] == 1 and preview['errors'] == []
    assert counts() == before
    assert preview['evaluation']['suite_version_id'] == change['suite_version_id']

    direct = {'suite_version_id': change['suite_version_id'], 'case_inputs': preset['case_inputs']}
    expected = mutate(client, f'/{identity}/evaluation-runs', direct, 1)['run']
    actual = mutate(client, f'/{identity}/evaluation-runs', preview['evaluation'], 2)['run']
    assert expected['run_input_sha256'] == actual['run_input_sha256']
    assert expected['case_results'] == actual['case_results']


def test_csv_preview_reports_physical_lines_and_keeps_tenant_and_size_boundaries(workspace):
    client, _, _ = workspace
    preset = client.get('/api/v1/workspace', headers=headers()).json()['data']['presets'][0]
    identity = mutate(client, '', preset['create_body'])['change_id']
    file = _csv(preset)
    assert _preview(client, identity, file, actor='reviewer').status_code == 403
    assert _preview(client, identity, file, actor='other').status_code == 404
    assert _preview(client, identity, file, revision=2).status_code == 409
    assert _preview(client, identity, file, content_type='text/plain').status_code == 415
    assert _preview(client, identity, b'X' * (256 * 1024 + 1)).status_code == 413
    assert _preview(client, identity, b'\xff').json()['data']['errors'][0]['code'] == 'INVALID_UTF8'

    first = preset['case_inputs'][0]['case_id']
    malformed = f'case_id,claim_days,case_context\r\n{first},3.5,"{{\r\n}}"\r\n{first},3,{{}}\r\n'
    response = _preview(client, identity, malformed.encode())
    assert response.status_code == 200, response.text
    data = response.json()['data']
    assert data['ready'] is False and data['evaluation'] is None
    assert {'row': 2, 'column': 'claim_days', 'code': 'INVALID_INTEGER'} in data['errors']
    assert {'row': 4, 'column': 'case_id', 'code': 'DUPLICATE_CASE_ID'} in data['errors']
    missing = _preview(client, identity, b'case_id,claim_days,case_context\r\n').json()['data']
    assert {'row': None, 'column': 'case_id', 'code': 'MISSING_CASE_ID', 'case_id': first} in missing['errors']


def test_fifty_cases_are_sorted_and_invalid_context_does_not_reveal_content():
    required = {f'case-{index:02}' for index in range(50)}
    suite = '12345678-1234-4321-8abc-123456789abc'
    header = 'case_id,claim_days,case_context\n'
    rows = [f'{case_id},3,{{}}\n' for case_id in sorted(required, reverse=True)]
    good = preview_cases((header + ''.join(rows)).encode(), required, suite, 1)
    assert good.ready and [case.case_id for case in good.evaluation.case_inputs] == sorted(required)
    rows[0] = 'case-49,3,"{""secret_fixture"":1,""secret_fixture"":2}"\n'
    invalid = preview_cases((header + ''.join(rows)).encode(), required, suite, 1)
    assert not invalid.ready and invalid.errors[0].code == 'INVALID_CONTEXT'
    assert 'secret_fixture' not in invalid.model_dump_json()


def test_preview_openapi_documents_read_only_csv_contract(workspace):
    client, _, _ = workspace
    route = client.get('/openapi.json').json()['paths']['/api/v1/changes/{change_id}/evaluation-runs/preview-csv']['post']
    assert 'text/csv' in route['requestBody']['content']
    assert '415' in route['responses'] and '413' in route['responses']
