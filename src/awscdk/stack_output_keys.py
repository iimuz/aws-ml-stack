"""AWS CDKのStack output設定."""

from enum import Enum


class StackOutputKey(Enum):
    """Stack output key."""

    security_group_id = "SecurityGroupId"
