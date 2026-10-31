# Review workspace visual design

2026-11-01. The v1 workspace now uses an ink masthead, iris selection/actions,
peach brand accent and locally bundled SUIT variable type. This gives the
review workbench a stronger identity while keeping the actual change and its
evidence central. There are no simulated metrics, chat features or live-status
claims. The original `/api` interface and stored execution/evidence formats
are unaffected.

## Visual and interaction decisions

| Element | Applied choice and reason | Files |
| --- | --- | --- |
| Identity | Ink `#24223f`, iris `#5945d8`, peach `#ffbd9d`, canvas `#f3f3f8`, text `#28283c`, evidence green `#146c52`. A compact dark title band supplies the focal contrast. | `service/static/v1.html`, `v1.css` |
| Typography | Unmodified SUIT Variable, 100–900, served locally with `font-display: swap`. Larger selected-change title and quieter UUID distinguish content from references. | `v1.css`, `vendor/suit/`, `service/workspace.py` |
| Inspection | Queue and inspector remain parallel from 992px; evidence becomes a third panel from 1280px. Narrow screens preserve the queue/detail/evidence order. | `v1.css` |
| Current stage | Four actual workflow states are labeled. Only the returned current state has `aria-current="step"`; a rejected request marks no active stage. Earlier steps are never fabricated as completed. | `v1.js`, `scripts/v1_ui_probe.js` |
| Evidence | Only actual `VALID` / `ELIGIBLE` values receive success color. `NOT_CONFIGURED` remains neutral, and evidence is loaded explicitly. | `v1.js`, `v1.css` |
| Feedback | Native dialogs stay opaque; linked error summaries, field focus, 44px mobile controls and reduced-motion rules are retained. Motion is limited to interaction feedback. | `v1.html`, `v1.css`, `v1.js` |

## Primary references and reuse boundaries

| Source | Observed benefit / applied area | Excluded / license scope |
| --- | --- | --- |
| [Linear](https://linear.app/) | Its current product context keeps an issue alongside review/activity/properties. Read-only computed styles established a dark canvas and strong type hierarchy. Adapted the contrast and object/context hierarchy into our header and inspector. | No full issue system or marketing hero. [Terms §1.3](https://linear.app/terms) reserve materials/software; proprietary UI, no SPDX asserted. No code/assets copied. |
| [Raycast](https://www.raycast.com/) | Public AI/tool examples separate actions from activity; computed styles established strong dark/light contrast and headline hierarchy. Applied direct action emphasis and a restrained focal surface. | No chat metaphor, keyboard-shortcut claims or product renders. [Terms §VI](https://www.raycast.com/terms-of-service) reserve software/content/trademarks; extension licenses do not license its UI. No code/assets copied. |
| [Langfuse Sessions](https://langfuse.com/docs/observability/features/sessions) | Related records remain in context. Existing list/detail/evidence separation is retained. | No unsupported scores/cost widgets/sharing. Core MIT excludes enterprise directories; [pinned licenses and earlier LangSmith/Dify review](AI_UI_REFERENCES.md) retain their distinct scopes. |
| [SUIT](https://github.com/sun-typeface/SUIT/tree/55118d981336d8fce005eb62888c12c0568ef7b0) | Korean/Latin UI type; actual font binary and license are bundled. | OFL-1.1, Reserved Font Name SUIT; original bytes and full notice preserved. This is the only new third-party asset. |

Linear/Raycast research used official text, accessible product structure and
computed styles. Remote screenshot APIs failed, so their screenshots or
animation details were **not visually inspected** in this pass. Earlier
Langfuse image inspection is recorded separately. Local CaseProof screenshots
are actual browser captures of a disposable synthetic profile, not upstream
assets or mockups.

UI/UX Pro Max was read and `--design-system` searched twice. Its landing-page
and Brutalism recommendations did not fit this approval workspace; those
layouts were rejected rather than persisted as a verified design system.
Readable type, contrast, selected-state distinction and reduced motion were
used as general guidance. Frontend Design supplied the subject-specific
palette/type/layout review. Uncodixfy's final review removed redundant English
labels and preserved functional hierarchy; its broad style bans do not
override the user's explicit request for a more vivid interface.

GitHub MCP fetched the pinned SUIT license; downloaded Git blob identities and
SHA-256 were checked. Context7 retrieved official FastAPI FileResponse
documentation for explicit `media_type`; a regression reproduces an OS MIME
guess of `application/octet-stream` and requires `font/woff2` without changing
global MIME settings. Existing Tabler bytes remain untouched.

## Verification scope

The new stage assertion first failed against the old renderer. The native
Chrome 156 flow then passed creation, full-suite evaluation, committed-response
loss/replay, rejection, linked correction, separate approvals and evidence
lookup. Its existing error-focus probe checks invalid-reason POST0, linked
field focus, reset and Escape at 1440/390px. RequestClient source is unchanged.

The MIME regression failed before the explicit route and passed afterward;
affected Python checks reported 4 PASS and 1 optional Python-browser SKIP. The
separate MCP browser execution is an actual run, not that skipped Python test.
Node replay/uncertain-denial checks and UI syntax checks passed. Full CI and
archive/installed checks are recorded with their exact source commit in
[validation](VALIDATION.md).

The final local suite included the new font regression: **913 PASS, 458 optional
SKIP, 22 subtests PASS**, with 3 warnings. This environment has NumPy but no active
PostgreSQL server or Python Playwright; CI exercises those database/statistics
checks separately. Windows socketpair initialization was retried 57 times;
application requests and assertions were not retried. Baseline smoke was 12/12.
The measured normal text pairs are 5.53–15.27:1; input border and focus outline
against white are 3.22:1 and 3.25:1. These are selected measurements, not a complete
WCAG certification. [Actual flow, dimensions and measurements](evidence/g1-g6/ui-visual-refresh.json).

Implementation `b0c3d64` passed all 9 CI jobs: each ordinary OS/Python matrix
reported 912 PASS, actual PostgreSQL 460 PASS and paired statistics 34 PASS.
[CI evidence](evidence/g1-g6/ci-b0c3d64.json) and the
[exact source/wheel/outside-checkout checks](evidence/g1-g6/installed-b0c3d64.json)
are preserved. A subsequent style-only refinement uses the muted text token
for non-current stage labels, measured at 5.53:1, and removes an unused color
rule. The desktop/mobile captures and computed-style check were repeated.

This is a synthetic review prototype. Independent usability observation,
screen-reader speech, real insurance decisions, external anchors/models and
production deployment are not established by visual or automated checks.
