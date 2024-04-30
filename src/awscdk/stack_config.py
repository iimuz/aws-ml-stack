"""AWS CDKの全体で利用する設定値."""

from pydantic import BaseModel, Field


class StackConfig(BaseModel):
    """AWS CDKの全体で利用する設定値."""

    resource_prefix: str = Field(default="")

    stack_name: str = Field(default="")
    vpc_name: str = Field(default="")
    ssh_security_group_name: str = Field(default="")

    @staticmethod
    def create_dev() -> "StackConfig":
        """開発環境用の設定値を作成する."""
        prefix = "ml-dev"

        return StackConfig(
            resource_prefix=prefix,
            stack_name=prefix,
            vpc_name=f"{prefix}-vpc",
            ssh_security_group_name=f"{prefix}-ssh-sg",
        )
