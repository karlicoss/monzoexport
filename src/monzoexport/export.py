from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from subprocess import run

from pymonzo import MonzoAPI

from .exporthelpers import logging_helper

# useful for debugging http calls
# import logging
# # Enable logging at the DEBUG level
# logging.basicConfig(level=logging.DEBUG)
from .exporthelpers.export_helper import Json

logger = logging_helper.make_logger(__name__)


class Exporter:
    def __init__(self, *args, full: bool = False, **kwargs) -> None:  # noqa: ARG002
        self.api = MonzoAPI()
        self.full = full

    def _get_account_data(self, account_id: str) -> Json:
        # ugh. after 5 minutes past auth can only get last 90 days
        # https://docs.monzo.com/#list-transactions
        # otherwise we'd get auth error

        # UPD from feb 2024
        # seems like even within 5 mins of first login, monzo api doesn't like when we pass timestamps too far back in time for 'since'
        # see https://community.monzo.com/t/changes-when-listing-with-our-api/158676
        assert not self.full, (
            'broken for now, see https://community.monzo.com/t/changes-when-listing-with-our-api/158676'
        )

        since = (datetime.now(tz=UTC) - timedelta(days=90 - 1)).strftime('%Y-%m-%dT%H:%M:%SZ')

        transactions: list[Json] = []

        while True:
            # see https://github.com/pawelad/pymonzo/blob/b1bcd6391b066276fb8f464f62f63ffc26f53da2/src/pymonzo/transactions/resources.py#L111-L123
            # sadly it doesn't expose raw api so we basically just have to copy it...
            chunk = self.api.transactions._get_response(
                method='get',
                endpoint='/transactions',
                params={
                    'account_id': account_id,
                    'limit': 100,
                    'since': since,
                    'expand[]': 'merchant',
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
        return {
            # todo balance? for ledging
            'transactions': transactions,
        }

    def export_json(self) -> Json:
        res = {}
        # see https://github.com/pawelad/pymonzo/blob/b1bcd6391b066276fb8f464f62f63ffc26f53da2/src/pymonzo/accounts/resources.py#L64-L65
        for acc_json in self.api.accounts._get_response(method='get', endpoint='/accounts').json()['accounts']:
            aid = acc_json['id']
            adata = {
                'info': acc_json,
                'data': self._get_account_data(account_id=aid),
            }
            res[aid] = adata
        return res


def get_json(**params):
    return Exporter(**params).export_json()


def login(client_id: str | None = None, client_secret: str | None = None) -> None:
    """
    Asking for user input here is ok; we only need to do it once
    """
    token_path = MonzoAPI.settings_path
    print(
        f'''
This will log you into Monzo API.

Please follow the [[https://github.com/pawelad/pymonzo#oauth-2][instructions]],
and enter the auth parameters as you are prompted.

You'll only need to input that manually once!
After that, the credentials are saved to the file ({token_path!s}), and you'll just have to pass it to the export script.
'''.lstrip()
    )

    # not sure if relying on builtin redirect URI is a good idea?
    redirect_uri = 'https://github.com'

    if client_id is None:
        client_id = input('client id: ')
    if client_secret is None:
        client_secret = input('client secret: ')

    # ugh. pymonzo has MonzoAPI.authorize(...) method
    # however, it tries to launch a local web server and get a response from browser which may not always work (e.g. on a VPS)
    # see https://github.com/pawelad/pymonzo/blob/b1bcd6391b066276fb8f464f62f63ffc26f53da2/src/pymonzo/client.py#L170-L175
    from authlib.integrations.httpx_client import OAuth2Client

    client = OAuth2Client(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        token_endpoint_auth_method="client_secret_post",
    )
    auth_url, _state = client.create_authorization_url(MonzoAPI.authorization_endpoint)
    print(f'Opening link to proceed with auth: {auth_url}')

    try:
        run(['xdg-open', auth_url], check=False)
    except:  # in case they not have xdg-open..
        pass

    authorization_response = input("paste FULL url you've been redirected to: ")
    token = client.fetch_token(
        url=MonzoAPI.token_endpoint,
        authorization_response=authorization_response,
    )

    print('tap in your monzo PHONE APP to allow access to the data')
    _tapped = input('press any key when tapped')

    from pymonzo.settings import PyMonzoSettings

    settings = PyMonzoSettings(
        client_id=client_id,
        client_secret=client_secret,
        token=token,
    )
    settings.save_to_disk(MonzoAPI.settings_path)
    print("Token should be saved on disk now (you won't need to relogin anymore)")


def make_parser():
    # TODO add logger configuration to export_helper?
    from .exporthelpers.export_helper import Parser, setup_parser

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

    parser.add_argument(
        '--first-time', action='store_true', help='combines the effects of --login and --full (legacy flag)'
    )
    return parser


def _migrate_token_if_necessary(token_path: Path) -> None:
    # from pymonzo v1 to v2 token format changed, this is just to migrate it without user involvement
    if not token_path.exists():
        return
    data = json.loads(token_path.read_text())
    if 'token' in data:
        # already v2 format
        return
    logger.warning(f"migrating {token_path} to pymonzo v2 format")
    # only 'client_id' and 'client_secret' stay on top
    # everything else goes inside 'token' dict
    client_id = data.pop('client_id')
    client_secret = data.pop('client_secret')
    new_data = {
        'client_id': client_id,
        'client_secret': client_secret,
        'token': data,
    }
    token_path.write_text(json.dumps(new_data, indent=1, sort_keys=True))


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

    token_path = Path(params['token_path'])
    _migrate_token_if_necessary(token_path)
    MonzoAPI.settings_path = token_path

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
