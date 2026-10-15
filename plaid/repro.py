"""repro.py — reproduce plaid/plaid-python#587 failure modes against the CURRENT (unfixed) SDK.

Run: PYTHONPATH=~/workspace/proof-of-work/plaid/repo ~/workspace/proof-of-work/plaid/.venv/bin/python repro.py
"""
import traceback

import plaid
from plaid import Configuration, Environment

print("plaid-python version:", plaid.__version__ if hasattr(plaid, "__version__") else "unknown")
print("Configuration module:", Configuration.__module__)
print()

failures = []


def check(name, fn):
    """fn returns True when behaviour is correct."""
    try:
        ok = fn()
    except Exception:
        ok = False
        print(f"[{name}] EXCEPTION:")
        traceback.print_exc(limit=2)
    print(f"[{name}] {'OK' if ok else 'FAILS'}")
    if not ok:
        failures.append(name)
    print()


def mode1_snake_case_dict_keys():
    """Issue: snake_case dict keys should map to camelCase security-scheme ids."""
    c = Configuration(api_key={"client_id": "CID", "secret": "SEC", "plaid_version": "2020-09-14"})
    auth = c.auth_settings()
    return "clientId" in auth and auth["clientId"]["value"] == "CID"


def mode2_case_variant_dict_keys():
    """Issue: case-insensitive key access (CLIENT_ID / client-id -> clientId)."""
    c = Configuration(api_key={"CLIENT_ID": "CID", "SECRET": "SEC", "PLAID_VERSION": "2020-09-14"})
    got = c.get_api_key_with_prefix("clientId")
    return got == "CID"


def mode3_kwargs_constructor():
    """Issue: direct keyword arguments (client_id, secret, plaid_version, environment)."""
    c = Configuration(
        client_id="CID",
        secret="SEC",
        plaid_version="2020-09-14",
        environment="sandbox",
    )
    auth = c.auth_settings()
    return (
        "clientId" in auth
        and auth["clientId"]["value"] == "CID"
        and auth["secret"]["value"] == "SEC"
        and c.host == Environment.Sandbox
    )


def mode4_case_insensitive_lookup():
    """Issue example: api_key['client_id'] should find 'clientId' after init."""
    c = Configuration(api_key={"clientId": "CID", "secret": "SEC"})
    return c.api_key["client_id"] == "CID"


def mode5_mutation_normalizes():
    """Issue example: api_key['CLIENT_ID'] = X should be readable as clientId."""
    c = Configuration(api_key={"clientId": "CID"})
    c.api_key["CLIENT_ID"] = "NEW"
    return c.get_api_key_with_prefix("clientId") == "NEW"


def baseline_exact_camelcase():
    """Previously-working mode: exact camelCase keys must keep working."""
    c = Configuration(api_key={"clientId": "CID", "secret": "SEC"})
    return (
        c.api_key["clientId"] == "CID"
        and c.get_api_key_with_prefix("clientId") == "CID"
    )


check("mode1 snake_case dict keys", mode1_snake_case_dict_keys)
check("mode2 case-variant dict keys", mode2_case_variant_dict_keys)
check("mode3 kwargs constructor", mode3_kwargs_constructor)
check("mode4 case-insensitive lookup", mode4_case_insensitive_lookup)
check("mode5 mutation normalizes", mode5_mutation_normalizes)
check("baseline exact camelCase keys", baseline_exact_camelcase)

print("=" * 60)
print("FAILURES:", len(failures), failures if failures else "(none)")
raise SystemExit(1 if failures else 0)
