"""AWS CDK."""

import aws_cdk as cdk

from src.stacks import MyProjectStack

# cdk.context.jsonに記載されたaws:cdk:regionの値を取得する

app = cdk.App()
region = app.node.try_get_context("aws:cdk:region")
account = app.node.try_get_context("aws:cdk:account")
env = cdk.Environment(region=region, account=account)
MyProjectStack(app, "MyProjectStack", env=env)

app.synth()
