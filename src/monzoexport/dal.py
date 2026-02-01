from __future__ import annotations

from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import NamedTuple

import orjson
from pymonzo.api_objects import (  # type: ignore[import-untyped]
    MonzoTransaction,
)

from .exporthelpers import dal_helper, logging_helper
from .exporthelpers.dal_helper import Json, pathify

### https://github.com/nomis/pymonzo/commit/45ebe1c01a867b3e6084827e957ccb16db5f6a55
T_keys = MonzoTransaction._required_keys
if 'account_balance' in T_keys:
    T_keys.remove('account_balance')
###


logger = logging_helper.make_logger(__name__)


AccountId = str
TransactionId = str
TransactionRaw = Json


def _fix_raw_transaction(raw) -> None:
    merchant = raw.get('merchant')
    if not isinstance(merchant, dict):
        # in old exports merchant is a str??
        return
    if 'created' not in merchant:
        # if there is no created date, parsing merchant fails
        # see https://github.com/pawelad/pymonzo/issues/28
        merchant['created'] = raw['created']


class Account(NamedTuple):
    raw: dict[TransactionId, TransactionRaw]

    @property
    def transactions(self) -> list[MonzoTransaction]:
        return list(map(MonzoTransaction, self.raw.values()))


class DAL:
    def __init__(self, sources: Sequence[Path | str]) -> None:
        self.sources = list(map(pathify, sources))

    # TODO think about storage format again? acc_id is present in transactions anyway; might be easier to groupby?
    def data(self) -> dict[AccountId, Account]:
        dd: dict[AccountId, Account] = {}
        for raw in self.transactions_raw():
            acc_id = raw['account_id']
            acc = dd.get(acc_id)
            if acc is None:
                acc = Account({})
                dd[acc_id] = acc
            acc.raw[raw['id']] = raw
        return dd

    # order in raw file looks ok, chronological?
    def transactions_raw(self) -> Iterator[TransactionRaw]:
        emitted: set[TransactionId] = set()
        total = len(self.sources)
        width = len(str(total))
        for idx, path in enumerate(self.sources):
            logger.info(f'processing [{idx:>{width}}/{total:>{width}}] {path}')
            j = orjson.loads(path.read_bytes())
            if isinstance(j, list):
                # backport legacy data
                acc_id = j[0]['account_id']
                j = {acc_id: {'data': {'transactions': j}}}
            for _acc_id, acc_payload in j.items():  # noqa: PERF102
                raws = acc_payload['data']['transactions']
                for raw in raws:
                    _fix_raw_transaction(raw)
                    t_id = raw['id']
                    # NOTE: hopefully makes sense to override here, as we collect more data?
                    # TODO not sure what to do about transactions that were updated...
                    if t_id in emitted:
                        continue
                    emitted.add(t_id)
                    yield raw

    def transactions(self) -> Iterator[MonzoTransaction]:
        yield from map(MonzoTransaction, self.transactions_raw())


def demo(dao: DAL) -> None:
    import matplotlib.pyplot as plt
    import pandas as pd

    for aid, acc in dao.data().items():
        print(f"Account {aid}: {len(acc.transactions)} transactions total")
        df = pd.DataFrame(
            {
                'dt': t.created,
                'description': t.description,  # ty: ignore[unresolved-attribute]
                # TODO currency
                'amount': t.amount,  # ty: ignore[unresolved-attribute]
                'category': t.category,  # ty: ignore[unresolved-attribute]
            }
            for t in acc.transactions
        )
        if len(df) > 0:
            df = df.set_index('dt')
            breakdown = df.groupby('category')['amount'].sum()
            breakdown = breakdown.abs()
            # ugh seems like y= is only necessary to make type checkers happy
            # y is optional, but pandas-stubs thinks they are required??
            breakdown.plot.pie(title=aid, y="amount")
        plt.show()
        # plt.savefig('plot.png')  # useful for testing


def main() -> None:
    dal_helper.main(DAL=DAL, demo=demo)


if __name__ == '__main__':
    main()
