from __future__ import annotations

import sys
from collections.abc import Iterator
from importlib import reload
from pathlib import Path
from typing import get_args, get_origin, get_type_hints

import orjson
import pytest

from . import dal


@pytest.fixture
def _without_pymonzo(monkeypatch: pytest.MonkeyPatch) -> None:
    # Block submodules too, since exporter tests may have already imported pymonzo.
    monkeypatch.setitem(sys.modules, 'pymonzo', None)
    for name in list(sys.modules):
        if name.startswith('pymonzo.'):
            monkeypatch.setitem(sys.modules, name, None)
    reload(dal)


def test_raw_data(tmp_path: Path, _without_pymonzo: None) -> None:
    """Read raw transactions and group them by account without pymonzo."""
    raw = {'id': 'tx_test', 'account_id': 'acc_test', 'amount': -123, 'extra_field': 'preserved'}
    payload = {'acc_test': {'data': {'transactions': [raw]}}}
    source = tmp_path / 'export.json'
    source.write_bytes(orjson.dumps(payload))

    reader = dal.DAL([source])
    assert list(reader.transactions_raw()) == [raw]
    assert reader.data()['acc_test'].raw == {'tx_test': raw}


def test_later_sources_override_transactions(tmp_path: Path) -> None:
    """Use later records while retaining older-only transactions and first-seen ID order."""
    original = {'id': 'tx_updated', 'account_id': 'acc_test', 'amount': -100, 'notes': 'old', 'obsolete_field': True}
    updated = {'id': 'tx_updated', 'account_id': 'acc_test', 'amount': -125, 'notes': 'new', 'settled': ''}
    older_only = {'id': 'tx_older_only', 'account_id': 'acc_test', 'amount': -200}
    newer_only = {'id': 'tx_newer_only', 'account_id': 'acc_test', 'amount': -300}

    # Filenames deliberately disagree with the supplied source order.
    older = tmp_path / 'z-old.json'
    newer = tmp_path / 'a-new.json'
    for path, records in ((older, [original, older_only]), (newer, [newer_only, updated])):
        path.write_bytes(orjson.dumps({'acc_test': {'data': {'transactions': records}}}))

    reader = dal.DAL([older, newer])
    assert list(reader.transactions_raw()) == [updated, older_only, newer_only]
    assert reader.data()['acc_test'].raw == {t['id']: t for t in [updated, older_only, newer_only]}


def transactions() -> Iterator[dal.MonzoTransaction]:
    """Match HPI's provider annotation without importing HPI or pymonzo."""
    return dal.DAL([]).transactions()


def test_runtime_annotations(_without_pymonzo: None) -> None:
    """Resolve DAL and HPI-style provider annotations without pymonzo."""
    for provider in (dal.DAL.transactions, transactions):
        return_type = get_type_hints(provider)['return']
        assert get_origin(return_type) is Iterator
        assert len(get_args(return_type)) == 1
