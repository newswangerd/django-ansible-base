from unittest import mock

from ansible_base.authentication.session import SessionAuthentication
from ansible_base.lib.utils.response import get_relative_url

authenticated_test_page = "authenticator-list"


@mock.patch("rest_framework.views.APIView.authentication_classes", [SessionAuthentication])
@mock.patch("ansible_base.authentication.authenticator_plugins.github_enterprise_org.AuthenticatorPlugin.authenticate")
def test_github_enterprise_org_auth_successful(authenticate, unauthenticated_api_client, github_enterprise_organization_authenticator, user):
    """
    Test that a successful Github authentication returns a 200 on the /me endpoint.

    Here we mock the Github authentication backend to return a user.
    """
    client = unauthenticated_api_client
    authenticate.return_value = user
    client.login()

    url = get_relative_url(authenticated_test_page)
    response = client.get(url)
    assert response.status_code == 200


@mock.patch("rest_framework.views.APIView.authentication_classes", [SessionAuthentication])
@mock.patch("ansible_base.authentication.authenticator_plugins.github_enterprise_org.AuthenticatorPlugin.authenticate", return_value=None)
def test_github_enterprise_org_auth_failed(authenticate, unauthenticated_api_client, github_enterprise_organization_authenticator):
    """
    Test that a failed Github authentication returns a 401 on the /me endpoint.
    """
    client = unauthenticated_api_client
    client.login()

    url = get_relative_url(authenticated_test_page)
    response = client.get(url)
    assert response.status_code == 401
