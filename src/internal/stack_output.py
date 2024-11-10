"""AWS CDKのStack outputを管理するクラス."""

from boto3 import Session
from mypy_boto3_cloudformation.type_defs import OutputTypeDef
from pydantic import BaseModel, ConfigDict

from src.awscdk.stack_config import StackConfig
from src.awscdk.stack_output_keys import StackOutputKey


class StackOutput(BaseModel):
    """Stack output."""

    security_group_id: str

    model_config = ConfigDict(frozen=True)

    @staticmethod
    def load_from_stack(config: StackConfig, session: Session) -> "StackOutput":
        """Stackからoutputを取得する."""
        cloudformation = session.client("cloudformation")
        response = cloudformation.describe_stacks(StackName=config.stack_name)
        stack = response["Stacks"][0]
        if stack["StackStatus"] not in ["CREATE_COMPLETE", "UPDATE_COMPLETE"]:
            message = f"Stack status is not CREATE_COMPLETE: {stack['StackStatus']}"
            raise ValueError(message)
        outputs: list[OutputTypeDef] = stack.get("Outputs", [])

        return StackOutput(
            security_group_id=_get_first_value_from(
                outputs, StackOutputKey.security_group_id.value
            )
        )


def _get_first_value_from(outputs: list[OutputTypeDef], key: str) -> str:
    """Stack outputから指定したkeyの最初の値を取得する."""
    value = next(
        (
            output.get("OutputValue", "")
            for output in outputs
            if output.get("OutputKey", "") == key
        ),
        None,
    )
    if value is None:
        message = f"Output key not found: {key}"
        raise ValueError(message)

    return value
