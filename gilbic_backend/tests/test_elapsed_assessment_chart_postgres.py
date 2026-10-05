"""Current posting roles are part of elapsed assessment authority."""

import pytest
from test_elapsed_period_assessment_postgres import (
    _candidate,
    _exact,
    _post,
    _prepare,
)
from test_elapsed_period_assessment_postgres import (
    elapsed_assessment as _elapsed_assessment,
)

elapsed_assessment = _elapsed_assessment


def test_posted_elapsed_proof_rejects_lost_posting_role(elapsed_assessment):
    f = elapsed_assessment
    _post(f, *_prepare(f))
    assert _exact(f)
    f["conn"].execute(
        "UPDATE accounting.accounts SET is_posting=false WHERE code='1120'"
    )
    assert not _exact(f), (
        "Historical journal existence cannot prove current posting authority"
    )


@pytest.mark.parametrize("code", ["1120", "4000", "1190", "5000"])
def test_new_elapsed_candidate_requires_posting_accounts(elapsed_assessment, code):
    f = elapsed_assessment
    f["conn"].execute(
        "UPDATE accounting.accounts SET is_posting=false WHERE code=%s", (code,)
    )
    assert not _candidate(f)["ready"]


def test_elapsed_proof_survives_display_name_and_retirement(elapsed_assessment):
    f = elapsed_assessment
    _post(f, *_prepare(f))
    assert _exact(f)
    f["conn"].execute(
        "UPDATE accounting.accounts SET name=name||' historical',is_active=false "
        "WHERE code IN ('1120','4000','1190','5000')"
    )
    assert _exact(f)
