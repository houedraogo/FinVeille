-- Controlled reconstruction of the unversioned schema observed in the audit.
-- Mirrors legacy_schema_lot2.sql but also includes a pre-existing user_projects
-- table (0 rows), reproducing the exact production scenario where create_all()
-- materialised the table before Alembic was introduced.
-- Apply ONLY to a disposable PostgreSQL database already at revision 5a37a54cae56.
BEGIN;
ALTER TABLE users DROP CONSTRAINT users_default_organization_id_fkey;
ALTER TABLE alerts DROP CONSTRAINT alerts_organization_id_fkey;
ALTER TABLE saved_searches DROP CONSTRAINT saved_searches_organization_id_fkey;
ALTER TABLE device_pipeline DROP CONSTRAINT device_pipeline_match_project_id_fkey;
ALTER TABLE users DROP COLUMN country;
ALTER TABLE users DROP COLUMN sectors;
ALTER TABLE device_pipeline DROP COLUMN priority;
ALTER TABLE device_pipeline DROP COLUMN documents;
ALTER TABLE devices DROP COLUMN ai_readiness_score;
ALTER TABLE saved_searches DROP COLUMN result_count;
DROP TABLE alembic_version;

-- Pre-existing user_projects: identical structure to what d742f48a3c19 would create.
CREATE TABLE user_projects (
    id UUID PRIMARY KEY NOT NULL,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    organization_id UUID REFERENCES organizations(id) ON DELETE SET NULL,
    name VARCHAR(300) NOT NULL,
    description TEXT,
    sectors TEXT[] NOT NULL DEFAULT '{}',
    countries TEXT[] NOT NULL DEFAULT '{}',
    stage VARCHAR(50) NOT NULL,
    budget_min NUMERIC(15, 2),
    budget_max NUMERIC(15, 2),
    currency VARCHAR(10),
    keywords TEXT[] DEFAULT '{}',
    cached_matches JSON NOT NULL,
    match_score NUMERIC(5, 2),
    matched_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX ix_user_projects_user_id ON user_projects (user_id);
CREATE INDEX ix_user_projects_organization_id ON user_projects (organization_id);

INSERT INTO users (id, email, password_hash, role, platform_role, is_active)
VALUES ('10000000-0000-0000-0000-000000000001', 'legacy@example.org', 'legacy-hash', 'reader', 'member', true);
INSERT INTO organizations (id, name, slug, plan, status, created_by_id)
VALUES ('20000000-0000-0000-0000-000000000001', 'Legacy Org', 'legacy-org', 'free', 'active', '10000000-0000-0000-0000-000000000001');
UPDATE users SET default_organization_id = '20000000-0000-0000-0000-000000000001'
WHERE id = '10000000-0000-0000-0000-000000000001';
INSERT INTO plans (id, slug, name, price_monthly_eur, currency, limits, features, sort_order, is_active)
VALUES ('30000000-0000-0000-0000-000000000001', 'legacy-plan', 'Legacy', 0, 'EUR', '{}', '{}', 0, true);
INSERT INTO subscriptions (id, organization_id, plan_id, status)
VALUES ('31000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000001', '30000000-0000-0000-0000-000000000001', 'active');
INSERT INTO sources (id, name, organism, country, source_type, level, url, collection_mode, reliability, category, is_active)
VALUES ('40000000-0000-0000-0000-000000000001', 'Legacy Source', 'Org', 'France', 'portail_officiel', 1, 'https://example.org', 'html', 5, 'public', true);
INSERT INTO devices (id, title, organism, country, device_type, source_url, source_id, status)
VALUES ('50000000-0000-0000-0000-000000000001', 'Legacy Grant', 'Org', 'France', 'subvention', 'https://example.org/grant', '40000000-0000-0000-0000-000000000001', 'open');
INSERT INTO match_projects (id, user_id, organization_id, result)
VALUES ('60000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000001', '{"legacy":true}');
INSERT INTO funding_projects (id, organization_id, name, status, is_primary)
VALUES ('61000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000001', 'Legacy Project', 'active', true);
INSERT INTO device_pipeline (id, user_id, organization_id, device_id, pipeline_status, match_project_id, note, snapshot)
VALUES ('70000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000001', '50000000-0000-0000-0000-000000000001', 'soumis', '60000000-0000-0000-0000-000000000001', 'Note client à conserver', '{"legacy":true}');
INSERT INTO favorite_devices (id, user_id, organization_id, device_id, snapshot)
VALUES ('71000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000001', '50000000-0000-0000-0000-000000000001', '{"saved":true}');
INSERT INTO alerts (id, user_id, organization_id, name, criteria)
VALUES ('72000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000001', 'Alerte historique', '{"country":"France"}');
INSERT INTO saved_searches (id, user_id, organization_id, name, query)
VALUES ('73000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000001', 'Recherche historique', '{"q":"grant"}');
INSERT INTO billing_customers (id, organization_id, stripe_customer_id, metadata_json)
VALUES ('74000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000001', 'cus_legacy', '{}');
COMMIT;
