

Tool to export your Monzo transactions

<!-- Keep this separator: Quarto otherwise moves the generated preamble below the following heading. -->

# Installing

## Basic install

Install with pip:

`pip3 install 'monzoexport[export,dal,optional] @ git+https://github.com/karlicoss/monzoexport'`

The
[‘extras’](https://packaging.python.org/en/latest/tutorials/installing-packages/#installing-extras)
in square brackets provide additional dependencies, feel free to omit
some of them if you don’t need them:

- `export` is needed for [export functionality](#exporting)
- `dal` is needed to [access exported data](#using-the-data)
- `optional` is for nicer logging facilities and faster JSON processing

See [`optional-dependencies`](pyproject.toml) section in
`pyproject.toml` for more details.

## Advanced install options

- editable install

  You’ll need to clone the repository with submodules.

  - use `git clone --recursive`, or
    `git pull && git submodule update --init`
  - after that, you can use `pip3 install --editable`

- run via `uvx`

  This allows you to run monzoexport without installing if you just want
  to quickly try it out. E.g.:

  `uvx --from 'monzoexport[export,dal,optional] @ git+https://github.com/karlicoss/monzoexport' python3 -m monzoexport.export ...`

  It’s a little awkward though since you can’t install tools without
  ‘executable scripts’ with uv at the moment.

# Exporting

## Running export

Usage:

**Recommended**: create `secrets.py` keeping your API parameters, e.g.:

    token-path = "TOKEN-PATH"

After that, use:

    python3 -m monzoexport.export --secrets /path/to/secrets.py

That way you type less and have control over where you keep your
plaintext secrets.

**Alternatively**, you can pass parameters directly, e.g.

    python3 -m monzoexport.export --token-path <token-path>

However, this is verbose and prone to leaking your keys/tokens/passwords
in shell history.

You can also import `monzoexport.export` as a module and call `get_json`
function directly to get raw JSON.

I **highly** recommend checking exported files at least once just to
make sure they contain everything you expect from your export. If they
don’t, please feel free to ask or raise an issue!

## Setting up API parameters

Create a new OAuth client on the [Monzo developer
website](https://developers.monzo.com/apps/home).

- Set confidentiality to `confidential`.
- Set the redirect URI to `https://github.com`, which is currently
  hardcoded in the export script.

After creating the client, select it in the OAuth clients list.

- Add your user ID to the collaborators. Your user ID is the same as the
  app’s owner ID. You might need to refresh the page before the change
  appears.
- Note the client ID and client secret, which you’ll need for the
  export.

## Initial export

The `--first-time` parameter walks you through the login procedure:

    python3 -m monzoexport.export --token-path token.json --first-time /path/to/first-export.json

After a successful export, move `token.json` somewhere safe and pass its
location as `--token-path` later. You won’t need to pass `--first-time`
again.

**After five minutes from login, the API can only sync the last 90 days
of transactions.** See the [Monzo API
documentation](https://docs.monzo.com/#list-transactions) for more
information. It is therefore important to do at least one export
immediately after receiving the token.

# Using the data

You can use `monzoexport.dal` (stands for “Data Access/Abstraction
Layer”) to access your exported data, even offline. I elaborate on
motivation behind it [here](https://beepb00p.xyz/exports.html#dal).

- the main use case is importing it as a Python module for
  **programmatic access** to your data.

  You can find some inspiration in
  [`my.`](https://beepb00p.xyz/mypkg.html) package that I’m using as an
  API to all my personal data.

- to test it against your export, simply run:
  `python3 -m monzoexport.dal --source /path/to/export`

- you can also try it interactively in an IPython shell:
  `python3 -m monzoexport.dal --source /path/to/export --interactive`

# Contributing

If you want to contribute to or develop this project, check out [GitHub
Actions](.github/workflows/main.yml) to see how the project is run and
tested.

Generally you should be able to run the checks via `tox`, e.g.

`uv tool run --with tox-uv tox`

## Updating README

This README is generated from a ‘literate’ Quarto
[README.qmd](README.qmd) via the following command:

`tox -e quarto`

If you want to correct something, feel free to simply update `README.md`
though, I can reconcile the changes next time I regenerate it.
