"""Unit tests for the issue #587 fix: case-insensitive api_key handling and
kwargs-based Configuration initialization. No network access required.
"""
import copy

import pytest

from plaid import Configuration, Environment
from plaid.configuration import CaseInsensitiveDict, _normalize_config_key


# --------------------------------------------------------------------------
# key normalization
# --------------------------------------------------------------------------

class TestNormalizeKey:
    @pytest.mark.parametrize("variant", [
        "clientId", "client_id", "CLIENT_ID", "Client_Id", "client-id",
        "CLIENT-ID", "cLiEnTiD",
    ])
    def test_variants_collapse(self, variant):
        assert _normalize_config_key(variant) == "clientid"

    def test_non_string_passthrough(self):
        assert _normalize_config_key(42) == 42
        assert _normalize_config_key(None) is None


class TestCaseInsensitiveDict:
    def test_init_from_mapping(self):
        d = CaseInsensitiveDict({"client_id": "x"})
        assert d["clientId"] == "x"
        assert d["CLIENT_ID"] == "x"

    def test_init_kwargs(self):
        d = CaseInsensitiveDict(clientId="x")
        assert d["client_id"] == "x"

    def test_set_get_del_contains(self):
        d = CaseInsensitiveDict()
        d["CLIENT_ID"] = "x"
        assert "clientId" in d
        assert "client_id" in d
        assert d.get("client-id") == "x"
        del d["ClientId"]
        assert "clientid" not in d

    def test_update_and_pop(self):
        d = CaseInsensitiveDict({"a": 1})
        d.update({"CLIENT_ID": "x"}, SECRET="y")
        assert d["client_id"] == "x"
        assert d["secret"] == "y"
        assert d.pop("ClientId") == "x"
        assert d.pop("missing", "dflt") == "dflt"

    def test_setdefault(self):
        d = CaseInsensitiveDict()
        assert d.setdefault("CLIENT_ID", "x") == "x"
        assert d.setdefault("client_id", "y") == "x"  # existing wins

    def test_copy(self):
        d = CaseInsensitiveDict({"CLIENT_ID": "x"})
        c = d.copy()
        assert isinstance(c, CaseInsensitiveDict)
        assert c["clientId"] == "x"

    def test_non_string_keys(self):
        d = CaseInsensitiveDict({1: "one"})
        assert d[1] == "one"


# --------------------------------------------------------------------------
# Configuration — the five issue failure modes
# --------------------------------------------------------------------------

class TestIssueModes:
    def test_mode1_snake_case_dict_keys(self):
        c = Configuration(api_key={"client_id": "CID", "secret": "SEC",
                                    "plaid_version": "2020-09-14"})
        auth = c.auth_settings()
        assert auth["clientId"]["value"] == "CID"
        assert auth["secret"]["value"] == "SEC"
        assert auth["plaidVersion"]["value"] == "2020-09-14"

    def test_mode2_case_variant_dict_keys(self):
        c = Configuration(api_key={"CLIENT_ID": "CID", "SECRET": "SEC"})
        assert c.get_api_key_with_prefix("clientId") == "CID"
        assert c.get_api_key_with_prefix("secret") == "SEC"

    def test_mode3_kwargs_constructor(self):
        c = Configuration(client_id="CID", secret="SEC",
                          plaid_version="2020-09-14", environment="sandbox")
        auth = c.auth_settings()
        assert auth["clientId"]["value"] == "CID"
        assert auth["secret"]["value"] == "SEC"
        assert auth["plaidVersion"]["value"] == "2020-09-14"
        assert c.host == Environment.Sandbox

    def test_mode4_case_insensitive_lookup(self):
        c = Configuration(api_key={"clientId": "CID"})
        assert c.api_key["client_id"] == "CID"
        assert c.api_key["CLIENT-ID"] == "CID"

    def test_mode5_mutation_normalizes(self):
        c = Configuration(api_key={"clientId": "CID"})
        c.api_key["CLIENT_ID"] = "NEW"
        assert c.get_api_key_with_prefix("clientId") == "NEW"

    def test_issue_example_end_to_end(self):
        # Mirrors the example in the issue body.
        c = Configuration(client_id="your-client-id", secret="your-secret",
                          plaid_version="2020-09-14", environment="sandbox")
        assert c.api_key["clientId"] == "your-client-id"
        assert c.api_key["client_id"] == "your-client-id"
        c.api_key["CLIENT_ID"] = "new-client-id"
        assert c.get_api_key_with_prefix("clientId") == "new-client-id"


# --------------------------------------------------------------------------
# Regression: previously working behaviour must be unchanged
# --------------------------------------------------------------------------

class TestRegression:
    def test_exact_camelcase_still_works(self):
        c = Configuration(api_key={"clientId": "CID", "secret": "SEC"})
        assert c.api_key["clientId"] == "CID"
        assert c.get_api_key_with_prefix("clientId") == "CID"
        auth = c.auth_settings()
        assert auth["clientId"]["key"] == "PLAID-CLIENT-ID"

    def test_default_configuration_unchanged(self):
        c = Configuration()
        assert dict(c.api_key) == {}
        assert c.host == Environment.Production
        assert c.auth_settings() == {}

    def test_api_key_prefix_normalized(self):
        c = Configuration(api_key={"clientId": "CID"},
                          api_key_prefix={"CLIENTID": "Bearer"})
        assert c.get_api_key_with_prefix("clientId") == "Bearer CID"

    def test_later_assignment_is_wrapped(self):
        c = Configuration()
        c.api_key = {"client_id": "CID"}  # plain dict assigned post-init
        assert isinstance(c.api_key, CaseInsensitiveDict)
        assert c.get_api_key_with_prefix("clientId") == "CID"

    def test_explicit_dict_beats_kwarg(self):
        c = Configuration(api_key={"clientId": "DICT"},
                          client_id="KWARG")
        assert c.get_api_key_with_prefix("clientId") == "DICT"

    def test_none_api_key(self):
        c = Configuration(api_key=None)
        assert dict(c.api_key) == {}

    def test_deepcopy_and_default_copy(self):
        c = Configuration(client_id="CID", environment="sandbox")
        Configuration.set_default(c)
        try:
            d = Configuration.get_default_copy()
            assert d.get_api_key_with_prefix("clientId") == "CID"
            assert d.host == Environment.Sandbox
            assert isinstance(d.api_key, CaseInsensitiveDict)
        finally:
            Configuration._default = None

    def test_environment_resolution(self):
        assert Configuration(environment="sandbox").host == Environment.Sandbox
        assert Configuration(environment="SANDBOX").host == Environment.Sandbox
        assert Configuration(environment="production").host == Environment.Production
        assert Configuration(environment=Environment.Sandbox).host == Environment.Sandbox
        custom = "https://custom.example.com"
        assert Configuration(environment=custom).host == custom
        # explicit host still works when no environment kwarg is given
        assert Configuration(host="https://x.example.com").host == "https://x.example.com"
