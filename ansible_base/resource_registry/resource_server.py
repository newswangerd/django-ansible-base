from datetime import datetime, timedelta
from typing import TypedDict

import jwt
from django.conf import settings

from ansible_base.resource_registry.models import service_id


class ResourceServerConfig(TypedDict):
    URL: str
    SECRET_KEY: str
    VALIDATE_HTTPS: bool
    JWT_ALGORITHM: str


def get_resource_server_config() -> ResourceServerConfig:
    defaults = {"JWT_ALGORITHM": "HS256", "VALIDATE_HTTPS": True}
    return ResourceServerConfig(**{**defaults, **settings.RESOURCE_SERVER})


def get_service_token(user_id, expiration=60, **kwargs):
    config = get_resource_server_config()
    payload = {
        "iss": str(service_id()),
        "sub": str(user_id),
        **kwargs,
    }

    if expiration is not None:
        payload["exp"] = datetime.now() + timedelta(seconds=expiration)

    return jwt.encode(payload, config["SECRET_KEY"], config["JWT_ALGORITHM"])
