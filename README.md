# Argoz Real Estate CRM — Django MVT Backend

Backend for the Argoz CRM. Source of truth for business rules:
`docs/Argoz_CRM_Django_MVT_Technical_Software_Design_Document_v1.docx`.
Architecture rules: `CLAUDE.md`.

## Stack
Django 4.2 · Celery + Redis · Channels (WebSocket notifications) · MariaDB
(`argoz`) in prod, sqlite in dev. Custom DB-driven authorization, configurable
policies, centralized audit, OOP distribution strategies.

## Layout (`apps/`)
`core` (abstract bases, constants, exceptions) · `companies` (tenant root +
current-company resolver) · `accounts` (User, profiles, teams, languages,
brokers) · `authorization` (roles/permissions, effective resolver,
decorators/mixins/tags) · `audit` (append-only log + RequestMeta middleware) ·
`policies` (configurable rules + strategy registry) · `leads` (lifecycle, stages,
SLA, follow-ups, services) · `distribution` (Round Robin / By Turn strategies,
manual, retry/escalation, SLA expiry) · `marketing` (campaigns + all type
children, budget/approval/attribution/ROI) · `finance` (approval façade) ·
`notifications` (typed notifications, email outbox, WS consumer) · `integrations`
(dynamic webhooks → LeadCreationService) · `reports` (scoped selectors).

Each app: `models.py` (fields only), `services*` (workflows), `selectors.py`
(reads), `tasks.py` (Celery → services). Views stay thin.

## Run (dev)
```bash
cp .env.example .env                 # dev defaults to sqlite, no Redis needed
venv/Scripts/python manage.py migrate
venv/Scripts/python manage.py seed_crm        # stages, sources, policies, roles, types
venv/Scripts/python manage.py createsuperuser # email is the login field
venv/Scripts/python manage.py runserver
```

Background workers (need Redis; set `USE_REDIS=1`, `USE_MYSQL=1` as desired):
```bash
celery -A config worker -l info
celery -A config beat   -l info          # SLA scan, reminders, email, webhook retry
```

## Key entry points
- Lead intake (all sources incl. webhooks): `apps.leads.services.LeadCreationService`
- Distribution: `apps.distribution.services` (`DistributionEngine`,
  `ManualAssignmentService`, `RetryEscalationService`, `SLAExpiryService`)
- Permissions: `apps.authorization.services.EffectivePermissionResolver`,
  `@crm_permission_required`, `CRMPermissionRequiredMixin`, `{{ user|can:'code' }}`
- Policies: `apps.policies.services.PolicyResolver`
- Campaigns: `apps.marketing.services` · Finance: `apps.finance.services`
- Webhook setup: `apps.integrations.setup_service.IntegrationSetupService`;
  receive endpoint `POST /integrations/webhooks/<uuid>/` (header `X-Webhook-Token`)

## Pages (server-rendered MVT, docs §14)
Namespaced URLs, thin permission-protected views calling services, nav built
from `PageDefinition` filtered by the effective permission set:
`dashboard:index`, `leads:list|detail|create|assign|followup_create|meeting_create|stage_change`,
`marketing:campaign_list|campaign_create|campaign_detail|campaign_budget`,
`finance:campaign_approval|campaign_decide`, `accounts:login|user_list|user_create`,
`authorization:role_list|permission_catalog|user_matrix`, `policies:list|edit`,
`audit:list`, `notifications:list`, `integrations:webhook_list|webhook_create`.

## Notes
- Doc targets Django 5/Python 3.12; built on the installed Django 4.2 / 3.11.
- Templates are minimal/unstyled (no CSS/JS) — they exercise the view layer and
  permission-aware nav; styling is intentionally out of scope.
