#!/usr/bin/env python3
import json
from pathlib import Path
from typing import Any, Dict, NamedTuple, Sequence, Union, List

from pymonzo.api_objects import MonzoTransaction, MonzoMerchant # type: ignore

import dal_helper
from dal_helper import Json, PathIsh

logger = dal_helper.logger('monzoexport', level='debug')


AccountId = str
TransactionId = str
TransactionRaw = Json


class Account(NamedTuple):
    raw: Dict[TransactionId, TransactionRaw]

    @property
    def transactions(self) -> List[MonzoTransaction]:
        return list(map(MonzoTransaction, self.raw.values()))
        # TODO iterator?
        # TODO sort by date?


class DAL:
    def __init__(self, sources: Sequence[PathIsh]) -> None:
        self.sources = list(map(Path, sources))


    # TODO think about storage format again? acc_id is present in transactions anyway; might be easier to groupby?
    def data(self) -> Dict[AccountId, Account]:
        dd: Dict[AccountId, Account] = {}
        for src in self.sources:
            logger.debug("processing %s", src)
            j = json.loads(src.read_text())
            if isinstance(j, list):
                # backport legacy data
                acc_id = j[0]['account_id']
                j = {acc_id: {'data': {'transactions': j}}}
            for acc_id, payload in j.items():
                if acc_id not in dd:
                    dd[acc_id] = Account({})
                acc = dd[acc_id]
                transactions = payload['data']['transactions']
                new_trans = 0
                for traw in transactions:
                    tid = traw['id']
                    new_trans += 1 if tid not in acc.raw else 0
                    # NOTE: hopefully makes sense to override here, as we collect more data?
                    # don't think it's worthy arbitering etc.
                    acc.raw[tid] = traw
                logger.debug('%s: %-6d/%-6d new transactions (%-6d total)', acc_id, new_trans, len(transactions), len(acc.raw))
        return dd


def demo(dao: DAL) -> None:
    import pandas as pd # type: ignore
    import matplotlib.pyplot as plt # type: ignore
    for aid, acc in dao.data().items():
        print(f"Account {aid}: {len(acc.transactions)} transactions total")
        df = pd.DataFrame({
            'dt': t.created,
            'description': t.description, # type: ignore
            # TODO currency
            'amount': t.amount, # type: ignore
            'category': t.category, # type: ignore
        } for t in acc.transactions)
        if len(df) > 0:
            df.set_index('dt', inplace=True)
            # df.to_string(justify='left')
            breakdown = df.groupby('category')['amount'].sum()
            breakdown = breakdown.abs()
            breakdown.plot.pie(title=aid)
        plt.show()


if __name__ == '__main__':
    dal_helper.main(DAL=DAL, demo=demo)
