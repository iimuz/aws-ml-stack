"""AWS CDKのStack outputを管理するクラス."""

import boto3
from mypy_boto3_cloudformation.type_defs import OutputTypeDef
from pydantic import BaseModel, Field

from src.awscdk.stack_config import StackConfig
from src.awscdk.stack_output_keys import StackOutputKey


class StackOutput(BaseModel):
    """Stack output."""

    security_group_id: str | None = Field(default=None)

    @staticmethod
    def load_from_stack(config: StackConfig, profile: str) -> "StackOutput":
        """Stackからoutputを取得する."""
        session = boto3.Session(profile_name=profile)
        cloudformation = session.client("cloudformation")
        response = cloudformation.describe_stacks(StackName=config.stack_name)
        stack = response["Stacks"][0]
        if stack["StackStatus"] != "CREATE_COMPLETE":
            message = f"Stack status is not CREATE_COMPLETE: {stack['StackStatus']}"
            raise ValueError(message)
        outputs: list[OutputTypeDef] = stack.get("Outputs", [])

        return StackOutput(
            security_group_id=_get_first_value_from(
                outputs, StackOutputKey.security_group_id.value
            )
        )


def _get_first_value_from(outputs: list[OutputTypeDef], key: str) -> str | None:
    """Stack outputから指定したkeyの最初の値を取得する."""
    return next(
        (
            output.get("OutputValue", "")
            for output in outputs
            if output.get("OutputKey", "") == key
        ),
        None,
    )
