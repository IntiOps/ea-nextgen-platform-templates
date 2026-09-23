"""Typed deployment intent and time-aware retail cost evidence, independent of IaC/CI."""
from datetime import datetime, timedelta, timezone
import re
from decimal import Decimal
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, field_validator, model_validator
from pydantic import BaseModel, ConfigDict

class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class WorkingHours(Contract):
    timezone: str
    weekdays: list[int] = Field(min_length=1, max_length=7)
    start: str = Field(pattern=r'^(?:[01]\d|2[0-3]):[0-5]\d$')
    end: str = Field(pattern=r'^(?:[01]\d|2[0-3]):[0-5]\d$')

    @field_validator('timezone')
    @classmethod
    def known_zone(cls, value):
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError('Use an IANA timezone') from exc
        return value

    @field_validator('weekdays')
    @classmethod
    def days(cls, values):
        if len(set(values)) != len(values) or any(day < 0 or day > 6 for day in values):
            raise ValueError('Weekdays must be distinct integers from 0 (Monday) to 6')
        return values

    @model_validator(mode='after')
    def nonempty(self):
        if self.start == self.end:
            raise ValueError('Equal schedule boundaries are ambiguous; omit the schedule for 24/7')
        return self

    def active(self, instant: datetime) -> bool:
        local = instant.astimezone(ZoneInfo(self.timezone))
        clock = local.strftime('%H:%M')
        if self.start < self.end:
            return local.weekday() in self.weekdays and self.start <= clock < self.end
        # Overnight windows belong to the day on which the window starts.
        return ((local.weekday() in self.weekdays and clock >= self.start) or
                ((local.weekday() - 1) % 7 in self.weekdays and clock < self.end))


class DeploymentIntent(Contract):
    cloud: Literal['azure', 'aws']
    ecosystem: Literal['app-service', 'lambda', 'kubernetes']
    iac: Literal['terraform', 'bicep', 'cdk-python', 'cdk-typescript']
    cicd: Literal['github-actions', 'azure-pipelines']
    purpose: Literal['poc', 'development', 'staging', 'production']
    region: str = Field(min_length=1, max_length=64)
    starts_at: datetime
    expires_at: datetime | None = None
    working_hours: WorkingHours | None = None
    expiry_action: Literal['none', 'destroy'] = 'none'
    retention_days: int = Field(ge=1, le=3650)
    availability: Literal['single', 'zone-redundant', 'managed-multizone']
    instances: int = Field(default=1, ge=1, le=100)
    sku: str = Field(min_length=1, max_length=64)
    currency: Literal['USD', 'EUR'] = 'USD'
    budget_limit: Decimal = Field(gt=0)

    @field_validator('starts_at', 'expires_at')
    @classmethod
    def aware(cls, value):
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError('Timestamps must include an explicit UTC offset')
        return value

    @model_validator(mode='after')
    def coherent(self):
        allowed = {'azure': {'terraform','bicep'}, 'aws': {'terraform','cdk-python','cdk-typescript'}}
        if self.iac not in allowed[self.cloud]:
            raise ValueError('IaC engine does not match the cloud')
        if (self.ecosystem == 'app-service' and self.cloud != 'azure') or (self.ecosystem == 'lambda' and self.cloud != 'aws'):
            raise ValueError('Ecosystem does not match the cloud')
        if self.expires_at and (self.expires_at <= self.starts_at or self.expires_at - self.starts_at > timedelta(days=366)):
            raise ValueError('Expiry must be after creation and within 366 days')
        if self.expiry_action == 'destroy' and (not self.expires_at or self.purpose not in {'poc','development'}):
            raise ValueError('Automatic destruction is only available for time-bounded PoC/Development')
        if self.purpose == 'production':
            if self.expires_at or self.working_hours or self.expiry_action != 'none':
                raise ValueError('Production must run 24/7 without expiry or scheduled outages')
            if self.availability == 'single':
                raise ValueError('Production requires an explicit high-availability topology')
        if self.availability == 'zone-redundant' and self.instances < 2:
            raise ValueError('Zone redundancy requires at least two instances')
        if self.ecosystem == 'app-service':
            if self.availability == 'managed-multizone':
                raise ValueError('App Service zone redundancy must be configured explicitly')
            if self.availability == 'zone-redundant' and not re.fullmatch(r'P[0-9]+[MV]*V[234]', self.sku.upper()):
                raise ValueError('App Service zone redundancy requires a supported Premium SKU')
        return self


