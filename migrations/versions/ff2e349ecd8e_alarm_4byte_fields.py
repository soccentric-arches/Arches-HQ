"""alarm: 4-byte alarm code fields + nullable alarm_rule_id

Revision ID: ff2e349ecd8e
Revises: a40971629062
Create Date: 2026-07-30 00:00:00.000000

Extends the pre-existing ``alarm`` table (phase1) with the 4-byte alarm
scheme used by device-reported alarms (loop 20260730-app-alarms-daemon,
R3 ingest path). Adds ``major_id``, ``sub_section``, ``fault_type``,
``severity`` (SmallInteger) and ``alarm_code`` (Integer, the raw packed
4-byte code for traceability), all nullable so existing rule-based alarms
still insert cleanly. Makes ``alarm_rule_id`` nullable because
device-reported alarms have no originating rule.

Byte order of ``alarm_code`` (big-endian uint32, byte 0 = most significant):
  byte 0 = major_id, byte 1 = sub_section,
  byte 2 = fault_type, byte 3 = severity.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ff2e349ecd8e'
down_revision: Union[str, Sequence[str], None] = 'a40971629062'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Make alarm_rule_id nullable: device-reported alarms have no rule.
    op.alter_column(
        'alarm',
        'alarm_rule_id',
        existing_type=sa.UUID(),
        nullable=True,
    )
    # 4-byte alarm scheme fields.
    op.add_column('alarm', sa.Column('major_id', sa.SmallInteger(), nullable=True))
    op.add_column('alarm', sa.Column('sub_section', sa.SmallInteger(), nullable=True))
    op.add_column('alarm', sa.Column('fault_type', sa.SmallInteger(), nullable=True))
    op.add_column('alarm', sa.Column('severity', sa.SmallInteger(), nullable=True))
    # BigInteger: the 4-byte code is unsigned; 0xFFFFFFFF overflows int32.
    op.add_column('alarm', sa.Column('alarm_code', sa.BigInteger(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('alarm', 'alarm_code')
    op.drop_column('alarm', 'severity')
    op.drop_column('alarm', 'fault_type')
    op.drop_column('alarm', 'sub_section')
    op.drop_column('alarm', 'major_id')
    op.alter_column(
        'alarm',
        'alarm_rule_id',
        existing_type=sa.UUID(),
        nullable=False,
    )