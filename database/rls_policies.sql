-- CloudDesk Support Platform — Row Level Security policies
-- Run AFTER schema.sql in a Supabase project.
-- The backend uses the service-role key (bypasses RLS).
-- The browser uses the anon key (subject to RLS).

-- Enable RLS on every data table
alter table profiles           enable row level security;
alter table customers          enable row level security;
alter table subscriptions      enable row level security;
alter table workspaces         enable row level security;
alter table products           enable row level security;
alter table tickets            enable row level security;
alter table ticket_messages    enable row level security;
alter table support_articles   enable row level security;
alter table incidents          enable row level security;
alter table workflow_runs      enable row level security;
alter table workflow_events    enable row level security;
alter table resolution_actions enable row level security;
alter table approval_requests  enable row level security;
alter table escalations        enable row level security;
alter table customer_memory    enable row level security;
alter table audit_logs         enable row level security;

-- Helper: get the current user's role from the profiles table
create or replace function current_user_role() returns text
language sql stable as $$
  select role from profiles where id = auth.uid()
$$;

-- ── profiles ─────────────────────────────────────────────────────────────────
-- Users can read their own profile; admins can read all.
create policy "profiles: read own or admin"
  on profiles for select
  using (id = auth.uid() or current_user_role() = 'admin');

-- ── customers ────────────────────────────────────────────────────────────────
-- Agents and admins can read; only admins can write.
create policy "customers: read by agent+"
  on customers for select
  using (current_user_role() in ('agent','admin'));

create policy "customers: write by admin"
  on customers for all
  using (current_user_role() = 'admin');

-- ── subscriptions ─────────────────────────────────────────────────────────────
create policy "subscriptions: read by agent+"
  on subscriptions for select
  using (current_user_role() in ('agent','admin'));

-- ── workspaces ────────────────────────────────────────────────────────────────
create policy "workspaces: read by agent+"
  on workspaces for select
  using (current_user_role() in ('agent','admin'));

-- ── products ──────────────────────────────────────────────────────────────────
create policy "products: read by all authenticated"
  on products for select
  using (auth.role() = 'authenticated');

-- ── tickets ───────────────────────────────────────────────────────────────────
create policy "tickets: read by agent+"
  on tickets for select
  using (current_user_role() in ('agent','admin'));

create policy "tickets: write by agent+"
  on tickets for all
  using (current_user_role() in ('agent','admin'));

-- ── ticket_messages ───────────────────────────────────────────────────────────
create policy "ticket_messages: read by agent+"
  on ticket_messages for select
  using (current_user_role() in ('agent','admin'));

create policy "ticket_messages: write by agent+"
  on ticket_messages for all
  using (current_user_role() in ('agent','admin'));

-- ── support_articles ──────────────────────────────────────────────────────────
create policy "support_articles: read by all authenticated"
  on support_articles for select
  using (auth.role() = 'authenticated');

create policy "support_articles: write by admin"
  on support_articles for all
  using (current_user_role() = 'admin');

-- ── incidents ─────────────────────────────────────────────────────────────────
create policy "incidents: read by all authenticated"
  on incidents for select
  using (auth.role() = 'authenticated');

-- ── workflow_runs ─────────────────────────────────────────────────────────────
create policy "workflow_runs: read by agent+"
  on workflow_runs for select
  using (current_user_role() in ('agent','admin'));

-- ── workflow_events ───────────────────────────────────────────────────────────
create policy "workflow_events: read by agent+"
  on workflow_events for select
  using (current_user_role() in ('agent','admin'));

-- ── resolution_actions ────────────────────────────────────────────────────────
create policy "resolution_actions: read by agent+"
  on resolution_actions for select
  using (current_user_role() in ('agent','admin'));

-- ── approval_requests ─────────────────────────────────────────────────────────
create policy "approval_requests: read by agent+"
  on approval_requests for select
  using (current_user_role() in ('agent','admin'));

create policy "approval_requests: decide by agent+"
  on approval_requests for update
  using (current_user_role() in ('agent','admin'));

-- ── escalations ───────────────────────────────────────────────────────────────
create policy "escalations: read by agent+"
  on escalations for select
  using (current_user_role() in ('agent','admin'));

-- ── customer_memory ───────────────────────────────────────────────────────────
create policy "customer_memory: read by agent+"
  on customer_memory for select
  using (current_user_role() in ('agent','admin'));

-- ── audit_logs ────────────────────────────────────────────────────────────────
create policy "audit_logs: read by admin"
  on audit_logs for select
  using (current_user_role() = 'admin');
