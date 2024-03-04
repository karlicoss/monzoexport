#!/usr/bin/env python3
from datetime import datetime, timedelta, timezone
import json
from subprocess import run
from typing import Optional, List


from .exporthelpers import export_helper
from .exporthelpers.export_helper import Json

# useful for debugging http calls
# import logging
# # Enable logging at the DEBUG level
# logging.basicConfig(level=logging.DEBUG)

### https://github.com/nomis/pymonzo/commit/45ebe1c01a867b3e6084827e957ccb16db5f6a55
from pymonzo.api_objects import MonzoTransaction  # type: ignore[import-untyped]

T_keys = MonzoTransaction._required_keys
if 'account_balance' in T_keys:
    T_keys.remove('account_balance')
###

import pymonzo  # type: ignore
from pymonzo import MonzoAPI


class Exporter:
    def __init__(self, *args, full: bool = False, **kwargs) -> None:
        self.api = MonzoAPI()
        self.full = full

    def _get_account_data(self, account_id: str) -> Json:
        # ugh. after 5 minutes past auth can only get last 90 days
        # https://docs.monzo.com/#list-transactions
        # otherwise we'd get auth error

        # UPD from feb 2024
        # seems like even within 5 mins of first login, monzo api doesn't like when we pass timestamps too far back in time for 'since'
        # see https://community.monzo.com/t/changes-when-listing-with-our-api/158676
        assert not self.full, 'broken for now, see https://community.monzo.com/t/changes-when-listing-with-our-api/158676'

        since = (datetime.now(tz=timezone.utc) - timedelta(days=90 - 1)).strftime('%Y-%m-%dT%H:%M:%SZ')

        transactions: List[Json] = []

        while True:
            chunk = self.api._get_response(
                method='get',
                endpoint='/transactions',
                params={
                    'account_id': account_id,
                    'limit': 100,
                    'since': since,
                },
            ).json()['transactions']

            if len(chunk) == 0:
                # this is possible if account had no transactions at all? handle just in case
                break

            if len(transactions) > 0:
                # 'since' is always inclusive, and we don't remove first transaction in chunk, there will be dupes
                # assert just in case
                assert transactions[-1]['id'] == chunk[0]['id']
                chunk = chunk[1:]

            if len(chunk) == 0:
                # no more data
                break

            transactions.extend(chunk)
            since = transactions[-1]['created']

        # ok, they are ordered by creation date?
        full_transactions = (
            self.api._get_response(method='get', endpoint=f"/transactions/{t['id']}", params={'expand[]': 'merchant'}).json()['transaction']
            # NOTE: sadly this doens't work at the momen, see https://github.com/pawelad/pymonzo/issues/28
            # self.api.transaction(t['id'], expand_merchant=True)._raw_data
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


def login(client_id: Optional[str] = None, client_secret: Optional[str] = None) -> None:
    """
    Asking for user input here is ok; we only need to do it once
    """
    token_path = pymonzo.monzo_api.config.TOKEN_FILE_PATH
    print(
        f'''
This will log you into Monzo API.

Please follow the [[https://github.com/pawelad/pymonzo#oauth-2][instructions]],
and enter the auth parameters as you are prompted.

You'll only need to input that manually once!
After that, the credentials are saved to the file ({token_path}), and you'll just have to pass it to the export script.
'''.lstrip()
    )

    # not sure if relying on builtin redirect URI is a good idea?
    redirect_uri = 'https://github.com'
    pymonzo.monzo_api.config.REDIRECT_URI = redirect_uri

    if client_id is None:
        client_id = input('client id: ')
    if client_secret is None:
        client_secret = input('client secret: ')
    auth_url = f'https://auth.monzo.com/?response_type=code&redirect_uri={redirect_uri}&client_id={client_id}&state=some_secret_string'
    print(f'Opening link to proceed with auth: {auth_url}')

    try:
        run(['xdg-open', auth_url])
    except:  # in case they not have xdg-open..
        pass
    auth_code = input('auth code (after you authenticate in the web browser), only insert code= query param: ')
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
    from .exporthelpers.export_helper import setup_parser, Parser

    parser = Parser("Tool to export your Monzo transactions")
    setup_parser(
        parser=parser,
        params=['token-path'],
        extra_usage='''
You can also import ~export.py~ as a module and call ~get_json~ function directly to get raw JSON.
        ''',
    )
    parser.add_argument('--login', action='store_true', help='use to log in (only need to use once)')
    parser.add_argument(
        '--full',
        action='store_true',
        help='''
This will fetch all of your transactions.

Note that after 5 minutes after login, api can only sync the last 90 days of transactions.
See https://docs.monzo.com/#list-transactions for more information.
''',
    )

    parser.add_argument('--first-time', action='store_true', help='combines the effects of --login and --full (legacy flag)')
    return parser


def main() -> None:
    parser = make_parser()
    args = parser.parse_args()

    params = args.params
    dumper = args.dumper
    full = args.full
    do_login = args.login
    first_time = args.first_time
    if first_time:
        full = True
        do_login = True

    # todo use env variable?
    pymonzo.monzo_api.config.TOKEN_FILE_PATH = params['token_path']

    if do_login:
        login()

    j = get_json(**params, full=full)
    js = json.dumps(j, indent=1, ensure_ascii=False, sort_keys=True)
    dumper(js)


if __name__ == '__main__':
    # TODO move to export_helper?
    # from kython.klogging import setup_logzero
    # setup_logzero(logging.getLogger('requests_oauthlib'), level=logging.DEBUG)
    main()
