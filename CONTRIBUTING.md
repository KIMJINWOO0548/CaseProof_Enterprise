# Contributing to CaseProof

CaseProof is a development prototype for synthetic insurance-rule checks and human review. The v5.3 package prepares the repository and implementation contracts; it does not imply that the future design is implemented. Read the root README and `prebuild/` acceptance criteria before changing behavior.

## Development setup

Use an isolated Python 3.11, 3.12, or 3.13 environment. From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --require-hashes -r requirements-dev.lock
python -m pip install --no-deps --no-build-isolation -e .
python -m pip check
```

On Windows, create the environment with `py -3.12 -m venv .venv` and activate it with `.\.venv\Scripts\Activate.ps1`. The remaining `python` commands are the same. If activation is restricted, use `.\.venv\Scripts\python.exe` directly.

`requirements.txt` defines supported runtime ranges. The hash-locked files record a selected resolution, including transitive dependencies. Installing `.[dev]` is available for dependency compatibility experiments but can select newer versions; record that distinction in the results. Use a dedicated environment because the inherited top-level module names `service`, `reference`, and the data directory `datasets` are not a stable public SDK.

## Checks before a pull request

```bash
python -m scripts.check_package
python -m pytest -q
python -m scripts.smoke
python -m scripts.check_ui_syntax
python -m build --no-isolation
python -m scripts.check_distribution dist
```

The UI syntax check requires Node.js 22. It does not exercise a browser. Follow the README's separate browser instructions for a UI change. Run builds with an empty `dist/` output directory; preserve any release artifacts you need before replacing them.

For each meaningful behavior change, demonstrate the failure with an isolated test, implement the change, and run relevant regressions. Tests must use temporary databases and synthetic fixtures. Do not connect tests to an existing operational database. A change to a fixture's expected value needs a documented rule/source rationale, rather than merely matching the implementation.

## Scope and evidence

- Keep each pull request focused on one observable behavior or contract.
- Reference the applicable prebuild gate, describe before and after behavior, and explain data or API compatibility effects.
- Include actual commands, Python/dependency versions, exit codes, and limitations. Mark unexecuted checks `NOT_RUN`; record failed checks as failures.
- Review generated logs, screenshots, and fixtures before committing them. Never commit emitted demo tokens, credentials, customer records, local database files, or environment files.
- Keep historical test results dated and explicitly historical. Do not copy them into a new run's evidence.
- A successful numeric check is not insurance advice, payment authorization, regulatory certification, or proof of LLM accuracy.

Use `SECURITY.md` for vulnerabilities. Ordinary bugs should include a minimal synthetic reproduction, the commit or package version, operating system, Python version, and sanitized output.

## Dependencies and CI

Explain any new runtime dependency and its maintenance and license implications. When changing dependency ranges, regenerate and review both lock files, then run the Python matrix. Hashes identify downloaded distributions; they do not establish that a dependency is safe. See `docs/OSS_RELEASE_CHECKLIST.md` for CI permissions, scanning coverage, and release requirements.

CI uses read-only repository permissions and no repository secrets. Do not add `pull_request_target`, untrusted shell interpolation, automatic publication, or writable tokens as a shortcut to make a check pass. Pin third-party actions to reviewed commit IDs and update their release comments together. Dependency audit exceptions require a documented advisory, scope, rationale, owner, and expiry; there are no default exceptions.

## Contribution rights

Submit only work you have the right to contribute. Original contributions intentionally submitted for this project are offered under Apache-2.0, as described in `LICENSE`, unless expressly stated otherwise and accepted by the project owner. Keep existing notices, disclose copied or adapted material and its source/license, and identify material AI assistance in the change description. No contributor license agreement or signed-off-by requirement is configured by this package.

The original archive did not establish all authorship and redistribution rights. The repository owner must complete the provenance review in `THIRD_PARTY_NOTICES.md` before public distribution. Do not treat a generated license file as proof of ownership.
