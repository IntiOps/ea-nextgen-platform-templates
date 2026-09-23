import os
import re
from pathlib import Path
import aws_cdk as cdk
from aws_cdk import aws_lambda as functions, aws_logs as logs

app = cdk.App()
account = os.environ["EA_ACCOUNT_ID"]
region = os.environ["EA_REGION"]
instance = os.environ["EA_INSTANCE"]
purpose = os.environ["EA_PURPOSE"]
revision = os.environ["EA_REVISION"]
retention = int(os.environ["EA_RETENTION_DAYS"])
if not re.fullmatch(r"[0-9]{12}", account) or not re.fullmatch(r"[a-z][a-z0-9-]{2,23}",instance):
    raise ValueError("Invalid deployment scope")
if purpose not in {"poc","development","staging","production"} or not re.fullmatch(r"[0-9a-f]{40}",revision):
    raise ValueError("Invalid purpose or source revision")
if retention not in {1,3,5,7,14,30,60,90,120,150,180,365}:
    raise ValueError("Unsupported retention")
stack = cdk.Stack(app, "ea-"+instance, env=cdk.Environment(account=account,region=region))
for key,value in {"managed_by":"ea-nextgen-template","instance":instance,"purpose":purpose,"owner_id":os.environ["EA_OWNER_ID"]}.items():
    cdk.Tags.of(stack).add(key,value)
log_resource = logs.CfnLogGroup(stack,"Logs",retention_in_days=retention)
log_resource.apply_removal_policy(cdk.RemovalPolicy.RETAIN if purpose=="production" else cdk.RemovalPolicy.DESTROY)
log_group = logs.LogGroup.from_log_group_name(stack,"LogReference",log_resource.ref)
function = functions.Function(stack,"Application",runtime=functions.Runtime.PYTHON_3_12,handler="handler.handler",
    code=functions.Code.from_asset(str(Path(__file__).resolve().parents[2]/"app")),
    log_group=log_group,memory_size=512 if purpose=="production" else 256,timeout=cdk.Duration.seconds(10),
    environment={"SOURCE_REVISION":revision})
cdk.CfnOutput(stack,"FunctionName",value=function.function_name)
app.synth()
