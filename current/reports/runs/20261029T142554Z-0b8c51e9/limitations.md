# Verification limits

- All databases in these tests were newly created, disposable synthetic SQLite databases. BEGIN IMMEDIATE reserves a writer only for mutation POST sessions. This is local serialization, not proof of PostgreSQL or multi-worker support.
- SQLite lock conflicts are explicit retryable409 responses; production load/throughput is unmeasured. No application transaction or assertion is retried by windows_checks; it only handles Windows socketpair initialization error10014.
- Each record captures a successful original response. Historical replay is authorized again, but intentionally precedes current integrity/state checks; current GET/evidence remains the source of latest state. Clients display that an already-processed request was replayed and then fetch current state.
- All current POST mutation APIs now require Idempotency-Key12–128, including create/submit/decisions. Old direct clients must add this header. The UI, smoke script and shared test helper were updated. Previous schemas have no automatic migration.
- The UI retry check executes the real inline request function in Node with controlled fetch outcomes. It is not a rendered browser or accessibility test. Browser automation ended because it could not confidently determine the current URL; GitHub also required user authentication. No alternate desktop-control method was used after that stop.
- Existing browser_e2e.py still has a fixed-path temporary DB deletion and was not executed. Its safe rewrite and actual browser end-to-end acceptance remain future work.
- PostgreSQL/RLS/migrations, external anchors, real models/insurance data, expert review and benchmark claims remain unverified or unimplemented. The existing Starlette/httpx deprecation warning remains.
- Existing history and failed logs were retained. Earlier 142-test milestone evidence was not rewritten into the new157-test result.
