from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

import pytest

from . import export


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
