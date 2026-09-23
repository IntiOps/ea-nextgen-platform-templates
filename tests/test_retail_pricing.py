from decimal import Decimal
import pytest
import retail_pricing as pricing


def meter(**changes):
    value=dict(productName='Azure App Service Basic Plan - Linux',type='Consumption',unitOfMeasure='1 Hour',
               armRegionName='westeurope',skuName='B1',currencyCode='USD',tierMinimumUnits=0,
               isPrimaryMeterRegion=True,meterId='linux-b1',retailPrice=0.018)
    value.update(changes)
    return value


def test_linux_price_excludes_windows_and_counts_instances(monkeypatch):
    monkeypatch.setattr(pricing,'_json',lambda _: {'Items':[meter(),meter(productName='Windows')]})
    rate=pricing.azure_app_service('westeurope','B1',instances=2)
    assert rate.unit_price == Decimal('0.018')
    assert rate.quantity == 2
    assert rate.billing == 'provisioned'


@pytest.mark.parametrize('items',[[],[meter(),meter()]])
def test_missing_ambiguous_prices_are_not_zero(monkeypatch,items):
    monkeypatch.setattr(pricing,'_json',lambda _: {'Items':items})
    with pytest.raises(pricing.PriceUnavailable): pricing.azure_app_service('westeurope','B1')


def test_price_pagination_rejects_external_hosts(monkeypatch):
    monkeypatch.setattr(pricing,'_json',lambda _: {'Items':[meter()],'NextPageLink':'https://example.org/next'})
    with pytest.raises(pricing.PriceUnavailable,match='pagination host'):
        pricing.azure_app_service('westeurope','B1')


def test_aws_uses_explicit_consumption(monkeypatch):
    data={'products':{},'terms':{'OnDemand':{}}}
    for name,unit,price in [('Lambda-Requests','Requests','0.0000002'),('Lambda-GB-Second','Lambda-GB-Second','0.0000166667')]:
        data['products'][name]={'attributes':{'regionCode':'eu-west-1','usagetype':'EU-'+name,'group':'AWS-Lambda-Requests' if name=='Lambda-Requests' else 'AWS-Lambda-Duration'}}
        data['terms']['OnDemand'][name]={'offer':{'priceDimensions':{'rate':{'beginRange':'0','unit':unit,'pricePerUnit':{'USD':price}}}}}
    monkeypatch.setattr(pricing,'_json',lambda _:data)
    rates=pricing.aws_lambda('eu-west-1',requests=Decimal('1000'),gb_seconds=Decimal('50'))
    assert [rate.usage_units for rate in rates] == [1000,50]
    assert all(rate.billing == 'usage' for rate in rates)


def test_price_requests_reject_credentials_ports_and_untrusted_hosts():
    for url in ['https://example.org/prices','https://prices.azure.com:444/prices','https://user:password@prices.azure.com/prices']:
        with pytest.raises(pricing.PriceUnavailable,match='host'):
            pricing._json(url)


def test_price_redirects_fail_before_following():
    with pytest.raises(pricing.PriceUnavailable,match='redirects'):
        pricing.NoRedirect().redirect_request(None,None,302,'redirect',{},'https://example.org')
