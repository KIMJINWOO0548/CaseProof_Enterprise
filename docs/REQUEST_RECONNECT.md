# Request recovery in the v1 workspace

The browser creates a key before the first write and saves one pending request
per tenant and actor in browser local storage. The record contains the method's
relative path, serialized synthetic body, expected revision, key, format
version and server-provided request context. A same-origin Web Lock protects
the pending slot across tabs. The bearer token stays in memory. Keep synthetic
titles and reasons on this demo, since pending text remains visible to software
with access to the browser profile.

Reconnect through the same browser profile and origin and sign in again.
**원래 요청 복구** sends the saved path, body, revision and key. The server
checks the authenticated actor and SQLite workspace context before accepting
the request. A known commit produces its original response. A request that
never committed may proceed subject to today's role, state, revision and gates.
The same committed key with different normalized input returns 409. The
workspace then reads the selected change's current detail independently,
including its integrity status. An older result does not populate that view.

The authenticated workspace catalog adds `data.request_context`. The v1 write
routes accept `X-CaseProof-Request-Context` as an optional precondition.
The supported file-backed SQLite demo validates its original resolved file
identity and the tenant and actor on each checked write. A same-file server
restart retains the context. The verified restore command publishes a new
file, whose context differs. A pending request for the former database stays
blocked even when the old backup lacks the key. Direct API clients retain the
existing unguarded header contract. Clients carrying intents across restarts
should preserve and send the original context. The current authorized
`GET /api/v1/mutations/{key}` remains available for manual verification of
committed results.

A structured 4xx on the first attempt clears the failed intent, except for a
workspace-context mismatch. A 5xx, malformed response, dropped response, or
later denial leaves the saved intent unresolved. Newly authenticated roles drive
the UI after reconnect. The server reads current roles independently of the
saved request. Restored actors remain quarantined until explicit review with
rotated credentials. An older backup can contain verified historical approval
and still deny the old actor. Recovery never supplies approval based on a
cached receipt.

Recovery requires a browser with working local storage and Web Locks and a
supported local file identity. Closing a tab or restarting the demo preserves
the saved intent. Clearing browser data or using a different origin/profile
loses browser-side recovery. If the original workspace is unavailable, the
pending request remains blocked for reconciliation. Privileged in-place
replacement of database bytes, cross-device recovery and production restore
are outside this demo's verification.
