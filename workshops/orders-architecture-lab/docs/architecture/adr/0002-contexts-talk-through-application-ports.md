# ADR-0002 · Contexts talk through application ports

Status: accepted

## Context
Orders needs Payments to charge and Notifications to tell the customer. Reaching into another
context's tables or infrastructure couples their release cycles and leaks their models.

## Decision
A context declares a port in its application layer (`PaymentGateway`, `OrderNotifier`). An adapter
in its infrastructure implements it by calling the other context's application layer
(`PaymentsApplicationGateway` → `ChargePayment`).

## Consequences
Payments can change its storage or its provider without touching Orders. Importing
`payments.infrastructure` from Orders' domain or application breaks this decision.
