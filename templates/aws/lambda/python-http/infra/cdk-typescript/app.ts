import * as cdk from 'aws-cdk-lib';
import { aws_lambda as functions, aws_logs as logs } from 'aws-cdk-lib';
import * as path from 'node:path';
const required = (name: string): string => { const value=process.env[name]; if (!value) throw new Error(`Missing ${name}`); return value; };
const account=required('EA_ACCOUNT_ID'), region=required('EA_REGION'), instance=required('EA_INSTANCE');
const purpose=required('EA_PURPOSE'), revision=required('EA_REVISION'), retention=Number(required('EA_RETENTION_DAYS'));
if (!/^[0-9]{12}$/.test(account) || !/^[a-z][a-z0-9-]{2,23}$/.test(instance)) throw new Error('Invalid scope');
if (!['poc','development','staging','production'].includes(purpose) || !/^[0-9a-f]{40}$/.test(revision)) throw new Error('Invalid purpose or revision');
if (![1,3,5,7,14,30,60,90,120,150,180,365].includes(retention)) throw new Error('Invalid retention');
const app=new cdk.App();
const stack=new cdk.Stack(app,`ea-${instance}`,{env:{account,region}});
for (const [key,value] of Object.entries({managed_by:'ea-nextgen-template',instance,purpose,owner_id:required('EA_OWNER_ID')})) cdk.Tags.of(stack).add(key,value);
const logGroup=new logs.LogGroup(stack,'Logs',{retention,removalPolicy:purpose==='production'?cdk.RemovalPolicy.RETAIN:cdk.RemovalPolicy.DESTROY});
const fn=new functions.Function(stack,'Application',{runtime:functions.Runtime.PYTHON_3_12,handler:'handler.handler',
  code:functions.Code.fromAsset(path.resolve(__dirname,'../../../app')),logGroup,
  memorySize:purpose==='production'?512:256,timeout:cdk.Duration.seconds(10),environment:{SOURCE_REVISION:revision}});
new cdk.CfnOutput(stack,'FunctionName',{value:fn.functionName});
app.synth();
