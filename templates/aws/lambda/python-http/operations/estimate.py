"""Read-only retail estimate. Never authenticates to a cloud or executes IaC."""
import argparse
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
from runtime_policy import DeploymentIntent, estimate
from retail_pricing import azure_app_service, aws_lambda


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--intent',type=Path,required=True)
    parser.add_argument('--ends-at',required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--requests',type=Decimal)
    parser.add_argument('--gb-seconds',type=Decimal)
    args=parser.parse_args()
    intent=DeploymentIntent.model_validate_json(args.intent.read_text())
    end=datetime.fromisoformat(args.ends_at.replace('Z','+00:00'))
    if intent.ecosystem=='app-service':
        rates=[azure_app_service(intent.region,intent.sku,instances=intent.instances,currency=intent.currency)]
        missing=['network_transfer']
        if intent.iac=='terraform': missing.append('shared_state_storage')
    elif intent.ecosystem=='lambda':
        if intent.currency!='USD': parser.error('AWS public price files are USD; supply an explicit exchange-rate policy before using another currency')
        if args.requests is None or args.gb_seconds is None: parser.error('Lambda requires --requests and --gb-seconds for this exact estimate period')
        rates=aws_lambda(intent.region,requests=args.requests,gb_seconds=args.gb_seconds)
        missing=['cloudwatch_logs','network_transfer']
        if intent.iac=='terraform': missing.append('shared_state_storage')
    else:
        parser.error('No verified price adapter for this ecosystem')
    result=estimate(intent,rates,ends_at=end,now=datetime.now(timezone.utc),missing_resources=missing)
    result['intent_sha256']=hashlib.sha256(intent.model_dump_json().encode()).hexdigest()
    result['coverage']='partial: compute only; not an apply authorization'
    result['lifecycle_execution']='not configured; time-bound result assumes successful approved cleanup'
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(f"Compute estimate: {result['estimated_total']} {result['currency']}; full-cost coverage pending")
    return 2 if result['blockers'] else 0


if __name__=='__main__':
    raise SystemExit(main())
