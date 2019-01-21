#!/usr/bin/env python3.6
# pip3 install pymonzo

from sys import stdout

from monzo_secrets import *

import pymonzo

# TODO shit. how to make it generic?
pymonzo.monzo_api.config.PYMONZO_REDIRECT_URI = REDIRECT_URI
pymonzo.monzo_api.config.REDIRECT_URI = REDIRECT_URI


from pymonzo import MonzoAPI

from kython import *

# use this if token expired
# api = MonzoAPI(client_id=CLIENT_ID, client_secret=CLIENT_SECRET, auth_code=AUTH_CODE)
# this should just read token from disk if you copy it
api = MonzoAPI() # should read token from disk


## upd from 210119 -- this is probably unnecessary
# ugh, unclear how these two work...
# api = MonzoAPI(client_id=CLIENT_ID, client_secret=CLIENT_SECRET, auth_code=AUTH_CODE, access_token=ACCESS_TOKEN)
###



[acc] = [acc for acc in api.accounts() if acc.id == ACCOUNT_ID]

transactions = [t._raw_data for t in api.transactions(acc.id, reverse=False)]

json_dumps(stdout, transactions)
