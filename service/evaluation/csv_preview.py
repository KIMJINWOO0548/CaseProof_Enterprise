"""Bounded, read-only conversion of a synthetic case CSV to the existing input DTO."""
import csv
import io
import re

from pydantic import TypeAdapter

from service.api.schemas_v1 import CSVPreview, CaseContext, CaseInput, RegisteredId, parse_body

CSV_LIMIT = 256 * 1024
CASE_LIMIT = 1000
ERROR_LIMIT = 50
COLUMNS = ['case_id', 'claim_days', 'case_context']
case_identity = TypeAdapter(RegisteredId)


def preview_cases(content, required, suite_version_id, revision):
    cases, errors, seen = [], [], set()
    errors_truncated = False

    def issue(code, row=None, column=None, **details):
        nonlocal errors_truncated
        if len(errors) == ERROR_LIMIT:
            errors_truncated = True
        else:
            errors.append(dict(code=code, row=row, column=column, **details))

    def result():
        ready = not errors
        evaluation = dict(suite_version_id=suite_version_id, case_inputs=sorted(cases, key=lambda case: case['case_id'])) if ready else None
        return CSVPreview(ready=ready, revision=revision, errors=errors, errors_truncated=errors_truncated, evaluation=evaluation)

    try:
        decoded = content.decode('utf-8-sig')
    except UnicodeDecodeError:
        issue('INVALID_UTF8')
        return result()

    reader = csv.reader(io.StringIO(decoded, newline=''), strict=True)
    first_line = 1
    try:
        if next(reader, None) != COLUMNS:
            issue('INVALID_HEADER', 1)
            return result()
        for index in range(CASE_LIMIT + 1):
            first_line = reader.line_num + 1
            row = next(reader, None)
            if row is None:
                break
            if index == CASE_LIMIT:
                issue('TOO_MANY_ROWS', first_line)
                return result()
            if len(row) != len(COLUMNS):
                issue('INVALID_COLUMN_COUNT', first_line)
                continue
            case_id, claim_days, context = row
            try:
                case_identity.validate_python(case_id)
            except ValueError:
                issue('INVALID_CASE_ID', first_line, 'case_id')
                continue
            if case_id not in required:
                issue('UNKNOWN_CASE_ID', first_line, 'case_id')
                continue
            if case_id in seen:
                issue('DUPLICATE_CASE_ID', first_line, 'case_id')
                continue
            seen.add(case_id)
            if re.fullmatch(r'[0-9]+', claim_days) is None:
                issue('INVALID_INTEGER', first_line, 'claim_days')
                continue
            digits = claim_days.lstrip('0')
            if len(digits) > 4:
                issue('INVALID_CLAIM_DAYS', first_line, 'claim_days')
                continue
            try:
                case_context = parse_body(CaseContext, context)
            except (ValueError, TypeError, RecursionError):
                issue('INVALID_CONTEXT', first_line, 'case_context')
                continue
            cases.append(CaseInput(case_id=case_id, claim_days=int(digits or '0'), case_context=case_context.model_dump()).model_dump())
    except csv.Error:
        issue('INVALID_CSV', first_line)
        return result()
    for case_id in sorted(required - seen):
        issue('MISSING_CASE_ID', column='case_id', case_id=case_id)
    return result()
