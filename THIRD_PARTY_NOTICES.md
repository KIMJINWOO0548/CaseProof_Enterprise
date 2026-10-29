# Provenance and third-party materials

## Original and inherited materials

Apache-2.0 is the selected default for original project code, documentation, and synthetic fixtures whose rights holders authorize that release. The full unmodified license text is in `LICENSE`; its authoritative source is the [Apache Software Foundation](https://www.apache.org/licenses/LICENSE-2.0.txt). This selection does not grant rights that the repository owner does not hold.

The source provided for this handoff was a CaseProof Enterprise v5.2 prebuild archive containing v5.1 service/reference code and tests. It did not provide a complete original-author inventory, contributor agreements, or a file-by-file provenance register. No upstream repository identity, original copyright owner, or clean rights clearance is asserted here.

| Material | Provenance recorded by this package | Required before public distribution |
| --- | --- | --- |
| `service/`, `reference/`, inherited tests and scripts | Copied from the supplied prototype archive; organization or packaging may be changed | Confirm author/owner and permission to release; preserve any upstream notices |
| `datasets/*.json` | Described in the supplied archive as synthetic rules and fixtures | Confirm original generation and absence of confidential or copied policy text; document allowed reuse |
| Inherited design, audit, and research text | Supplied with the archive; historical claims remain historical | Confirm rights to original prose and quoted material; retain source attribution and result dates |
| New packaging, CI, community policy, and handoff additions | Prepared for the v5.3 handoff with AI assistance | Owner reviews and accepts the intended Apache-2.0 release and contributor attribution |
| External documents, logos, screenshots, reports, and binaries | No blanket rights determination was supplied | Exclude unverified copies; add only after documenting source, license/permission, attribution, and scope |

Referenced public standards and research are citations, not a claim that their text is Apache-licensed. A link does not authorize redistribution. External PDFs, proprietary policy documents, browser binaries, model weights, and vendor assets are not needed for the runtime and should not be bundled in this source release without separate permission. The source distribution includes only this release’s reviewed synthetic verification evidence; historical archives and runtime report folders are excluded. The wheel contains runtime assets only.

## Dependencies

Python dependencies are obtained separately from package indexes; they are not vendored into the project's wheel or source tree. `requirements.lock` and `requirements-dev.lock` record the selected versions and distribution hashes. Each dependency and its transitive dependencies retains its own license. The project's Apache-2.0 license does not relicense them.

Direct runtime projects are [FastAPI](https://github.com/fastapi/fastapi), [Pydantic](https://github.com/pydantic/pydantic), [SQLAlchemy](https://github.com/sqlalchemy/sqlalchemy), and [Uvicorn](https://github.com/encode/uvicorn). Development tooling includes pytest, HTTPX, jsonschema, PyPA build, setuptools, and wheel. Optional browser testing uses Playwright and a separately installed browser. Review the `LICENSE`/`NOTICE` files for the exact resolved distributions, including their transitive components, before redistributing an environment or image. This list is an inventory starting point, not a completed license audit or SBOM.

The Docker image incorporates the separately maintained Python/Debian base image and installed dependencies. Their terms and notices remain applicable. The mutable minor base tag must be replaced by a reviewed digest for an identified release image. A Python-only dependency audit does not cover operating-system packages or a browser binary.

## Rights-review record

Before public release, record for each imported or adapted file: source or supplier, author/rightsholder if known, version/hash, license or written permission, retained notices, and reviewer/date. Unresolved material must be removed or held from public distribution; do not fill gaps with guessed authors or licenses. Store confidential permission records privately and record only a non-sensitive summary in the repository.
