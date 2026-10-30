# Review workspace update

The interface serves analysts, domain reviewers, release approvers and auditors
working with the existing synthetic `/api`. The goal is a clear, reproducible
review flow with readable evidence, accessible controls and honest status.

Keep the existing FastAPI-served HTML and request contract. A new SPA would add
build tooling without enabling a missing workflow; a marketing landing page
would hide the actual product. This update improves the working application.

Use the actual **Tabler 1.7.3** core stylesheet (MIT), vendored unmodified with
its notices and npm integrity record. Standard Tabler table, card, button, form,
badge, step and modal classes define the components. Application CSS covers only
layout, narrow-screen behavior and workflow-specific content. Small status text uses measured contrast corrections; the upstream file remains intact. No plugin scripts,
charts, fonts, CDN requests or new frontend build environment are needed.

A full-width request table supplies search and status filters. Selecting a row
loads the review card and a separate evidence card alongside it on wide screens;
these stack on smaller screens. Native browser dialogs use Tabler modal markup
while retaining focus/Escape behavior. Evidence separates record, audit and seal
checks and retains the original JSON disclosure. The login uses a simple Tabler
authentication card instead of a marketing introduction.

Only backend-authorized actions are offered. The UI's readiness hints do not
replace server checks. No automatic actor, fabricated approvals, seeded passing
history or new token endpoint is introduced. Tokens stay in memory. Pending
requests keep their exact key/body/revision in memory, scoped to authenticated
tenant and actor; role switching does not replay another actor's request. A
recovery action explicitly retries the original request after an uncertain
response. Reloading the page clears in-memory recovery and is a known limit.

Implementation sequence: independent request-helper failure checks; native forms
and layout; selection/session guards and recovery; real browser three-person
workflow plus narrow/keyboard/error checks; whole regression and source/build
checks; focused commit and push. This is baseline UI work, not completion of G4's
future linked-change, full-suite or user-study gates.
