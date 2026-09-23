from datetime import datetime, timezone
from decimal import Decimal
import pytest
from pydantic import ValidationError
from runtime_policy import DeploymentIntent, ResourceRate, estimate

NOW = datetime(2026, 9, 21, tzinfo=timezone.utc)


def intent(**overrides):
    data = dict(cloud='azure',ecosystem='app-service',iac='bicep',cicd='azure-pipelines',purpose='development',
        region='westeurope',starts_at=NOW,retention_days=7,availability='single',sku='B1',budget_limit='100',
        working_hours={'timezone':'Europe/Madrid','weekdays':[0,1,2,3,4],'start':'09:00','end':'18:00'})
    data.update(overrides)
    return DeploymentIntent(**data)


def rate(**overrides):
    data = dict(resource='app_service_plan',meter='B1',region='westeurope',currency='USD',unit='hour',
        unit_price='0.1',quantity=1,billing='provisioned',source='https://prices.azure.com/api/retail/prices',retrieved_at=NOW)
    data.update(overrides)
    return ResourceRate(**data)


def test_app_service_working_hours_do_not_remove_plan_charges():
    result=estimate(intent(),[rate()],ends_at=datetime(2026,9,28,tzinfo=timezone.utc),now=NOW)
    assert Decimal(result['provisioned_hours']) == 168
    assert Decimal(result['active_hours']) == 45
    assert Decimal(result['estimated_total']) == Decimal('16.8')
    with pytest.raises(ValueError,match='stopped-app'):
        estimate(intent(),[rate(billing='active')],ends_at=datetime(2026,9,28,tzinfo=timezone.utc),now=NOW)


def test_production_requires_ha_and_forbids_expiry_or_schedules():
    with pytest.raises(ValidationError): intent(purpose='production')
    with pytest.raises(ValidationError): intent(purpose='production',working_hours=None)
    valid=intent(purpose='production',working_hours=None,availability='zone-redundant',instances=2,sku='P1v3')
    assert valid.purpose == 'production'


def test_budget_missing_prices_and_stale_prices_block_approval():
    result=estimate(intent(budget_limit='1'),[rate()],ends_at=datetime(2026,9,28,tzinfo=timezone.utc),now=NOW,missing_resources=['logs'])
    assert result['can_request_apply_approval'] is False
    assert result['blockers'] == ['budget_exceeded','missing_resource:logs']
    result=estimate(intent(),[],ends_at=datetime(2026,9,22,tzinfo=timezone.utc),now=NOW)
    assert result['blockers'] == ['no_pricing_evidence']
    result=estimate(intent(),[rate()],ends_at=datetime(2026,9,28,tzinfo=timezone.utc),now=datetime(2026,9,23,tzinfo=timezone.utc))
    assert 'price_not_current:app_service_plan' in result['blockers']


def test_dst_and_overnight_windows_use_real_elapsed_time():
    data=intent(starts_at=datetime(2026,10,25,tzinfo=timezone.utc),working_hours={'timezone':'Europe/Madrid','weekdays':[6],'start':'01:00','end':'04:00'})
    result=estimate(data,[rate()],ends_at=datetime(2026,10,25,4,tzinfo=timezone.utc),now=NOW)
    assert Decimal(result['active_hours']) == 3
    overnight=intent(working_hours={'timezone':'UTC','weekdays':[0],'start':'22:00','end':'02:00'})
    assert overnight.working_hours.active(datetime(2026,9,22,1,tzinfo=timezone.utc))
    assert not overnight.working_hours.active(datetime(2026,9,22,3,tzinfo=timezone.utc))


def test_usage_and_cloud_choice_must_be_explicit():
    with pytest.raises(ValidationError): intent(iac='cdk-python')
    with pytest.raises(ValidationError): rate(unit='request',billing='usage')
    with pytest.raises(ValidationError): intent(expiry_action='destroy')


def test_advisory_expiry_does_not_end_billing():
    end=datetime(2026,9,28,tzinfo=timezone.utc)
    expiry=datetime(2026,9,22,tzinfo=timezone.utc)
    advisory=estimate(intent(expires_at=expiry),[rate()],ends_at=end,now=NOW)
    governed=estimate(intent(expires_at=expiry,expiry_action='destroy'),[rate()],ends_at=end,now=NOW)
    assert Decimal(advisory['provisioned_hours']) == 168
    assert Decimal(governed['provisioned_hours']) == 24


def test_production_price_must_include_all_instances():
    deployment=intent(purpose='production',working_hours=None,availability='zone-redundant',instances=2,sku='P1v3')
    result=estimate(deployment,[rate()],ends_at=datetime(2026,9,22,tzinfo=timezone.utc),now=NOW)
    assert 'instance_quantity_mismatch:app_service_plan' in result['blockers']
    with pytest.raises(ValidationError):
        intent(availability='zone-redundant',instances=2,sku='P1')
