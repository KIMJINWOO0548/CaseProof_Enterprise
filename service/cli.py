"""Local seed CLI. Credentials are printed once and not bundled with releases."""
import argparse, os
from .db import make_engine,create_tables,session_factory
from .seed import seed_demo

def main():
    p=argparse.ArgumentParser(description='CaseProof synthetic demo initializer')
    p.add_argument('action',choices=['init-demo'])
    p.add_argument('--database',default=os.getenv('CASEPROOF_DATABASE_URL') or 'sqlite:///./caseproof_demo.sqlite3')
    args=p.parse_args()
    if os.getenv('CASEPROOF_DEMO_MODE')!='1':
        p.error('Set CASEPROOF_DEMO_MODE=1 for the local synthetic demo')
    if not args.database.startswith('sqlite'):
        p.error('This CLI only initializes local SQLite demo data')
    engine=make_engine(args.database)
    try:
        create_tables(engine)
        with session_factory(engine)() as s:
            tokens=seed_demo(s)
            s.commit()
    finally:
        engine.dispose()
    print('SYNTHETIC LOCAL DEMO only. NOT for real insurance data.\n')
    for key,value in tokens.items():
        print(f'{key:<22} {value}')
    if not tokens:
        print('Accounts already initialized; credentials are not repeated. Choose a new SQLite path for another demo.')
    print('\nStore credentials privately. Never commit local token output to Git.')
if __name__=='__main__':
    main()
