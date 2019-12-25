#!/usr/bin/env python3
# pip install pymonzo
import argparse
import json
from datetime import datetime, timedelta
from typing import Dict, Any


# TODO submodule
import pymonzo
# pymonzo.monzo_api.config.PYMONZO_REDIRECT_URI = REDIRECT_URI
# pymonzo.monzo_api.config.REDIRECT_URI = REDIRECT_URI # TODO don't need this anymore?


from pymonzo import MonzoAPI


# TODO also move to export_helper??
Json = Dict[str, Any]


class Exporter:
    def __init__(self, *wargs, **kwargs) -> None:
        self.api = MonzoAPI()

    def _get_account_data(self, account_id: str) -> Json:
        # transactions = [t._raw_data for t in api.transactions(acc.id, reverse=False)]

        # ugh. after 5 minutes past auth can only get last 90 days
        # https://docs.monzo.com/#list-transactions
        # TODO add argument --first-time or something?
        since = datetime.now() - timedelta(days=90 - 1)
        transactions = self.api._get_response(
            method='get',
            endpoint='/transactions',
            params={
                'account_id': account_id,
                'since'     : f'{since:%Y-%m-%dT%H:%M:%SZ}',
            },
        ).json()['transactions']
        # TODO perhaps keeping transactions as they are in a dict
        # TODO he?
        return {
            # TODO balance? for ledging
            'transactions': transactions,
        }

    # TODO could use dictify here...
    def export_json(self) -> Json:
        res = {}
        for a in self.api.accounts():
            adata = {}
            aid = a.id
            adata['info'] = a._raw_data
            adata['data'] = self._get_account_data(account_id=aid)
            res[aid] = adata
        return res


def get_json(**params):
    return Exporter(**params).export_json()


def main():
    from export_helper import setup_parser
    parser = argparse.ArgumentParser("Tool to export your personal Monzo data")
    setup_parser(parser=parser, params=['token-path', 'account-id']) # TODO exports -- need help for each param?
    args = parser.parse_args()

    params = args.params
    dumper = args.dumper

    # use this if token expired
    # api = MonzoAPI(client_id=CLIENT_ID, client_secret=CLIENT_SECRET, auth_code=AUTH_CODE)
    # this should just read token from disk
    pymonzo.monzo_api.config.TOKEN_FILE_PATH = params['token_path']

    j = get_json(**params)
    js = json.dumps(j, indent=1, ensure_ascii=False, sort_keys=True)
    dumper(js)


if __name__ == '__main__':
    main()

