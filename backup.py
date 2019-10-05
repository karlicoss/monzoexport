#!/usr/bin/env python3.6
# pip3 install pymonzo

import json
import sys


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
    
    transactions = [t._raw_data for t in api.transactions(acc.id, reverse=False)]
    
    json.dump(transactions, sys.stdout)

if __name__ == '__main__':
    main()
    
