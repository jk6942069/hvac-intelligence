"""Initial SaaS schema: users table + user_id columns + indexes.

Revision ID: 001
Revises:
Create Date: 2026-03-05
"""
from alembic import op
import sqlalchemy as sa

revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # users table
    op.create_table(
        'users',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('email', sa.String(), nullable=True),
        sa.Column('plan', sa.String(), nullable=False, server_default='starter'),
        sa.Column('stripe_customer_id', sa.String(), nullable=True),
        sa.Column('stripe_subscription_id', sa.String(), nullable=True),
        sa.Column('scans_used_this_month', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('scans_reset_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('NOW()')),
        sa.PrimaryKeyConstraint('id'),
    )

    # Add user_id to companies
    op.add_column('companies', sa.Column('user_id', sa.String(), nullable=True))
    op.create_index('ix_companies_user_conviction', 'companies', ['user_id', 'conviction_score'])
    op.create_foreign_key('fk_companies_user_id', 'companies', 'users', ['user_id'], ['id'])

    # Add user_id + cities to pipeline_runs
    op.add_column('pipeline_runs', sa.Column('user_id', sa.String(), nullable=True))
    op.add_column('pipeline_runs', sa.Column('cities', sa.JSON(), nullable=True))
    op.create_index('ix_pipeline_runs_user_created', 'pipeline_runs', ['user_id', 'started_at'])
    op.create_foreign_key('fk_pipeline_runs_user_id', 'pipeline_runs', 'users', ['user_id'], ['id'])

    # Add user_id to memos
    op.add_column('memos', sa.Column('user_id', sa.String(), nullable=True))
    op.create_index('ix_memos_user_id', 'memos', ['user_id'])
    op.create_foreign_key('fk_memos_user_id', 'memos', 'users', ['user_id'], ['id'])


def downgrade() -> None:
    op.drop_constraint('fk_memos_user_id', 'memos', type_='foreignkey')
    op.drop_index('ix_memos_user_id', table_name='memos')
    op.drop_column('memos', 'user_id')

    op.drop_constraint('fk_pipeline_runs_user_id', 'pipeline_runs', type_='foreignkey')
    op.drop_index('ix_pipeline_runs_user_created', table_name='pipeline_runs')
    op.drop_column('pipeline_runs', 'cities')
    op.drop_column('pipeline_runs', 'user_id')

    op.drop_constraint('fk_companies_user_id', 'companies', type_='foreignkey')
    op.drop_index('ix_companies_user_conviction', table_name='companies')
    op.drop_column('companies', 'user_id')

    op.drop_table('users')
