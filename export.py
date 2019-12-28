#!/usr/bin/env python3
import argparse
import json
from datetime import datetime, timedelta
from typing import Dict, Any
import logging


# TODO submodule?
# pip install pymonzo
import pymonzo
from pymonzo import MonzoAPI


from export_helper import Json


class Exporter:
    def __init__(self, *args, first_time=False, **kwargs) -> None:
        self.api = MonzoAPI()
        self.first_time = first_time

    def _get_account_data(self, account_id: str) -> Json:
        # TODO add argument --first-time or something?
        # ugh. after 5 minutes past auth can only get last 90 days
        # https://docs.monzo.com/#list-transactions
        # otherwise we'd get auth error
        if self.first_time:
            since = None
        else:
            since_dt = datetime.now() - timedelta(days=90 - 1)
            since = f'{since_dt:%Y-%m-%dT%H:%M:%SZ}'
        transactions = self.api._get_response(
            method='get',
            endpoint='/transactions',
            params={
                'account_id': account_id,
                'since'     : since,
            },
        ).json()['transactions']
        full_transactions = (
            self.api.transaction(t['id'], expand_merchant=True)._raw_data
            for t in transactions
        )
        return {
            # TODO balance? for ledging
            'transactions': list(full_transactions),
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


def login():
    """
    Asking for user input here is ok; we only need to do it once
    """
    # see https://github.com/pawelad/pymonzo#authentication
    redirect_uri = 'https://github.com'
    client_id = input('client id: ')
    client_secret = input('client secret: ')
    # TODO patch up redicect url here?
    auth_url = f'https://auth.monzo.com/?response_type=code&redirect_uri={redirect_uri}&client_id={client_id}'
    print(f'Opening link to proceed with auth: {auth_url}')
    from subprocess import run
    try:
        run(['xdg-open', auth_url])
    except: # in case they not have xdg-open..
        pass
    auth_code = input('auth code (after browser auth): ')
    api = MonzoAPI(
        client_id=client_id,
        client_secret=client_secret,
        auth_code=auth_code,
    )
    print('tap in your monzo PHONE APP to allow access to the data')
    tapped = input('press any key when tapped')
    print("Token should be saved on disk now (you won't need to relogin anymore)")


def main():
    # TODO add logger configuration to export_helper?
    # TODO autodetect logzero?
    from export_helper import setup_parser
    parser = argparse.ArgumentParser("Tool to export your personal Monzo data")
    setup_parser(parser=parser, params=['token-path']) # TODO exports -- need help for each param?
    parser.add_argument(
        '--first-time',
        action='store_true',
        help='''
This will log you in (TODO)
and fetch all of your transactions.

After 5 minutes after login, api can only sync the last 90 days of transactions.
See https://docs.monzo.com/#list-transactions for more information.
''')
    args = parser.parse_args()

    params = args.params
    dumper = args.dumper
    first_time = args.first_time

    pymonzo.monzo_api.config.TOKEN_FILE_PATH = params['token_path']

    if first_time:
        login()

    j = get_json(**params, first_time=first_time)
    js = json.dumps(j, indent=1, ensure_ascii=False, sort_keys=True)
    dumper(js)


if __name__ == '__main__':
    # TODO move to export_helper?
    # from kython.klogging import setup_logzero
    # setup_logzero(logging.getLogger('requests_oauthlib'), level=logging.DEBUG)
    main()

