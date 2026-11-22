-- CloudDesk Support Platform — Postgres DDL
-- Authority: this file. See CLAUDE.md §6.
-- Run against a Supabase project via the SQL editor.
-- For local development, SQLAlchemy creates equivalent tables via create_all().

-- ── Enable extensions ───────────────────────────────────────────────────────
create extension if not exists "uuid-ossp";
create extension if not exists "pg_trgm";

-- ── Utility: set_updated_at trigger ─────────────────────────────────────────
create or replace function set_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

-- ── profiles ─────────────────────────────────────────────────────────────────
create table if not exists profiles (
  id          uuid primary key default uuid_generate_v4(),
  email       text not null unique,
  full_name   text not null,
  role        text not null default 'viewer' check (role in ('viewer','agent','admin')),
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);
create trigger trg_profiles_updated_at before update on profiles
  for each row execute function set_updated_at();

-- ── customers ────────────────────────────────────────────────────────────────
create table if not exists customers (
  id          uuid primary key default uuid_generate_v4(),
  external_id text not null unique,
  name        text not null,
  email       text not null unique,
  company     text,
  plan        text not null default 'free' check (plan in ('free','pro','business','enterprise')),
  status      text not null default 'active' check (status in ('active','suspended','cancelled')),
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);
create trigger trg_customers_updated_at before update on customers
  for each row execute function set_updated_at();

-- ── subscriptions ─────────────────────────────────────────────────────────────
create table if not exists subscriptions (
  id            uuid primary key default uuid_generate_v4(),
  customer_id   uuid not null references customers(id) on delete cascade,
  plan          text not null,
  seats         integer not null default 1,
  seats_used    integer not null default 0,
  status        text not null default 'active',
  billing_cycle text not null default 'monthly' check (billing_cycle in ('monthly','annual')),
  amount        numeric(10,2) not null default 0,
  currency      text not null default 'USD',
  renewal_date  date,
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now()
);
create trigger trg_subscriptions_updated_at before update on subscriptions
  for each row execute function set_updated_at();

-- ── workspaces ────────────────────────────────────────────────────────────────
create table if not exists workspaces (
  id               uuid primary key default uuid_generate_v4(),
  customer_id      uuid not null references customers(id) on delete cascade,
  name             text not null,
  slug             text not null unique,
  region           text not null default 'us-east-1',
  storage_used_gb  numeric(12,3) not null default 0,
  storage_limit_gb numeric(12,3) not null default 5,
  member_count     integer not null default 1,
  settings         jsonb not null default '{}',
  created_at       timestamptz not null default now(),
  updated_at       timestamptz not null default now()
);
create trigger trg_workspaces_updated_at before update on workspaces
  for each row execute function set_updated_at();

-- ── products ──────────────────────────────────────────────────────────────────
create table if not exists products (
  id          uuid primary key default uuid_generate_v4(),
  name        text not null,
  slug        text not null unique,
  description text,
  plan_limits jsonb not null default '{}',
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);
create trigger trg_products_updated_at before update on products
  for each row execute function set_updated_at();

-- ── tickets ───────────────────────────────────────────────────────────────────
create table if not exists tickets (
  id               uuid primary key default uuid_generate_v4(),
  ticket_number    text not null unique,
  customer_id      uuid not null references customers(id),
  subject          text not null,
  body             text not null,
  channel          text not null default 'web' check (channel in ('email','chat','web','api')),
  status           text not null default 'new' check (status in (
                     'new','in_progress','waiting_on_customer',
                     'waiting_on_approval','escalated','resolved','closed')),
  severity         text check (severity in ('low','medium','high','critical')),
  category         text check (category in (
                     'login_issue','billing','api_failure','workspace_permissions',
                     'storage_quota','integration','feature_request','account',
                     'security','other')),
  category_summary text,
  assigned_to      uuid references profiles(id),
  created_at       timestamptz not null default now(),
  updated_at       timestamptz not null default now()
);
create index if not exists idx_tickets_customer   on tickets(customer_id);
create index if not exists idx_tickets_status     on tickets(status);
create index if not exists idx_tickets_created_at on tickets(created_at desc);
create trigger trg_tickets_updated_at before update on tickets
  for each row execute function set_updated_at();

-- ── ticket_messages ───────────────────────────────────────────────────────────
create table if not exists ticket_messages (
  id         uuid primary key default uuid_generate_v4(),
  ticket_id  uuid not null references tickets(id) on delete cascade,
  role       text not null check (role in ('customer','agent','system')),
  body       text not null,
  author_id  uuid references profiles(id),
  created_at timestamptz not null default now()
);
create index if not exists idx_ticket_messages_ticket on ticket_messages(ticket_id);

