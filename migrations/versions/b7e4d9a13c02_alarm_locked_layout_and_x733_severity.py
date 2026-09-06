"""alarm locked layout and X.733 severity

Re-decodes the device alarm code against the layout Arches-Instrumentation
actually uses, and widens fault severity to the five X.733 levels.

Two defects, fixed together because the first is what frees the space the
second needs:

C-03/C-04 -- the `alarms` table stored major_id / sub_section / fault_type /
severity, decoded by cutting the 32-bit code into four equal bytes. The real
layout (locked; source of truth is Arches-Instrumentation/catalog/alarms.yaml
and REQ.md section 8) is [31:28] domain, [27:20] module, [19:16] type,
[15:0] index. The old byte boundaries fall *inside* the domain and module
fields, so every stored decode is wrong -- not shifted, garbage. The worked
example 0x10410007 was stored as (16, 65, 0, 7) instead of (1, 4, 1, 7).

C-05 -- severity is not in the code at all; it is reported separately, and
Instrumentation uses the five X.733 levels while HQ's FaultSeverity had only
info / warn / critical. MAJOR and MINOR had nowhere to land.

Existing rows are re-decoded from `alarm_code`, which is why that column was
kept for round-trip traceability. Severity cannot be recovered -- it was never
really in the code, the old low byte was the bottom of the alarm index -- so
rows are set to 'warning' and the true severity will arrive with the next
report from the device.

Revision ID: b7e4d9a13c02
Revises: ca576c7eb9fa
Create Date: 2026-09-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7e4d9a13c02'
down_revision: Union[str, Sequence[str], None] = 'ca576c7eb9fa'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Locked 32-bit layout (see the module docstring).
_DECODE_DOMAIN = "(alarm_code / 268435456) % 16"          # >> 28 & 0xF
_DECODE_MODULE = "(alarm_code / 1048576) % 256"           # >> 20 & 0xFF
_DECODE_TYPE = "(alarm_code / 65536) % 16"                # >> 16 & 0xF
_DECODE_INDEX = "alarm_code % 65536"                      # & 0xFFFF

_NEW_SEVERITY = ('info', 'warning', 'minor', 'major', 'critical')
_OLD_SEVERITY = ('info', 'warn', 'critical')


def upgrade() -> None:
    # ---- alarms: re-decode against the locked layout -----------------------
    #
    # batch_alter_table because SQLite cannot ALTER/DROP a column in place and
    # this project's baseline targets SQLite as well as Postgres.
    with op.batch_alter_table('alarms') as batch:
        batch.add_column(sa.Column('domain', sa.SmallInteger(), nullable=True))
        batch.add_column(sa.Column('module', sa.SmallInteger(), nullable=True))
        batch.add_column(sa.Column('alarm_type', sa.SmallInteger(), nullable=True))
        # index is 0..65535: SmallInteger is signed 16-bit and too narrow.
        batch.add_column(sa.Column('alarm_index', sa.Integer(), nullable=True))

    # Re-derive from the packed code rather than from the wrong columns -- the
    # old fields cannot be transformed into the new ones, only discarded.
    op.execute(
        f"UPDATE alarms SET "
        f"  domain = {_DECODE_DOMAIN}, "
        f"  module = {_DECODE_MODULE}, "
        f"  alarm_type = {_DECODE_TYPE}, "
        f"  alarm_index = {_DECODE_INDEX}"
    )

    # ---- severity: widen to the five X.733 levels --------------------------
    #
    # The column also changes meaning here: it was a byte sliced out of the
    # code, it is now the reported X.733 level. Nothing in the old value is
    # worth preserving, so every row starts at 'warning' and is corrected by
    # the device's next report.
    with op.batch_alter_table('alarms') as batch:
        batch.drop_column('severity')
    with op.batch_alter_table('alarms') as batch:
        batch.add_column(
            sa.Column(
                'severity',
                sa.Enum(*_NEW_SEVERITY, name='fault_severity'),
                nullable=False,
                server_default='warning',
            )
        )
        batch.drop_column('major_id')
        batch.drop_column('sub_section')
        batch.drop_column('fault_type')
        batch.alter_column('domain', nullable=False)
        batch.alter_column('module', nullable=False)
        batch.alter_column('alarm_type', nullable=False)
        batch.alter_column('alarm_index', nullable=False)

    op.create_index(op.f('ix_alarms_severity'), 'alarms', ['severity'], unique=False)

    # ---- fault.severity: same enum, existing rows remapped -----------------
    #
    # 'warn' is X.733's 'warning'; the rename is the only value change.
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        # Postgres enums are real types: add the new labels, then rename.
        op.execute("ALTER TYPE fault_severity ADD VALUE IF NOT EXISTS 'warning'")
        op.execute("ALTER TYPE fault_severity ADD VALUE IF NOT EXISTS 'minor'")
        op.execute("ALTER TYPE fault_severity ADD VALUE IF NOT EXISTS 'major'")
        op.execute("COMMIT")
        op.execute("UPDATE fault SET severity = 'warning' WHERE severity = 'warn'")
    else:
        # SQLite stores enums as VARCHAR with a CHECK constraint; the batch
        # rebuild below replaces the constraint, so the UPDATE must come first.
        op.execute("UPDATE fault SET severity = 'warning' WHERE severity = 'warn'")
        with op.batch_alter_table('fault') as batch:
            batch.alter_column(
                'severity',
                existing_type=sa.Enum(*_OLD_SEVERITY, name='fault_severity'),
                type_=sa.Enum(*_NEW_SEVERITY, name='fault_severity'),
                existing_nullable=False,
            )


def downgrade() -> None:
    op.drop_index(op.f('ix_alarms_severity'), table_name='alarms')

    with op.batch_alter_table('alarms') as batch:
        batch.add_column(sa.Column('major_id', sa.SmallInteger(), nullable=True))
        batch.add_column(sa.Column('sub_section', sa.SmallInteger(), nullable=True))
        batch.add_column(sa.Column('fault_type', sa.SmallInteger(), nullable=True))

    # Restore the (wrong) four-equal-bytes decode so the schema round-trips.
    op.execute(
        "UPDATE alarms SET "
        "  major_id = (alarm_code / 16777216) % 256, "
        "  sub_section = (alarm_code / 65536) % 256, "
        "  fault_type = (alarm_code / 256) % 256"
    )

    with op.batch_alter_table('alarms') as batch:
        batch.drop_column('severity')
    with op.batch_alter_table('alarms') as batch:
        batch.add_column(sa.Column('severity', sa.SmallInteger(), nullable=True))
    op.execute("UPDATE alarms SET severity = alarm_code % 256")

    with op.batch_alter_table('alarms') as batch:
        batch.alter_column('major_id', nullable=False)
        batch.alter_column('sub_section', nullable=False)
        batch.alter_column('fault_type', nullable=False)
        batch.alter_column('severity', nullable=False)
        batch.drop_column('domain')
        batch.drop_column('module')
        batch.drop_column('alarm_type')
        batch.drop_column('alarm_index')

    # fault.severity back to three levels; minor/major collapse to critical
    # (they are both more severe than warn, and info/warn are unchanged).
    op.execute("UPDATE fault SET severity = 'critical' WHERE severity IN ('minor', 'major')")
    op.execute("UPDATE fault SET severity = 'warn' WHERE severity = 'warning'")
    bind = op.get_bind()
    if bind.dialect.name != 'postgresql':
        with op.batch_alter_table('fault') as batch:
            batch.alter_column(
                'severity',
                existing_type=sa.Enum(*_NEW_SEVERITY, name='fault_severity'),
                type_=sa.Enum(*_OLD_SEVERITY, name='fault_severity'),
                existing_nullable=False,
            )
