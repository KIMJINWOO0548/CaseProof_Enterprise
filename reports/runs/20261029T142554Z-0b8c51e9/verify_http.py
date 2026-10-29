from pathlib import Path
import json, os, subprocess, sys, time, urllib.request
root=Path.cwd()
out=Path(__file__).resolve().parent
env={**os.environ, 'CASEPROOF_DEMO_MODE':'1', 'CASEPROOF_DATABASE_URL':'sqlite://'}
with (out/'http_wrapped_server.txt').open('w',encoding='utf-8') as log:
    proc=subprocess.Popen([sys.executable,'-m','scripts.windows_checks','uvicorn','service.app:app','--host','127.0.0.1','--port','18768','--backlog','1','--workers','1'],env=env,stdout=log,stderr=log)
    try:
        for attempt in range(50):
            if proc.poll() is not None:raise RuntimeError('Local HTTP server exited before ready')
            try:
                with urllib.request.urlopen('http://127.0.0.1:18768/api/health',timeout=1) as res:
                    health=json.load(res)
                break
            except OSError:time.sleep(.1)
        else:raise RuntimeError('Local HTTP startup timed out')
        with urllib.request.urlopen('http://127.0.0.1:18768/openapi.json',timeout=2) as res:
            schema=json.load(res)
        with urllib.request.urlopen('http://127.0.0.1:18768/',timeout=2) as res:
            html=res.read().decode('utf-8')
        assert health['real_insurance_decisions'] is False and 'CaseProof' in html
        assert 'reason' in schema['components']['schemas']['Decision']['required']
        for operation in schema['paths'].values():
            if 'post' in operation:
                key=next(p for p in operation['post']['parameters'] if p['name']=='Idempotency-Key')
                assert key['required'] and key['schema']['minLength']==12 and key['schema']['maxLength']==128
        (out/'openapi.json').write_text(json.dumps(schema,ensure_ascii=False,indent=2),encoding='utf-8')
        print('HTTP health, HTML and OpenAPI: PASS (127.0.0.1, one worker, in-memory SQLite)')
    finally:
        proc.terminate()
        try:proc.wait(timeout=5)
        except subprocess.TimeoutExpired:proc.kill();proc.wait()

