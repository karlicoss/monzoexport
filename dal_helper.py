import argparse
from glob import glob
from pathlib import Path
from typing import Any, Dict, Union

import IPython # type: ignore


PathIsh = Union[str, Path]
Json = Dict[str, Any] # TODO Mapping?


def main(*, DAL, demo=None):
    p = argparse.ArgumentParser()
    p.add_argument('--source', type=str, required=True)
    p.add_argument('--no-glob', action='store_true')
    p.add_argument('-i', '--interactive', action='store_true', help='Start Ipython session to play with data')
    args = p.parse_args()
    if '*' in args.source and not args.no_glob:
        sources = glob(args.source)
    else:
        sources = [args.source]

    # logger.debug('using %s', sources)
    dao = DAL(sources)
    print(dao)
    # TODO autoreload would be nice... https://github.com/ipython/ipython/issues/1144
    # TODO maybe just launch through ipython in the first place?
    if args.interactive:
        IPython.embed(header="Feel free to mess with 'dao' object in the interactive shell")
    else:
        assert demo is not None
        demo(dao=dao)
