#!/usr/bin/env python3
import json
from pathlib import Path
from typing import Any, Dict, NamedTuple, Sequence, Union

from dal_helper import Json, PathIsh


AccountId = str
TransactionId = str
TransactionRaw = Json


class Account(NamedTuple):
    raw: Dict[TransactionId, TransactionRaw]

    @property
    def transactions(self):
        return list(self.raw.values())
        # TODO iterator?
        # TODO sort by date?


class DAL:
    def __init__(self, sources: Sequence[PathIsh]) -> None:
        self.sources = list(map(Path, sources))
        assert len(self.sources) == 1 # TODO later


    def data(self) -> Dict[AccountId, Account]:
        dd: Dict[AccountId, Account] = {}
        for src in self.sources:
            j = json.loads(src.read_text())
        for acc_id, payload in j.items():
            if acc_id not in dd:
                dd[acc_id] = Account({})
            acc = dd[acc_id]
            for traw in payload['data']['transactions']:
                acc.raw[traw['id']] = traw
            # TODO log how many were merged?
        return dd


def demo(dao: DAL) -> None:
    for aid, acc in dao.data().items():
        # TODO could call some pandas perhaps?
        print(f"Account {aid}: {len(acc.transactions)} transactions total")


if __name__ == '__main__':
    import dal_helper
    dal_helper.main(DAL=DAL, demo=demo)
