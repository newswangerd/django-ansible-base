from functools import partial
from unittest import mock

import pytest
from crum import impersonate
from django.contrib.auth.models import User as DjangoUser
from django.test.utils import override_settings

from ansible_base.lib.utils import models
from ansible_base.lib.utils.encryption import ENCRYPTED_STRING
from test_app import models as test_app_models


def test_get_all_field_names(animal):
    """
    get_all_field_names should return all field names for a model.
    """
    field_names = models.get_all_field_names(animal)
    assert 'owner' in field_names
    assert 'kind' in field_names
    assert 'age' in field_names


def test_get_all_field_names_concrete_only(user):
    """
    get_all_field_names with concrete_only=True should return only concrete fields.
    """
    field_names = models.get_all_field_names(user)
    assert 'username' in field_names
    assert 'first_name' in field_names
    assert 'animal_set' not in field_names


@pytest.mark.xfail
def test_get_all_field_names_reverse_accessors(user):
    """
    get_all_field_names should include proper reverse field accessor names.
    """
    field_names = models.get_all_field_names(user)
    assert 'animal_set' in field_names


def test_get_type_for_model():
    dummy_model = mock.MagicMock()
    dummy_model._meta.concrete_model._meta.object_name = 'SnakeCaseString'

    assert models.get_type_for_model(dummy_model) == 'snake_case_string'


@pytest.mark.django_db
def test_system_user_unset():
    with override_settings(SYSTEM_USERNAME=None):
        assert models.get_system_user() is None


@pytest.mark.django_db
def test_system_user_set(system_user):
    assert models.get_system_user() == system_user


@pytest.mark.django_db
def test_system_user_set_but_no_user(expected_log):
    system_username = 'LittleTimmy'
    with override_settings(SYSTEM_USERNAME=system_username):
        expected_log = partial(expected_log, "ansible_base.lib.utils.models.logger")
        with expected_log('error', f'is set to {system_username} but no user with that username exists'):
            assert models.get_system_user() is not None


@pytest.mark.django_db
def test_user_or_system_user(system_user, user):
    with impersonate(user):
        assert models.current_user_or_system_user() == user

    assert models.current_user_or_system_user() == system_user


@pytest.mark.parametrize(
    'model,field_name,expected',
    [
        (test_app_models.User, 'password', True),
        (DjangoUser, 'password', True),
        (test_app_models.EncryptionModel, 'testing1', True),
        (test_app_models.EncryptionModel, 'testing2', True),
        (test_app_models.EncryptionModel, 'name', False),
        (test_app_models.City, 'country', True),
        (None, 'foo', False),
    ],
)
def test_is_encrypted_field(model, field_name, expected):
    assert models.is_encrypted_field(model, field_name) == expected


def test_diff_both_none():
    """
    Diffing two None means no fields are added, removed, or changed.
    """
    empty_model_diff = models.ModelDiff(added_fields={}, removed_fields={}, changed_fields={})
    delta = models.diff(None, None)

    assert delta == empty_model_diff
    assert not delta.has_changes
    assert delta.dict() == {'added_fields': {}, 'removed_fields': {}, 'changed_fields': {}}


@pytest.mark.parametrize(
    'require_type_match',
    [True, False],
)
def test_diff_old_none_means_all_fields_are_new(system_user, multiple_fields_model, require_type_match):
    """
    Diffing None and a model means all fields are added.
    require_type_match should not affect the result.
    """
    delta = models.diff(None, multiple_fields_model, require_type_match=require_type_match, json_safe=False)
    field_names = models.get_all_field_names(multiple_fields_model, concrete_only=True, include_attnames=False)
    assert len(delta.added_fields) == len(field_names)
    assert delta.removed_fields == {}
    assert delta.changed_fields == {}
    for field in field_names:
        assert delta.added_fields[field] == getattr(multiple_fields_model, field)


@pytest.mark.parametrize(
    'require_type_match',
    [True, False],
)
def test_diff_new_none_means_all_fields_are_old(system_user, multiple_fields_model, require_type_match):
    """
    Diffing a model and None means all fields are removed.
    require_type_match should not affect the result.
    """
    delta = models.diff(multiple_fields_model, None, require_type_match=require_type_match, json_safe=False)
    field_names = models.get_all_field_names(multiple_fields_model, concrete_only=True, include_attnames=False)
    assert len(delta.removed_fields) == len(field_names)
    assert delta.added_fields == {}
    assert delta.changed_fields == {}
    for field in field_names:
        assert delta.removed_fields[field] == getattr(multiple_fields_model, field)


