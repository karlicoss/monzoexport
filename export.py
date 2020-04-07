#!/usr/bin/env python3
import argparse
import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import logging


import pymonzo # type: ignore
from pymonzo import MonzoAPI # type: ignore


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


def login(client_id: Optional[str]=None, client_secret: Optional[str]=None):
    """
    Asking for user input here is ok; we only need to do it once
    """
    token_path = pymonzo.monzo_api.config.TOKEN_FILE_PATH
    print(f'''
This will log you into Monzo API.

Please follow the [[https://github.com/pawelad/pymonzo#oauth-2][instructions]],
and enter the auth parameters as you are prompted.

You'll only need to input that manually once!
After that, the credentials are saved to the file ({token_path}), and you'll just have to pass it to the export script.
'''.lstrip())


    redirect_uri = 'https://github.com'
    if client_id is None:
        client_id = input('client id: ')
    if client_secret is None:
        client_secret = input('client secret: ')
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


def make_parser():
    # TODO add logger configuration to export_helper?
    # TODO autodetect logzero?
    from export_helper import setup_parser, Parser
    parser = Parser("Tool to export your Monzo transactions")
    setup_parser(
        parser=parser,
        params=['token-path'],
        extra_usage='''
You can also import ~export.py~ as a module and call ~get_json~ function directly to get raw JSON.
        '''
    )
    # TODO exports -- need help for each param?
    parser.add_argument(
        '--first-time',
        action='store_true',
        help='''
This will log you in and fetch all of your transactions.

After 5 minutes after login, api can only sync the last 90 days of transactions.
See https://docs.monzo.com/#list-transactions for more information.
''')
    return parser


def main():
    parser = make_parser()
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

