from unittest import mock

import pytest
from django.test import override_settings

from ansible_base.authentication.session import SessionAuthentication
from ansible_base.lib.utils.response import get_fully_qualified_url, get_relative_url

authenticated_test_page = "authenticator-list"


@mock.patch("rest_framework.views.APIView.authentication_classes", [SessionAuthentication])
@mock.patch("ansible_base.authentication.authenticator_plugins.google_oauth2.AuthenticatorPlugin.authenticate")
def test_oidc_auth_successful(authenticate, unauthenticated_api_client, google_oauth2_authenticator, user):
    """
    Test that a successful Google OAuth2 authentication returns a 200 on the /me endpoint.

    Here we mock the Google OAuth2 authentication backend to return a user.
    """
    client = unauthenticated_api_client
    authenticate.return_value = user
    client.login()

    url = get_relative_url(authenticated_test_page)
    response = client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
@pytest.mark.parametrize(
    "key, secret, slug, expected_status_code, expected_error",
    [
        (None, None, None, 400, {'KEY': ['This field may not be null.']}),
        ('', None, None, 400, {'KEY': ['This field may not be blank.']}),
        ('testgoogleoauth2', '', None, 400, {'SECRET': ['This field may not be blank.']}),
        ('testgoogleoauth2', None, None, 201, {}),
        ('testgoogleoauth2', "testgoogleoauth2_secret", None, 201, {}),
        ('testgoogleoauth2', "testgoogleoauth2_secret", "test_chosen_slug", 201, {}),
    ],
)
def test_google_oauth2_callback_url_validation(
    admin_api_client,
    key,
    secret,
    slug,
    expected_status_code,
    expected_error,
):
    config = {"KEY": key, "SECRET": secret}

    data = {
        "name": "GOOGLE OAUTH2 TEST",
        "enabled": True,
        "create_objects": True,
        "remove_users": True,
        "configuration": config,
        "type": "ansible_base.authentication.authenticator_plugins.google_oauth2",
    }
    if slug:
        data["slug"] = slug

    url = get_relative_url("authenticator-list")
    response = admin_api_client.post(url, data=data, format="json")
    assert response.status_code == expected_status_code
    if expected_error:
        assert response.json() == expected_error
    else:
        if slug:
            expected_slug = slug
        else:
            expected_slug = response.data["slug"]
        with override_settings(FRONT_END_URL='http://testserver/'):
            expected_path = get_fully_qualified_url('social:complete', kwargs={'backend': expected_slug})
            assert response.json()['configuration']['CALLBACK_URL'] == expected_path


@mock.patch("rest_framework.views.APIView.authentication_classes", [SessionAuthentication])
@mock.patch("ansible_base.authentication.authenticator_plugins.google_oauth2.AuthenticatorPlugin.authenticate", return_value=None)
def test_oidc_auth_failed(authenticate, unauthenticated_api_client, google_oauth2_authenticator):
    """
    Test that a failed Google OAuth2 authentication returns a 401 on the /me endpoint.
    """
    client = unauthenticated_api_client
    client.login()

    url = get_relative_url(authenticated_test_page)
    response = client.get(url)
    assert response.status_code == 401
