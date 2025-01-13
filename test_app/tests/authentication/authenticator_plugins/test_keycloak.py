from unittest import mock

from ansible_base.authentication.authenticator_plugins.keycloak import AuthenticatorPlugin
from ansible_base.authentication.authenticator_plugins.utils import get_authenticator_plugin
from ansible_base.authentication.session import SessionAuthentication
from ansible_base.authentication.social_auth import SocialAuthMixin
from ansible_base.lib.utils.response import get_relative_url

authenticated_test_page = "authenticator-list"


@mock.patch("rest_framework.views.APIView.authentication_classes", [SessionAuthentication])
@mock.patch("ansible_base.authentication.authenticator_plugins.keycloak.AuthenticatorPlugin.authenticate")
def test_keycloak_auth_successful(authenticate, unauthenticated_api_client, keycloak_authenticator, user):
    """
    Test that a successful keycloak authentication returns a 200 on the /me endpoint.

    Here we mock the keycloak authentication backend to return a user.
    """
    client = unauthenticated_api_client
    authenticate.return_value = user
    did_login = client.login()
    assert did_login, "Failed to login"

    url = get_relative_url(authenticated_test_page)
    response = client.get(url)
    assert response.status_code == 200


@mock.patch("rest_framework.views.APIView.authentication_classes", [SessionAuthentication])
@mock.patch("ansible_base.authentication.authenticator_plugins.keycloak.AuthenticatorPlugin.authenticate")
def test_keycloak_auth_failure(authenticate, unauthenticated_api_client, keycloak_authenticator):
    """
    Test that a failed keycloak authentication returns a 401 on the /me endpoint.

    Here we mock the keycloak authentication backend to return None.
    """
    client = unauthenticated_api_client
    authenticate.return_value = None
    client.login()

    url = get_relative_url(authenticated_test_page)
    response = client.get(url)
    assert response.status_code == 401


@mock.patch("social_core.backends.oauth.BaseOAuth2.extra_data")
def test_extra_data(mockedsuper):
    ap = AuthenticatorPlugin()

    class SocialUser:
        def __init__(self):
            self.extra_data = {}

    rDict = {}
    rDict["is_superuser"] = "True"
    rDict["Group"] = ["mygroup"]
    social = SocialUser()
    ap.extra_data(None, None, response=rDict, social=social)
    assert mockedsuper.called
    assert "is_superuser" in social.extra_data


def test_groups_setting(keycloak_authenticator):
    custom_groups_claim = "grupper"

    class MockedDb:
        def __init__(self, group_claim):
            self.slug = "fake"
            self.configuration = {"GROUPS_CLAIM": group_claim}

    class MockBackend(SocialAuthMixin):
        database_instance = MockedDb(custom_groups_claim)

        def __init__(self):
            pass

    backend = MockBackend()

    auth_type = "ansible_base.authentication.authenticator_plugins.keycloak"
    kap = get_authenticator_plugin(auth_type)
    kap.database_instance = MockedDb(custom_groups_claim)
    assert kap.strategy.get_setting('GROUPS_CLAIM', backend) == custom_groups_claim
    assert kap.groups_claim == custom_groups_claim
