"""Offline checks of exporter logic under simplified API assumptions.

These tests do not establish how Monzo's live API filters or orders transactions.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import Mock

import pytest
from httpx import Response

from . import export
from .exporthelpers.export_helper import Json

NOW = datetime(2026, 9, 23, tzinfo=UTC)


@pytest.fixture
def api(monkeypatch: pytest.MonkeyPatch) -> Mock:
    api = Mock()
    monkeypatch.setattr(export, 'MonzoAPI', Mock(return_value=api))
    clock = Mock(wraps=datetime)
    clock.now.return_value = NOW
    monkeypatch.setattr(export, 'datetime', clock)
    return api


def transaction(*, index: int, created: datetime, account_id: str = 'acc_test') -> Json:
    return {
        'id': f'tx_{index:06d}',
        'account_id': account_id,
        'created': created.isoformat(),
        'merchant': {'id': 'merchant_test'},
        'extra_field': 'preserve raw fields',
    }


def mock_transactions(*, api: Mock, rows: list[Json], inclusive: bool) -> None:
    """Model chronological pages with timestamp bounds and a result limit.

    The supplied rows must already be ordered by creation time.
    ID cursors are deliberately unsupported; this fake cannot validate their real API semantics.
    """

    def response(*, method: str, endpoint: str, params: Json) -> Response:
        assert method == 'get'
        assert endpoint == '/transactions'
        assert params['limit'] == 100
        start = datetime.fromisoformat(params['since'])
        before = datetime.fromisoformat(params['before'])
        candidates = [row for row in rows if row['account_id'] == params['account_id']]
        candidates = [
            row
            for row in candidates
            if datetime.fromisoformat(row['created']) > start
            or (inclusive and datetime.fromisoformat(row['created']) == start)
        ]
        assert timedelta(0) < before - start < timedelta(days=365)
        candidates = [
            row
            for row in candidates
            if datetime.fromisoformat(row['created']) < before
            or (inclusive and datetime.fromisoformat(row['created']) == before)
        ]
        return Response(200, json={'transactions': candidates[: params['limit']]})

    api.transactions._get_response.side_effect = response


@pytest.mark.parametrize('inclusive', [False, True])
def test_pagination_with_shared_timestamps(api: Mock, *, inclusive: bool) -> None:
    """Check page overlap and deduplication when a timestamp straddles the 100-record boundary.

    Advancing past that timestamp would lose records under exclusive filtering.
    Re-fetching it must return each record only once, regardless of ID ordering.
    Both boundary modes are assumptions exercised by the fake, not claims about Monzo's current behavior.
    """
    rows = [transaction(index=i, created=NOW - timedelta(days=1) + timedelta(seconds=i // 3)) for i in range(205)]
    rows[99]['id'], rows[102]['id'] = rows[102]['id'], rows[99]['id']
    mock_transactions(api=api, rows=rows, inclusive=inclusive)

    result = export.Exporter()._get_account_data(account_id='acc_test', start=NOW - timedelta(days=89), end=NOW)

    assert result['transactions'] == rows


def test_crowded_timestamp_fails_instead_of_silently_skipping(api: Mock) -> None:
    """Fail explicitly when timestamp pagination cannot reach every record.

    With 101 records at one timestamp and a 100-record limit, repeating the boundary cannot advance.
    Advancing past it would silently omit the last record, so returning partial success is incorrect.
    """
    rows = [transaction(index=i, created=NOW - timedelta(days=1)) for i in range(101)]
    mock_transactions(api=api, rows=rows, inclusive=False)
    exporter = export.Exporter()

    with pytest.raises(AssertionError, match='a full page may share one timestamp'):
        exporter._get_account_data(account_id='acc_test', start=NOW - timedelta(days=2), end=NOW)


@pytest.mark.parametrize('inclusive', [False, True])
def test_full_history_across_empty_windows_and_boundaries(api: Mock, *, inclusive: bool) -> None:
    """Check completeness across date windows, including empty years and exact boundaries.

    More than a page lies in the overlap, so seeing previously collected records must not end pagination.
    A much later record checks that an empty window does not end the whole export.
    The expected output also retains the account with no transactions.
    """
    created = datetime(2018, 1, 1, tzinfo=UTC)
    boundary = created - timedelta(seconds=1) + timedelta(days=364)
    rows = [transaction(index=0, created=created)]
    rows.extend(transaction(index=i, created=boundary - timedelta(milliseconds=1000 - i)) for i in range(1, 206))
    rows.extend(
        [
            transaction(index=206, created=boundary),
            transaction(index=207, created=boundary + timedelta(milliseconds=500)),
            transaction(index=208, created=NOW - timedelta(days=1)),
        ]
    )
    accounts = [
        {'id': 'acc_test', 'created': created.isoformat()},
        {'id': 'acc_empty', 'created': NOW.isoformat()},
    ]
    api.accounts._get_response.return_value = Response(200, json={'accounts': accounts})
    mock_transactions(api=api, rows=rows, inclusive=inclusive)

    result = export.Exporter(full=True).export_json()

    assert result == {
        'acc_test': {'info': accounts[0], 'data': {'transactions': rows}},
        'acc_empty': {'info': accounts[1], 'data': {'transactions': []}},
    }


def test_login_keeps_stdout_clean(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    """Keep authentication chatter out of the stdout stream reserved for exported JSON.

    Simulate login, including browser-launch output, without contacting Monzo or saving credentials.
    This checks stream separation, not OAuth correctness or exact prompt wording.
    """
    from authlib.integrations import httpx_client
    from pymonzo import settings

    monkeypatch.setattr(export.MonzoAPI, 'settings_path', tmp_path / 'token.json')
    answers = iter(['client', 'secret', 'https://github.com?code=test', ''])
    monkeypatch.setattr('builtins.input', lambda: next(answers))
    oauth = Mock()
    oauth.create_authorization_url.return_value = ('https://example.com/auth', 'state')
    monkeypatch.setattr(httpx_client, 'OAuth2Client', Mock(return_value=oauth))
    monkeypatch.setattr(settings, 'PyMonzoSettings', Mock())

    def open_browser(*_args, **kwargs) -> None:
        print('browser output', file=kwargs.get('stdout'))

    monkeypatch.setattr(export, 'run', open_browser)
    export.login()

    captured = capsys.readouterr()
    assert captured.out == ''
    assert 'browser output' in captured.err
