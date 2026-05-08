"""add otp columns

Revision ID: d4e5f6a7b8c9
Revises: 18e1a6fad806
Create Date: 2026-05-07 09:15:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'd4e5f6a7b8c9'
down_revision = '18e1a6fad806'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column('users', sa.Column('otp_code', sa.String(length=6), nullable=True))
    op.add_column('users', sa.Column('otp_expiry', sa.DateTime(timezone=True), nullable=True))
    op.add_column('users', sa.Column('is_verified', sa.Boolean(), server_default='false', nullable=False))

def downgrade() -> None:
    op.drop_column('users', 'is_verified')
    op.drop_column('users', 'otp_expiry')
    op.drop_column('users', 'otp_code')
