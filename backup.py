#!/usr/bin/env python3.7
# pip3 install pymonzo

import json
import sys
from datetime import datetime, timedelta


from monzo_secrets import *


import pymonzo
# TODO shit. how to make it generic?
pymonzo.monzo_api.config.PYMONZO_REDIRECT_URI = REDIRECT_URI
pymonzo.monzo_api.config.REDIRECT_URI = REDIRECT_URI


from pymonzo import MonzoAPI


def main():
    # use this if token expired
    # api = MonzoAPI(client_id=CLIENT_ID, client_secret=CLIENT_SECRET, auth_code=AUTH_CODE)
    # this should just read token from disk
    api = MonzoAPI()

    [acc] = [acc for acc in api.accounts() if acc.id == ACCOUNT_ID] # TODO just backup all??
    
    # TODO maybe just receive all data?
    # TODO FIXME since
    # transactions = [t._raw_data for t in api.transactions(acc.id, reverse=False)]

    # ugh. after 5 minutes past auth can only get last 90 days now
    since = datetime.now() - timedelta(days=90 - 1)  
    transactions = api._get_response(
        method='get',
        endpoint='/transactions',
        params={
            'account_id': acc.id,
            'since'     : f'{since:%Y-%m-%dT%H:%M:%SZ}',
        },
    ).json()['transactions']
    # TODO perhaps keeping transactions as they are in a dict
    
    json.dump(transactions, sys.stdout, indent=1, ensure_ascii=False, sort_keys=True)

if __name__ == '__main__':
    main()
    