-- ── support_articles ──────────────────────────────────────────────────────────
create table if not exists support_articles (
  id         uuid primary key default uuid_generate_v4(),
  slug       text not null unique,
  title      text not null,
  category   text not null,
  tags       jsonb not null default '[]',
  summary    text,
  body       text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists idx_articles_category on support_articles(category);
create trigger trg_articles_updated_at before update on support_articles
  for each row execute function set_updated_at();

-- ── incidents ─────────────────────────────────────────────────────────────────
create table if not exists incidents (
  id                uuid primary key default uuid_generate_v4(),
  title             text not null,
  description       text not null,
  affected_services jsonb not null default '[]',
  status            text not null default 'investigating' check (status in ('investigating','monitoring','resolved')),
  severity          text not null default 'medium' check (severity in ('low','medium','high','critical')),
  started_at        timestamptz not null default now(),
  resolved_at       timestamptz,
  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now()
);
create trigger trg_incidents_updated_at before update on incidents
  for each row execute function set_updated_at();

-- ── workflow_runs ─────────────────────────────────────────────────────────────
create table if not exists workflow_runs (
  id           uuid primary key default uuid_generate_v4(),
  ticket_id    uuid not null references tickets(id),
  status       text not null default 'running' check (status in ('running','paused','completed','failed')),
  state        jsonb not null default '{}',
  started_by   uuid references profiles(id),
  started_at   timestamptz not null default now(),
  completed_at timestamptz,
  created_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now()
);
create index if not exists idx_workflow_runs_ticket on workflow_runs(ticket_id);
create trigger trg_workflow_runs_updated_at before update on workflow_runs
  for each row execute function set_updated_at();

-- ── workflow_events ───────────────────────────────────────────────────────────
create table if not exists workflow_events (
  id         uuid primary key default uuid_generate_v4(),
  run_id     uuid not null references workflow_runs(id) on delete cascade,
  event_type text not null,
  node       text,
  data       jsonb not null default '{}',
  created_at timestamptz not null default now()
);
create index if not exists idx_workflow_events_run on workflow_events(run_id);

-- ── resolution_actions ────────────────────────────────────────────────────────
create table if not exists resolution_actions (
  id          uuid primary key default uuid_generate_v4(),
  run_id      uuid not null references workflow_runs(id),
  ticket_id   uuid not null references tickets(id),
  action_type text not null,
  args        jsonb not null default '{}',
  status      text not null default 'pending' check (status in ('pending','approved','rejected','executed','failed')),
  result      jsonb,
  executed_at timestamptz,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);
create trigger trg_resolution_actions_updated_at before update on resolution_actions
  for each row execute function set_updated_at();

-- ── approval_requests ─────────────────────────────────────────────────────────
create table if not exists approval_requests (
  id          uuid primary key default uuid_generate_v4(),
  run_id      uuid not null references workflow_runs(id),
  ticket_id   uuid not null references tickets(id),
  action_id   uuid references resolution_actions(id),
  status      text not null default 'pending' check (status in ('pending','approved','rejected')),
  reason      text,
  decided_by  uuid references profiles(id),
  decided_at  timestamptz,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);
create trigger trg_approval_requests_updated_at before update on approval_requests
  for each row execute function set_updated_at();

-- ── escalations ───────────────────────────────────────────────────────────────
create table if not exists escalations (
  id         uuid primary key default uuid_generate_v4(),
  ticket_id  uuid not null references tickets(id),
  run_id     uuid references workflow_runs(id),
  team       text not null,
  reason     text not null,
  priority   text not null default 'medium' check (priority in ('low','medium','high','critical')),
  status     text not null default 'open' check (status in ('open','acknowledged','resolved')),
  created_by text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create trigger trg_escalations_updated_at before update on escalations
  for each row execute function set_updated_at();

-- ── customer_memory ───────────────────────────────────────────────────────────
create table if not exists customer_memory (
  id          uuid primary key default uuid_generate_v4(),
  customer_id uuid not null references customers(id) on delete cascade,
  memory_type text not null check (memory_type in ('preference','past_issue','troubleshooting','note')),
  content     text not null,
  ticket_id   uuid references tickets(id),
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);
create index if not exists idx_customer_memory_customer on customer_memory(customer_id);
create trigger trg_customer_memory_updated_at before update on customer_memory
  for each row execute function set_updated_at();

-- ── audit_logs ────────────────────────────────────────────────────────────────
create table if not exists audit_logs (
  id            uuid primary key default uuid_generate_v4(),
  actor_id      uuid,
  actor_role    text,
  action        text not null,
  resource_type text not null,
  resource_id   uuid,
  request_id    text,
  ip_address    text,
  extra         jsonb,
  created_at    timestamptz not null default now()
);
create index if not exists idx_audit_logs_created_at on audit_logs(created_at desc);
create index if not exists idx_audit_logs_actor      on audit_logs(actor_id);
