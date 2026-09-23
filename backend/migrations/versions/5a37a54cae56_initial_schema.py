"""initial_schema

Revision ID: 5a37a54cae56
Revises:
Create Date: 2026-09-23 05:05:12.893984
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '5a37a54cae56'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    existing = set(sa.inspect(op.get_bind()).get_table_names(schema='public')) - {'alembic_version'}
    if existing:
        raise RuntimeError(
            'Schema non vierge: ne pas recreer les tables. '
            'Executer le controle de baseline historique avant alembic upgrade head.'
        )
    op.create_table('organizations',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('slug', sa.String(length=255), nullable=False),
    sa.Column('plan', sa.String(length=50), nullable=False),
    sa.Column('status', sa.String(length=50), nullable=False),
    sa.Column('created_by_id', sa.UUID(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_organizations_slug'), 'organizations', ['slug'], unique=True)
    op.create_table('plans',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('slug', sa.String(length=80), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('price_monthly_eur', sa.Integer(), nullable=False),
    sa.Column('currency', sa.String(length=10), nullable=False),
    sa.Column('limits', sa.JSON(), nullable=False),
    sa.Column('features', sa.JSON(), nullable=False),
    sa.Column('stripe_price_id', sa.String(length=255), nullable=True),
    sa.Column('sort_order', sa.Integer(), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_plans_slug'), 'plans', ['slug'], unique=True)
    op.create_table('sources',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('organism', sa.String(length=255), nullable=False),
    sa.Column('country', sa.String(length=100), nullable=False),
    sa.Column('region', sa.String(length=100), nullable=True),
    sa.Column('source_type', sa.String(length=50), nullable=False),
    sa.Column('level', sa.SmallInteger(), nullable=False),
    sa.Column('url', sa.Text(), nullable=False),
    sa.Column('collection_mode', sa.String(length=50), nullable=False),
    sa.Column('check_frequency', sa.String(length=50), nullable=True),
    sa.Column('reliability', sa.SmallInteger(), nullable=False),
    sa.Column('category', sa.String(length=20), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('last_checked_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('last_success_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('consecutive_errors', sa.SmallInteger(), nullable=True),
    sa.Column('config', sa.JSON(), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_sources_category'), 'sources', ['category'], unique=False)
    op.create_index(op.f('ix_sources_country'), 'sources', ['country'], unique=False)
    op.create_index(op.f('ix_sources_is_active'), 'sources', ['is_active'], unique=False)
    op.create_index(op.f('ix_sources_level'), 'sources', ['level'], unique=False)
    op.create_table('users',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('email', sa.String(length=255), nullable=False),
    sa.Column('password_hash', sa.String(length=255), nullable=False),
    sa.Column('full_name', sa.String(length=255), nullable=True),
    sa.Column('role', sa.String(length=50), nullable=False),
    sa.Column('platform_role', sa.String(length=50), nullable=False),
    sa.Column('default_organization_id', sa.UUID(), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('country', sa.String(length=100), nullable=True),
    sa.Column('sectors', sa.String(length=500), nullable=True),
    sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['default_organization_id'], ['organizations.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_foreign_key('fk_organizations_created_by_id_users', 'organizations', 'users', ['created_by_id'], ['id'], ondelete='SET NULL')
    op.create_table('alerts',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('organization_id', sa.UUID(), nullable=True),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('criteria', sa.JSON(), nullable=False),
    sa.Column('frequency', sa.String(length=20), nullable=True),
    sa.Column('channels', postgresql.ARRAY(sa.Text()), nullable=True),
    sa.Column('alert_types', postgresql.ARRAY(sa.Text()), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=True),
    sa.Column('last_triggered_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_alerts_organization_id'), 'alerts', ['organization_id'], unique=False)
    op.create_index(op.f('ix_alerts_user_id'), 'alerts', ['user_id'], unique=False)
    op.create_table('audit_logs',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=True),
    sa.Column('organization_id', sa.UUID(), nullable=True),
    sa.Column('action', sa.String(length=160), nullable=False),
    sa.Column('resource_type', sa.String(length=120), nullable=True),
    sa.Column('resource_id', sa.String(length=160), nullable=True),
    sa.Column('ip_address', sa.String(length=80), nullable=True),
    sa.Column('user_agent', sa.Text(), nullable=True),
    sa.Column('metadata_json', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_audit_logs_action'), 'audit_logs', ['action'], unique=False)
    op.create_index(op.f('ix_audit_logs_created_at'), 'audit_logs', ['created_at'], unique=False)
    op.create_index(op.f('ix_audit_logs_organization_id'), 'audit_logs', ['organization_id'], unique=False)
    op.create_index(op.f('ix_audit_logs_user_id'), 'audit_logs', ['user_id'], unique=False)
    op.create_table('billing_customers',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('stripe_customer_id', sa.String(length=255), nullable=True),
    sa.Column('billing_email', sa.String(length=255), nullable=True),
    sa.Column('metadata_json', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('organization_id', name='uq_billing_customer_organization')
    )
    op.create_index(op.f('ix_billing_customers_organization_id'), 'billing_customers', ['organization_id'], unique=False)
    op.create_index(op.f('ix_billing_customers_stripe_customer_id'), 'billing_customers', ['stripe_customer_id'], unique=True)
    op.create_table('collection_logs',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('source_id', sa.UUID(), nullable=False),
    sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('ended_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('status', sa.String(length=50), nullable=False),
    sa.Column('items_found', sa.Integer(), nullable=True),
    sa.Column('items_new', sa.Integer(), nullable=True),
    sa.Column('items_updated', sa.Integer(), nullable=True),
    sa.Column('items_skipped', sa.Integer(), nullable=True),
    sa.Column('items_error', sa.Integer(), nullable=True),
    sa.Column('error_message', sa.Text(), nullable=True),
    sa.Column('details', sa.JSON(), nullable=True),
    sa.ForeignKeyConstraint(['source_id'], ['sources.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_collection_logs_source_id'), 'collection_logs', ['source_id'], unique=False)
    op.create_index(op.f('ix_collection_logs_started_at'), 'collection_logs', ['started_at'], unique=False)
    op.create_table('data_exports',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('status', sa.String(length=50), nullable=False),
    sa.Column('export_type', sa.String(length=80), nullable=False),
    sa.Column('download_token', sa.String(length=255), nullable=False),
    sa.Column('payload', sa.JSON(), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_data_exports_created_at'), 'data_exports', ['created_at'], unique=False)
    op.create_index(op.f('ix_data_exports_download_token'), 'data_exports', ['download_token'], unique=True)
    op.create_index(op.f('ix_data_exports_user_id'), 'data_exports', ['user_id'], unique=False)
    op.create_table('deletion_requests',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('status', sa.String(length=50), nullable=False),
    sa.Column('reason', sa.Text(), nullable=True),
    sa.Column('scheduled_for', sa.DateTime(timezone=True), nullable=True),
    sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_deletion_requests_created_at'), 'deletion_requests', ['created_at'], unique=False)
    op.create_index(op.f('ix_deletion_requests_user_id'), 'deletion_requests', ['user_id'], unique=False)
    op.create_table('devices',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('slug', sa.String(length=300), nullable=True),
    sa.Column('title', sa.String(length=500), nullable=False),
    sa.Column('title_normalized', sa.String(length=500), nullable=True),
    sa.Column('organism', sa.String(length=255), nullable=False),
    sa.Column('organism_type', sa.String(length=100), nullable=True),
    sa.Column('country', sa.String(length=100), nullable=False),
    sa.Column('region', sa.String(length=200), nullable=True),
    sa.Column('zone', sa.String(length=200), nullable=True),
    sa.Column('geographic_scope', sa.String(length=50), nullable=True),
    sa.Column('device_type', sa.String(length=100), nullable=False),
    sa.Column('aid_nature', sa.String(length=100), nullable=True),
    sa.Column('sectors', postgresql.ARRAY(sa.Text()), nullable=True),
    sa.Column('beneficiaries', postgresql.ARRAY(sa.Text()), nullable=True),
    sa.Column('short_description', sa.Text(), nullable=True),
    sa.Column('full_description', sa.Text(), nullable=True),
    sa.Column('content_sections_json', sa.JSON(), nullable=True),
    sa.Column('ai_rewritten_sections_json', sa.JSON(), nullable=True),
    sa.Column('ai_rewrite_status', sa.String(length=50), nullable=True),
    sa.Column('ai_rewrite_model', sa.String(length=120), nullable=True),
    sa.Column('ai_rewrite_checked_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('eligibility_criteria', sa.Text(), nullable=True),
    sa.Column('eligible_expenses', sa.Text(), nullable=True),
    sa.Column('specific_conditions', sa.Text(), nullable=True),
    sa.Column('required_documents', sa.Text(), nullable=True),
    sa.Column('amount_min', sa.Numeric(precision=15, scale=2), nullable=True),
    sa.Column('amount_max', sa.Numeric(precision=15, scale=2), nullable=True),
    sa.Column('currency', sa.String(length=10), nullable=True),
    sa.Column('funding_rate', sa.Numeric(precision=5, scale=2), nullable=True),
    sa.Column('funding_details', sa.Text(), nullable=True),
    sa.Column('open_date', sa.Date(), nullable=True),
    sa.Column('close_date', sa.Date(), nullable=True),
    sa.Column('is_recurring', sa.Boolean(), nullable=True),
    sa.Column('recurrence_notes', sa.Text(), nullable=True),
    sa.Column('status', sa.String(length=50), nullable=False),
    sa.Column('source_id', sa.UUID(), nullable=True),
    sa.Column('source_url', sa.Text(), nullable=False),
    sa.Column('source_raw', sa.Text(), nullable=True),
    sa.Column('source_hash', sa.String(length=64), nullable=True),
    sa.Column('language', sa.String(length=10), nullable=True),
    sa.Column('keywords', postgresql.ARRAY(sa.Text()), nullable=True),
    sa.Column('tags', postgresql.ARRAY(sa.Text()), nullable=True),
    sa.Column('auto_summary', sa.Text(), nullable=True),
    sa.Column('confidence_score', sa.SmallInteger(), nullable=True),
    sa.Column('completeness_score', sa.SmallInteger(), nullable=True),
    sa.Column('relevance_score', sa.SmallInteger(), nullable=True),
    sa.Column('ai_readiness_score', sa.SmallInteger(), nullable=True),
    sa.Column('ai_readiness_label', sa.String(length=80), nullable=True),
    sa.Column('ai_readiness_reasons', postgresql.ARRAY(sa.Text()), nullable=True),
    sa.Column('user_quality_score', sa.SmallInteger(), nullable=True),
    sa.Column('user_quality_decision', sa.String(length=50), nullable=True),
    sa.Column('user_quality_reasons', postgresql.ARRAY(sa.Text()), nullable=True),
    sa.Column('validation_status', sa.String(length=50), nullable=True),
    sa.Column('validated_by', sa.UUID(), nullable=True),
    sa.Column('validated_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('decision_analysis', sa.JSON(), nullable=True),
    sa.Column('decision_analyzed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('first_seen_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('last_verified_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('search_vector', postgresql.TSVECTOR(), nullable=True),
    sa.ForeignKeyConstraint(['source_id'], ['sources.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['validated_by'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('slug')
    )
    op.create_index('idx_devices_beneficiaries', 'devices', ['beneficiaries'], unique=False, postgresql_using='gin')
    op.create_index('idx_devices_keywords', 'devices', ['keywords'], unique=False, postgresql_using='gin')
    op.create_index('idx_devices_search_vector', 'devices', ['search_vector'], unique=False, postgresql_using='gin')
    op.create_index('idx_devices_sectors', 'devices', ['sectors'], unique=False, postgresql_using='gin')
    op.create_index(op.f('ix_devices_ai_rewrite_status'), 'devices', ['ai_rewrite_status'], unique=False)
    op.create_index(op.f('ix_devices_close_date'), 'devices', ['close_date'], unique=False)
    op.create_index(op.f('ix_devices_country'), 'devices', ['country'], unique=False)
    op.create_index(op.f('ix_devices_device_type'), 'devices', ['device_type'], unique=False)
    op.create_index(op.f('ix_devices_source_id'), 'devices', ['source_id'], unique=False)
    op.create_index(op.f('ix_devices_status'), 'devices', ['status'], unique=False)
    op.create_index(op.f('ix_devices_validation_status'), 'devices', ['validation_status'], unique=False)
    op.create_table('email_events',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=True),
    sa.Column('email', sa.String(length=255), nullable=False),
    sa.Column('template', sa.String(length=120), nullable=False),
    sa.Column('subject', sa.String(length=255), nullable=False),
    sa.Column('status', sa.String(length=50), nullable=False),
    sa.Column('provider_message_id', sa.String(length=255), nullable=True),
    sa.Column('error_message', sa.Text(), nullable=True),
    sa.Column('metadata_json', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_email_events_created_at'), 'email_events', ['created_at'], unique=False)
    op.create_index(op.f('ix_email_events_email'), 'email_events', ['email'], unique=False)
    op.create_index(op.f('ix_email_events_user_id'), 'email_events', ['user_id'], unique=False)
    op.create_table('funding_projects',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('created_by_id', sa.UUID(), nullable=True),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('summary', sa.Text(), nullable=True),
    sa.Column('countries', postgresql.ARRAY(sa.Text()), nullable=True),
    sa.Column('sectors', postgresql.ARRAY(sa.Text()), nullable=True),
    sa.Column('beneficiaries', postgresql.ARRAY(sa.Text()), nullable=True),
    sa.Column('target_funding_types', postgresql.ARRAY(sa.Text()), nullable=True),
    sa.Column('budget_min', sa.Numeric(precision=15, scale=2), nullable=True),
    sa.Column('budget_max', sa.Numeric(precision=15, scale=2), nullable=True),
    sa.Column('timeline_months', sa.Integer(), nullable=True),
    sa.Column('status', sa.String(length=50), nullable=False),
    sa.Column('is_primary', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['created_by_id'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_funding_projects_created_by_id'), 'funding_projects', ['created_by_id'], unique=False)
    op.create_index(op.f('ix_funding_projects_organization_id'), 'funding_projects', ['organization_id'], unique=False)
    op.create_table('invitations',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('email', sa.String(length=255), nullable=False),
    sa.Column('role', sa.String(length=50), nullable=False),
    sa.Column('token', sa.String(length=255), nullable=False),
    sa.Column('invited_by_id', sa.UUID(), nullable=True),
    sa.Column('accepted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['invited_by_id'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_invitations_email'), 'invitations', ['email'], unique=False)
    op.create_index(op.f('ix_invitations_organization_id'), 'invitations', ['organization_id'], unique=False)
    op.create_index(op.f('ix_invitations_token'), 'invitations', ['token'], unique=True)
    op.create_table('match_projects',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('organization_id', sa.UUID(), nullable=True),
    sa.Column('file_name', sa.String(length=500), nullable=True),
    sa.Column('file_size', sa.Integer(), nullable=True),
    sa.Column('result', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_match_projects_organization_id'), 'match_projects', ['organization_id'], unique=False)
    op.create_index(op.f('ix_match_projects_user_id'), 'match_projects', ['user_id'], unique=False)
    op.create_table('organization_members',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('role', sa.String(length=50), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('joined_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('organization_id', 'user_id', name='uq_organization_member_user')
    )
    op.create_index(op.f('ix_organization_members_organization_id'), 'organization_members', ['organization_id'], unique=False)
    op.create_index(op.f('ix_organization_members_user_id'), 'organization_members', ['user_id'], unique=False)
    op.create_table('organization_profiles',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('organization_type', sa.String(length=80), nullable=True),
    sa.Column('legal_form', sa.String(length=120), nullable=True),
    sa.Column('team_size', sa.String(length=50), nullable=True),
    sa.Column('annual_budget_range', sa.String(length=80), nullable=True),
    sa.Column('development_stage', sa.String(length=50), nullable=True),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('website', sa.String(length=500), nullable=True),
    sa.Column('countries', postgresql.ARRAY(sa.Text()), nullable=True),
    sa.Column('regions', postgresql.ARRAY(sa.Text()), nullable=True),
    sa.Column('sectors', postgresql.ARRAY(sa.Text()), nullable=True),
    sa.Column('target_funding_types', postgresql.ARRAY(sa.Text()), nullable=True),
    sa.Column('preferred_ticket_min', sa.Numeric(precision=15, scale=2), nullable=True),
    sa.Column('preferred_ticket_max', sa.Numeric(precision=15, scale=2), nullable=True),
    sa.Column('currency', sa.String(length=10), nullable=False),
    sa.Column('strategic_priorities', postgresql.ARRAY(sa.Text()), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('organization_id', name='uq_organization_profile_organization')
    )
    op.create_index(op.f('ix_organization_profiles_organization_id'), 'organization_profiles', ['organization_id'], unique=False)
    op.create_table('password_reset_tokens',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('token_hash', sa.String(length=255), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_password_reset_tokens_token_hash'), 'password_reset_tokens', ['token_hash'], unique=True)
    op.create_index(op.f('ix_password_reset_tokens_user_id'), 'password_reset_tokens', ['user_id'], unique=False)
    op.create_table('saved_searches',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('organization_id', sa.UUID(), nullable=True),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('title', sa.String(length=255), nullable=True),
    sa.Column('path', sa.String(length=255), nullable=True),
    sa.Column('query', sa.JSON(), nullable=False),
    sa.Column('result_count', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_saved_searches_organization_id'), 'saved_searches', ['organization_id'], unique=False)
    op.create_index(op.f('ix_saved_searches_user_id'), 'saved_searches', ['user_id'], unique=False)
    op.create_table('subscriptions',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('plan_id', sa.UUID(), nullable=False),
    sa.Column('status', sa.String(length=50), nullable=False),
    sa.Column('stripe_subscription_id', sa.String(length=255), nullable=True),
    sa.Column('current_period_start', sa.DateTime(timezone=True), nullable=True),
    sa.Column('current_period_end', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['plan_id'], ['plans.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('organization_id', name='uq_subscription_organization')
    )
    op.create_index(op.f('ix_subscriptions_organization_id'), 'subscriptions', ['organization_id'], unique=False)
    op.create_index(op.f('ix_subscriptions_plan_id'), 'subscriptions', ['plan_id'], unique=False)
    op.create_table('usage_events',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('organization_id', sa.UUID(), nullable=True),
    sa.Column('user_id', sa.UUID(), nullable=True),
    sa.Column('event_type', sa.String(length=120), nullable=False),
    sa.Column('quantity', sa.Integer(), nullable=False),
    sa.Column('event_metadata', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_usage_events_event_type'), 'usage_events', ['event_type'], unique=False)
    op.create_index(op.f('ix_usage_events_organization_id'), 'usage_events', ['organization_id'], unique=False)
    op.create_index(op.f('ix_usage_events_user_id'), 'usage_events', ['user_id'], unique=False)
    op.create_table('user_preferences',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('organization_id', sa.UUID(), nullable=True),
    sa.Column('preferences', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', name='uq_user_preferences_user')
    )
    op.create_index(op.f('ix_user_preferences_organization_id'), 'user_preferences', ['organization_id'], unique=False)
    op.create_index(op.f('ix_user_preferences_user_id'), 'user_preferences', ['user_id'], unique=False)
    op.create_table('device_history',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('device_id', sa.UUID(), nullable=False),
    sa.Column('changed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('changed_by', sa.String(length=100), nullable=True),
    sa.Column('change_type', sa.String(length=50), nullable=True),
    sa.Column('diff', sa.JSON(), nullable=True),
    sa.Column('source_hash', sa.String(length=64), nullable=True),
    sa.ForeignKeyConstraint(['device_id'], ['devices.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_device_history_changed_at'), 'device_history', ['changed_at'], unique=False)
    op.create_index(op.f('ix_device_history_device_id'), 'device_history', ['device_id'], unique=False)
    op.create_table('device_pipeline',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('organization_id', sa.UUID(), nullable=True),
    sa.Column('device_id', sa.UUID(), nullable=False),
    sa.Column('pipeline_status', sa.String(length=80), nullable=False),
    sa.Column('priority', sa.String(length=20), nullable=False),
    sa.Column('reminder_date', sa.Date(), nullable=True),
    sa.Column('match_project_id', sa.UUID(), nullable=True),
    sa.Column('note', sa.Text(), nullable=False),
    sa.Column('documents', sa.JSON(), nullable=True),
    sa.Column('snapshot', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['device_id'], ['devices.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['match_project_id'], ['match_projects.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'device_id', name='uq_device_pipeline_user_device')
    )
    op.create_index(op.f('ix_device_pipeline_device_id'), 'device_pipeline', ['device_id'], unique=False)
    op.create_index(op.f('ix_device_pipeline_match_project_id'), 'device_pipeline', ['match_project_id'], unique=False)
    op.create_index(op.f('ix_device_pipeline_organization_id'), 'device_pipeline', ['organization_id'], unique=False)
    op.create_index(op.f('ix_device_pipeline_user_id'), 'device_pipeline', ['user_id'], unique=False)
    op.create_table('device_relevance_cache',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('device_id', sa.UUID(), nullable=False),
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('funding_project_id', sa.UUID(), nullable=True),
    sa.Column('relevance_score', sa.Integer(), nullable=False),
    sa.Column('relevance_label', sa.String(length=120), nullable=True),
    sa.Column('priority_level', sa.String(length=40), nullable=True),
    sa.Column('eligibility_confidence', sa.String(length=40), nullable=True),
    sa.Column('decision_hint', sa.Text(), nullable=True),
    sa.Column('reason_codes', sa.JSON(), nullable=True),
    sa.Column('reason_texts', sa.JSON(), nullable=True),
    sa.Column('computed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['device_id'], ['devices.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['funding_project_id'], ['funding_projects.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('device_id', 'organization_id', 'funding_project_id', name='uq_device_relevance_cache_scope')
    )
    op.create_index(op.f('ix_device_relevance_cache_device_id'), 'device_relevance_cache', ['device_id'], unique=False)
    op.create_index(op.f('ix_device_relevance_cache_funding_project_id'), 'device_relevance_cache', ['funding_project_id'], unique=False)
    op.create_index(op.f('ix_device_relevance_cache_organization_id'), 'device_relevance_cache', ['organization_id'], unique=False)
    op.create_table('favorite_devices',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('organization_id', sa.UUID(), nullable=True),
    sa.Column('device_id', sa.UUID(), nullable=False),
    sa.Column('snapshot', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['device_id'], ['devices.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'device_id', name='uq_favorite_device_user_device')
    )
    op.create_index(op.f('ix_favorite_devices_device_id'), 'favorite_devices', ['device_id'], unique=False)
    op.create_index(op.f('ix_favorite_devices_organization_id'), 'favorite_devices', ['organization_id'], unique=False)
    op.create_index(op.f('ix_favorite_devices_user_id'), 'favorite_devices', ['user_id'], unique=False)


def downgrade() -> None:
    raise RuntimeError('Downgrade interdit: supprimer ce schema detruirait les donnees Kafundo')
