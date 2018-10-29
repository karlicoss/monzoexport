#!/usr/bin/env python3.6
# pip3 install pymonzo

from sys import stdout

from monzo_secrets import *
from pymonzo import MonzoAPI

from kython import *

# ugh, unclear how these two work...
# api = MonzoAPI(access_token=ACCESS_TOKEN)
# api = MonzoAPI(client_id=CLIENT_ID, client_secret=CLIENT_SECRET, auth_code=AUTH_CODE)


# this should just read token from disk if you copy it
api = MonzoAPI() # should read token from disk


[acc] = [acc for acc in api.accounts() if acc.id == ACCOUNT_ID]

transactions = [t._raw_data for t in api.transactions(acc.id, reverse=False)]

json_dumps(stdout, transactions)
