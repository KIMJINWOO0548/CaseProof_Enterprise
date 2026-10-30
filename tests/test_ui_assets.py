"""The real page must use the pinned, locally served open-source UI asset."""
import hashlib
import json
from pathlib import Path

from fastapi.testclient import TestClient

from service.app import create_app


def test_page_serves_pinned_tabler_and_notices(tmp_path):
    app = create_app(f"sqlite:///{tmp_path / 'ui.sqlite3'}", demo_mode=True)
    vendor = Path(__file__).resolve().parents[1] / 'service/static/vendor/tabler-1.7.3'
    provenance = json.loads((vendor / 'PROVENANCE.json').read_text(encoding='utf-8'))
    try:
        with TestClient(app) as client:
            page = client.get('/')
            assert '/static/vendor/tabler-1.7.3/tabler.min.css' in page.text
            assert 'class="table table-vcenter' in page.text
            response = client.get('/static/vendor/tabler-1.7.3/tabler.min.css')
            assert response.status_code == 200
            assert response.headers['content-type'].startswith('text/css')
            assert 'Tabler v1.7.3' in response.text
            assert hashlib.sha256(response.content).hexdigest() == provenance['files']['tabler.min.css']
            for name in ('LICENSE.txt', 'BOOTSTRAP-LICENSE.txt'):
                assert 'Permission is hereby granted' in client.get('/static/vendor/tabler-1.7.3/' + name).text
            assert client.get('/static/../app.py').status_code == 404
    finally:
        app.state.db_engine.dispose()
