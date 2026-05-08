"""
Alembic migration: add desired_states table for drift detection.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = 'add_desired_states_001'
down_revision = 'bc8de533f049'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'desired_states',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('resource_id', sa.String(512), nullable=False, unique=True, index=True),
        sa.Column('desired_state', JSONB(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade():
    op.drop_table('desired_states')
