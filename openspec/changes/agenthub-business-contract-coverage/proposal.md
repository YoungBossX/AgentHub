# Expand explicit local business acceptance

The native-QA cohort is closed with its failures intact. Fixed API checks and
the contacts integration happy path do not establish validation boundaries or
user recovery after rejected requests. Extend only these existing demo contracts.
No product runtime restart, arbitrary target tests, dependencies, listeners,
new adapter, deployment, authentication or database entity is included.

Add trusted backend assertions for declared field boundaries/types, stable unique
identifiers/defaults, seeded duplicate rejection and unsupported methods. Add an
explicit contacts-resilience-v2 integration contract: browser validation,
duplicate feedback, retained input/list, a labeled synthetic 503 and actual retry
and persistence. Keep legacy contacts-create-v1 available and publish exactly
which contract ran. Bind the chosen harness policy and both input sources.
