"""Unauthenticated retail evidence. Ambiguous or missing meters fail instead of becoming zero."""
from datetime import datetime, timezone
from decimal import Decimal
import json
import re
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, build_opener
from runtime_policy import ResourceRate

MAX_RESPONSE = 32 * 1024 * 1024


class PriceUnavailable(ValueError):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise PriceUnavailable('Pricing redirects are not accepted')


def _json(url: str):
    parsed = urlsplit(url)
    if parsed.scheme != 'https' or parsed.hostname not in {'prices.azure.com', 'pricing.us-east-1.amazonaws.com'} or parsed.port is not None or parsed.username or parsed.password:
        raise PriceUnavailable('Unsupported pricing host')
    with build_opener(NoRedirect()).open(url, timeout=30) as response:
        if urlsplit(response.url).hostname != urlsplit(url).hostname:
            raise PriceUnavailable('Unexpected pricing response host')
        content = response.read(MAX_RESPONSE + 1)
    if len(content) > MAX_RESPONSE:
        raise PriceUnavailable('Price response exceeds limit')
    return json.loads(content)


def azure_app_service(region: str, sku: str, *, instances: int = 1, currency: str = 'USD') -> ResourceRate:
    if not re.fullmatch(r'[a-z0-9]{3,40}', region) or not re.fullmatch(r'[A-Za-z0-9]{2,20}', sku) or currency not in {'USD','EUR'}:
        raise PriceUnavailable('Unsupported pricing context')
    query = urlencode({'currencyCode': currency, '$filter':
        f"serviceName eq 'Azure App Service' and armRegionName eq '{region}' and skuName eq '{sku}' and priceType eq 'Consumption'"})
    url = 'https://prices.azure.com/api/retail/prices?' + query
    matches = []
    next_url = url
    for _ in range(10):
        data = _json(next_url)
        matches.extend(item for item in data.get('Items', []) if
            'Linux' in item.get('productName','') and item.get('type') == 'Consumption' and
            item.get('unitOfMeasure') == '1 Hour' and item.get('armRegionName') == region and
            item.get('skuName') == sku and item.get('currencyCode') == currency and
            item.get('tierMinimumUnits', 0) == 0 and item.get('isPrimaryMeterRegion', True))
        next_url = data.get('NextPageLink')
        if not next_url:
            break
        if urlsplit(next_url).hostname != 'prices.azure.com' or urlsplit(next_url).scheme != 'https':
            raise PriceUnavailable('Unexpected pricing pagination host')
    else:
        raise PriceUnavailable('Pricing pagination limit exceeded')
    if len(matches) != 1:
        raise PriceUnavailable('App Service Linux meter is missing or ambiguous')
    item = matches[0]
    return ResourceRate(resource='app_service_plan', meter=item['meterId'], region=region,currency=currency,
        unit='hour',unit_price=Decimal(str(item['retailPrice'])),quantity=instances,billing='provisioned',
        source=url,retrieved_at=datetime.now(timezone.utc))


def aws_lambda(region: str, *, requests: Decimal, gb_seconds: Decimal) -> list[ResourceRate]:
    if not re.fullmatch(r'[a-z]{2}(?:-[a-z]+)+-\d', region):
        raise PriceUnavailable('Invalid AWS region')
    url = f'https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AWSLambda/current/{region}/index.json'
    data = _json(url)
    rates = []
    for group, units, unit, resource in [
        ('AWS-Lambda-Requests', requests, 'request', 'lambda_requests'),
        ('AWS-Lambda-Duration', gb_seconds, 'gb-second', 'lambda_compute'),
    ]:
        candidates=[]
        for sku, product in data.get('products', {}).items():
            attributes=product.get('attributes',{})
            if attributes.get('regionCode') != region or attributes.get('group') != group:
                continue
            for offer in data.get('terms',{}).get('OnDemand',{}).get(sku,{}).values():
                for dimension in offer.get('priceDimensions',{}).values():
                    if dimension.get('beginRange') == '0' and 'USD' in dimension.get('pricePerUnit',{}):
                        candidates.append((sku,dimension))
        if len(candidates) != 1:
            raise PriceUnavailable(f'Missing or ambiguous AWS meter: {group}')
        sku, dimension = candidates[0]
        rates.append(ResourceRate(resource=resource,meter=sku,region=region,currency='USD',unit=unit,
            unit_price=Decimal(dimension['pricePerUnit']['USD']),quantity=1,billing='usage',usage_units=units,
            source=url,retrieved_at=datetime.now(timezone.utc)))
    return rates