def test_diff_require_type_match_true(system_user, multiple_fields_model):
    """
    Diffing two models of different types should raise a TypeError
    if require_type_match is True.
    """
    # Test with *implicit* require_type_match=True
    with pytest.raises(TypeError) as excinfo:
        models.diff(multiple_fields_model, system_user)
    assert 'old and new must be of the same type' in str(excinfo.value)

    # Test with *explicit* require_type_match=True
    with pytest.raises(TypeError) as excinfo:
        models.diff(multiple_fields_model, system_user, require_type_match=True)
    assert 'old and new must be of the same type' in str(excinfo.value)


def test_diff_require_type_match_false(system_user, user, multiple_fields_model):
    """
    Diffing two models of different types should not raise a TypeError
    if require_type_match is False.
    """
    delta = models.diff(multiple_fields_model, system_user, require_type_match=False)
    assert 'last_name' in delta.added_fields
    assert delta.added_fields['last_name'] == system_user.last_name
    assert 'last_name' not in delta.removed_fields
    assert 'last_name' not in delta.changed_fields

    delta = models.diff(system_user, multiple_fields_model, require_type_match=False)
    assert 'last_name' in delta.removed_fields
    assert delta.removed_fields['last_name'] == system_user.last_name
    assert 'last_name' not in delta.added_fields
    assert 'last_name' not in delta.changed_fields


@pytest.mark.parametrize(
    'old,new',
    [
        (object(), 'user'),
        ('user', object()),
        (object(), object()),
        (None, object()),
        (object(), None),
    ],
    ids=[
        'old is not a model',
        'new is not a model',
        'both arguments are not models',
        'old is None, new is not a model',
        'old is not a model, new is None',
    ],
)
def test_diff_not_a_model_raises(request, old, new):
    """
    Diffing a non-Model instance should raise a TypeError.
    """
    if old == 'user':
        old = request.getfixturevalue('user')
    if new == 'user':
        new = request.getfixturevalue('user')

    with pytest.raises(TypeError) as excinfo:
        models.diff(old, new)

    assert 'old and new must be a Model instance' in str(excinfo.value)


def test_diff(system_user, user):
    """
    Diffing two models should return the fields that were added, removed, or changed.

    This is the normal case where the old and new models are of the same type.
    """
    delta = models.diff(system_user, user)
    assert 'username' in delta.changed_fields
    assert delta.changed_fields['username'] == (system_user.username, user.username)
    assert 'email' not in delta.changed_fields
    assert delta.added_fields == {}
    assert delta.removed_fields == {}


def test_diff_exclude_fields(system_user, user):
    """
    Excluding fields from the diff should not include them in the result.
    """
    user.first_name = 'newfirstname'
    user.save()
    delta = models.diff(system_user, user, exclude_fields=['username'])
    assert 'username' not in delta.changed_fields
    assert 'first_name' in delta.changed_fields
    assert delta.changed_fields['first_name'] == (system_user.first_name, user.first_name)


def test_diff_limit_fields(system_user, user):
    """
    Limiting the diff to only certain fields should only include those fields in the result.
    """
    user.first_name = 'newfirstname'
    user.save()
    delta = models.diff(system_user, user, limit_fields=['username'])
    assert 'username' in delta.changed_fields
    assert len(delta.changed_fields) == 1
    assert delta.added_fields == {}
    assert delta.removed_fields == {}

    delta = models.diff(None, user, limit_fields=['username'])
    assert 'username' in delta.added_fields
    assert len(delta.added_fields) == 1
    assert delta.removed_fields == {}
    assert delta.changed_fields == {}


def test_diff_with_fk(system_user, user, multiple_fields_model_1, multiple_fields_model_2):
    """
    Diffing with foreign key works, and with json_safe we get the pk of the related model.
    """
    multiple_fields_model_2.created_by = user
    multiple_fields_model_2.save()

    delta = models.diff(multiple_fields_model_1, multiple_fields_model_2, json_safe=False)
    assert delta.changed_fields['created_by'] == (multiple_fields_model_1.created_by, multiple_fields_model_2.created_by)
    # We don't include the "attnames"
    assert 'created_by_id' not in delta.changed_fields

    delta = models.diff(multiple_fields_model_1, multiple_fields_model_2, json_safe=True)
    assert delta.changed_fields['created_by'] == (multiple_fields_model_1.created_by.username, multiple_fields_model_2.created_by.username)
    # We don't include the "attnames"
    assert 'created_by_id' not in delta.changed_fields


