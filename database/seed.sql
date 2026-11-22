-- CloudDesk Support Platform — Postgres seed data
-- Run AFTER schema.sql to populate demo records.
-- For local SQLite demo, the Python seed_service.py loads sample_data/*.json instead.

-- ── Demo profiles ────────────────────────────────────────────────────────────
insert into profiles (id, email, full_name, role) values
  ('00000000-0000-0000-0000-000000000001', 'admin@clouddesk.demo',      'Admin User',    'admin'),
  ('00000000-0000-0000-0000-000000000002', 'sam.agent@clouddesk.demo',  'Sam Agent',     'agent'),
  ('00000000-0000-0000-0000-000000000003', 'vic.viewer@clouddesk.demo', 'Vic Viewer',    'viewer')
on conflict (id) do nothing;

-- ── Products ──────────────────────────────────────────────────────────────────
insert into products (id, name, slug, description, plan_limits) values
  (
    '10000000-0000-0000-0000-000000000001',
    'CloudDesk Free',
    'clouddesk-free',
    'Free tier for small teams',
    '{"storage_gb": 5, "seats": 3, "api_calls_per_day": 1000}'
  ),
  (
    '10000000-0000-0000-0000-000000000002',
    'CloudDesk Pro',
    'clouddesk-pro',
    'Professional tier for growing teams',
    '{"storage_gb": 100, "seats": 25, "api_calls_per_day": 50000}'
  ),
  (
    '10000000-0000-0000-0000-000000000003',
    'CloudDesk Business',
    'clouddesk-business',
    'Business tier with advanced features',
    '{"storage_gb": 500, "seats": 100, "api_calls_per_day": 250000}'
  ),
  (
    '10000000-0000-0000-0000-000000000004',
    'CloudDesk Enterprise',
    'clouddesk-enterprise',
    'Enterprise tier with SSO, SLA, and dedicated support',
    '{"storage_gb": 2000, "seats": -1, "api_calls_per_day": -1}'
  )
on conflict (id) do nothing;