class ResourceRate(Contract):
    resource: str = Field(min_length=1)
    meter: str = Field(min_length=1)
    region: str
    currency: Literal['USD', 'EUR']
    unit: Literal['hour', 'request', 'gb-second', 'gb-month', 'gb']
    unit_price: Decimal = Field(ge=0)
    quantity: Decimal = Field(gt=0)
    billing: Literal['provisioned', 'active', 'usage']
    usage_units: Decimal | None = Field(default=None, ge=0)
    source: str = Field(pattern=r'^https://')
    retrieved_at: datetime

    @model_validator(mode='after')
    def compatible(self):
        if self.retrieved_at.tzinfo is None:
            raise ValueError('Price observation must include UTC offset')
        if self.unit != 'hour' and self.billing != 'usage':
            raise ValueError('Non-hourly meters require explicit usage assumptions')
        if self.billing == 'usage' and self.usage_units is None:
            raise ValueError('Usage must be supplied; missing consumption is not zero cost')
        return self


def estimate(intent: DeploymentIntent, rates: list[ResourceRate], *, ends_at: datetime,
             now: datetime, missing_resources: list[str] | None = None) -> dict:
    """Minute-exact interval integration, including IANA timezone/DST and retained fixed charges."""
    if ends_at.tzinfo is None or now.tzinfo is None:
        raise ValueError('Estimate interval and current time must be timezone aware')
    # An advisory expiry does not delete infrastructure or end billing.
    end = min(ends_at, intent.expires_at) if intent.expires_at and intent.expiry_action == 'destroy' else ends_at
    start = intent.starts_at.astimezone(timezone.utc)
    end = end.astimezone(timezone.utc)
    if end <= start or end - start > timedelta(days=366):
        raise ValueError('Cost interval must be positive and at most 366 days')
    total_seconds = Decimal(str((end - start).total_seconds()))
    active_seconds = Decimal(0)
    cursor = start
    daily = {}
    while cursor < end:
        boundary = min(end, cursor.replace(second=0, microsecond=0) + timedelta(minutes=1))
        seconds = Decimal(str((boundary - cursor).total_seconds()))
        active = intent.working_hours is None or intent.working_hours.active(cursor)
        active_seconds += seconds if active else 0
        day = cursor.date().isoformat()
        if day not in daily:
            daily[day] = {'provisioned_hours': Decimal(0), 'active_hours': Decimal(0)}
        daily[day]['provisioned_hours'] += seconds / 3600
        daily[day]['active_hours'] += seconds / 3600 if active else 0
        cursor = boundary
    rows = []
    blockers = [f'missing_resource:{name}' for name in (missing_resources or [])]
    if not rates:
        blockers.append('no_pricing_evidence')
    for rate in rates:
        if rate.region != intent.region or rate.currency != intent.currency:
            blockers.append(f'price_context_mismatch:{rate.resource}')
        if now - rate.retrieved_at > timedelta(hours=24) or rate.retrieved_at > now + timedelta(minutes=5):
            blockers.append(f'price_not_current:{rate.resource}')
        # An App Service plan bills while provisioned, even when its app is stopped.
        if intent.ecosystem == 'app-service' and rate.resource == 'app_service_plan' and rate.billing != 'provisioned':
            raise ValueError('App Service plan cost cannot be reduced using stopped-app hours')
        if intent.ecosystem == 'app-service' and rate.resource == 'app_service_plan' and rate.quantity != intent.instances:
            blockers.append('instance_quantity_mismatch:app_service_plan')
        units = rate.usage_units if rate.billing == 'usage' else (active_seconds if rate.billing == 'active' else total_seconds) / 3600
        amount = units * rate.quantity * rate.unit_price
        rows.append({'resource': rate.resource, 'meter': rate.meter, 'billing': rate.billing,
                     'units': str(units), 'quantity': str(rate.quantity), 'unit_price': str(rate.unit_price),
                     'estimated_cost': str(amount.quantize(Decimal('.000001'))),
                     'source': rate.source, 'retrieved_at': rate.retrieved_at.isoformat()})
    total = sum((Decimal(row['estimated_cost']) for row in rows), Decimal(0))
    if total > intent.budget_limit:
        blockers.append('budget_exceeded')
    return {'currency':intent.currency, 'starts_at':start.isoformat(), 'ends_at':end.isoformat(),
            'provisioned_hours':str(total_seconds/3600), 'active_hours':str(active_seconds/3600),
            'intervals':{day:{key:str(value) for key,value in values.items()} for day,values in daily.items()},
            'resources':rows, 'estimated_total':str(total), 'budget_limit':str(intent.budget_limit),
            'blockers':sorted(set(blockers)), 'can_request_apply_approval':not blockers,
            'basis':'Retail estimate from supplied pricing/usage evidence; excludes unlisted items and taxes.'}