@pytest.mark.django_db
def test_diff_sanitizes_encrypted_fields_changed(disable_activity_stream):
    """
    Encrypted fields should be sanitized in the diff when changed.
    """
    instance1 = test_app_models.EncryptionModel.objects.create(name='oldname', testing1='oldtesting1', testing2='oldtesting2')
    instance2 = test_app_models.EncryptionModel.objects.get(pk=instance1.pk)
    instance2.name = 'newname'
    instance2.testing1 = 'newtesting1'

    delta = models.diff(instance1, instance2)
    assert delta.changed_fields['name'] == (instance1.name, instance2.name)
    assert delta.changed_fields['testing1'] == (ENCRYPTED_STRING, ENCRYPTED_STRING)


@pytest.mark.django_db
def test_diff_sanitizes_encrypted_fields_added(disable_activity_stream):
    """
    Encrypted fields should be sanitized in the diff when added.
    """
    logentry = test_app_models.ImmutableLogEntry.objects.create(message='oldmessage')
    encryptionmodel = test_app_models.EncryptionModel.objects.create(name='oldname', testing1='oldtesting1', testing2='oldtesting2')

    delta = models.diff(logentry, encryptionmodel, require_type_match=False)
    assert delta.added_fields['name'] == 'oldname'
    assert delta.added_fields['testing1'] == ENCRYPTED_STRING
    assert delta.added_fields['testing2'] == ENCRYPTED_STRING
    assert 'message' not in delta.added_fields


@pytest.mark.django_db
def test_diff_sanitizes_encrypted_fields_removed(disable_activity_stream):
    """
    Encrypted fields should be sanitized in the diff when removed.
    """
    logentry = test_app_models.ImmutableLogEntry.objects.create(message='oldmessage')
    encryptionmodel = test_app_models.EncryptionModel.objects.create(name='oldname', testing1='oldtesting1', testing2='oldtesting2')

    delta = models.diff(encryptionmodel, logentry, require_type_match=False)
    assert delta.removed_fields['name'] == 'oldname'
    assert delta.removed_fields['testing1'] == ENCRYPTED_STRING
    assert delta.removed_fields['testing2'] == ENCRYPTED_STRING
    assert 'message' not in delta.removed_fields


@pytest.mark.parametrize(
    "username,expected_value",
    [
        (None, False),
        ("system", True),
        ("random", False),
        ("organization", False),
    ],
)
def test_is_system_user_system_user_setting_set(username, expected_value, system_user, random_user, organization):
    if username is None:
        user = None
    elif username == 'system':
        user = system_user
    elif username == 'organization':
        user = organization
    elif username == 'random':
        user = random_user
    else:
        assert False, f"This test doesn't know what to do with type {username}"

    assert models.is_system_user(user) == expected_value


@pytest.mark.parametrize(
    "username",
    [
        None,
        "system",
        "random",
    ],
)
def test_is_system_user_no_system_user_setting(username, system_user, random_user):
    # If the system username is not set, no user should ever match it
    if username is None:
        user = None
    elif username == "system":
        user = system_user
    else:
        user = random_user

    with override_settings(SYSTEM_USERNAME=None):
        assert not models.is_system_user(user)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "resource_registry_in_installed_apps",
    [
        True,
        False,
    ],
)
def test_get_system_user_create_raises_exception(resource_registry_in_installed_apps):
    from django.conf import settings

    from ansible_base.resource_registry.models import ResourceType

    rr_app_name = 'ansible_base.resource_registry'
    installed_apps = settings.INSTALLED_APPS.copy()
    if resource_registry_in_installed_apps and rr_app_name not in settings.INSTALLED_APPS:
        installed_apps.append(rr_app_name)
    elif not resource_registry_in_installed_apps and rr_app_name in settings.INSTALLED_APPS:
        installed_apps.remove(rr_app_name)

    with override_settings(SYSTEM_USERNAME='not_system', INSTALLED_APPS=installed_apps):
        with mock.patch('ansible_base.lib.utils.models.create_system_user', side_effect=ResourceType.DoesNotExist("Failing on purpose")):
            try:
                assert models.get_system_user() is None
            except ResourceType.DoesNotExist:
                if resource_registry_in_installed_apps:
                    assert False, "We should not handled the exception since resource_registry is in the installed apps"
