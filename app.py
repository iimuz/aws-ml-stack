"""AWS CDK."""

import aws_cdk as cdk

from src.awscdk.stack_config import StackConfig
from src.awscdk.stacks import MLStack

app = cdk.App()
region = app.node.try_get_context("aws:cdk:region")
account = app.node.try_get_context("aws:cdk:account")
env = cdk.Environment(region=region, account=account)
config = StackConfig.create_dev()
MLStack(scope=app, stack_id=config.stack_name, env=env, stack_config=config)

app.synth()
