# 확인한 공식 기술 자료

확인일: 2026-10-29. 아래는 설계/도구 사용 근거이며 CaseProof의 실행·보안 인증 증거가 아니다. 공개 페이지를 통째로 재배포하지 않고 링크와 사용 목적만 기록한다.

| 자료 | 사용 목적 |
| --- | --- |
| [PostgreSQL 17 Row Security](https://www.postgresql.org/docs/17/ddl-rowsecurity.html) | app role/owner/BYPASSRLS/정책의 위협 한계 |
| [PostgreSQL 17 CREATE POLICY](https://www.postgresql.org/docs/17/sql-createpolicy.html) | USING/WITH CHECK 및 필요한 read policy |
| [Pydantic strict mode](https://pydantic.dev/docs/validation/latest/concepts/strict_mode/) | strict field의 실제 JSON 타입 경계; 자체 HTTP 시험과 함께 사용 |
| [GitHub Actions secure use](https://docs.github.com/en/actions/reference/security/secure-use) | 최소 token 권한, full-length SHA action pin |
| [uv universal resolution](https://docs.astral.sh/uv/concepts/resolution/) | OS/Python marker가 포함된 잠금 파일 |
| [uv requirements compilation](https://docs.astral.sh/uv/pip/compile/) | lock 생성·constraint·hash 옵션 |
| [Apache License 2.0](https://www.apache.org/licenses/LICENSE-2.0.txt) | 라이선스 원문; 사용자 제공 코드의 권리 확인을 대신하지 않음 |

금융 규제·보험약관의 법적 해석을 이번 수정에서 새로 확정하지 않았다. 원본의 과거 공식자료 조사·경쟁 도구/가격은 현재 유효하다고 간주하지 않는다. 실제 운영/비교실험을 진행하는 시점에 1차 자료와 버전을 다시 확인한다.
