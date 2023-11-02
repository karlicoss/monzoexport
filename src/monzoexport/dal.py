#!/usr/bin/env python3
from typing import Dict, NamedTuple, Sequence, Iterator, Set, List

from .exporthelpers import dal_helper, logging_helper
from .exporthelpers.dal_helper import PathIsh, Json, pathify

import orjson

from pymonzo.api_objects import MonzoTransaction, MonzoMerchant  # type: ignore[import-untyped]

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
    raw: Dict[TransactionId, TransactionRaw]

    @property
    def transactions(self) -> List[MonzoTransaction]:
        return list(map(MonzoTransaction, self.raw.values()))


class DAL:
    def __init__(self, sources: Sequence[PathIsh]) -> None:
        self.sources = list(map(pathify, sources))

    # TODO think about storage format again? acc_id is present in transactions anyway; might be easier to groupby?
    def data(self) -> Dict[AccountId, Account]:
        dd: Dict[AccountId, Account] = {}
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
        emitted: Set[TransactionId] = set()
        total = len(self.sources)
        width = len(str(total))
        for idx, path in enumerate(self.sources):
            logger.info(f'processing [{idx:>{width}}/{total:>{width}}] {path}')
            j = orjson.loads(path.read_bytes())
            if isinstance(j, list):
                # backport legacy data
                acc_id = j[0]['account_id']
                j = {acc_id: {'data': {'transactions': j}}}
            for acc_id, acc_payload in j.items():
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
    import pandas as pd
    import matplotlib.pyplot as plt  # type: ignore[import-not-found]

    for aid, acc in dao.data().items():
        print(f"Account {aid}: {len(acc.transactions)} transactions total")
        df = pd.DataFrame({
            'dt': t.created,
            'description': t.description,
            # TODO currency
            'amount': t.amount,
            'category': t.category,
        } for t in acc.transactions)
        if len(df) > 0:
            df.set_index('dt', inplace=True)
            # df.to_string(justify='left')
            breakdown = df.groupby('category')['amount'].sum()
            breakdown = breakdown.abs()
            breakdown.plot.pie(title=aid)  # type: ignore[call-overload]  # not sure why mypy complaining, it works...
        plt.show()
        # plt.savefig('plot.png')  # useful for testing


def main() -> None:
    dal_helper.main(DAL=DAL, demo=demo)


if __name__ == '__main__':
    main()
