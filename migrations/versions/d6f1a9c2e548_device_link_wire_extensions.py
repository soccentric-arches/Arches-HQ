"""device link wire extensions: C-02, C-06, C-08, C-12, F-05

Columns for the device↔HQ protocol work (Task.md group C), so the gateway
can receive what the retargeted device agent now sends:

C-02 -- device.authenticates-by-signing: ``device.agent_pubkey`` stores the
Ed25519 public key the device generated and presented at pairing. No bearer
credential column is added; new pairings simply issue none, and devices that
paired before this change keep authenticating with their stored credential
token until they re-pair.

C-06 -- alarm transport: ``alarms`` gains the aggregation fields the device's
alarm daemon already computed (owner, additional_text, count, acknowledged,
needs_snapshot, first/last seen) plus X.733 correlated notification ids, so
HQ stores the same fact the device holds instead of recounting occurrences.

C-08 -- telemetry metadata: ``telemetry_sample.unit`` and ``.metric_type``
carry through the device's metric registration instead of being dropped at
the boundary.

C-12 -- backup completion: ``backup.name``, ``.checksum_sha256``,
``.upload_completed_at`` and ``.success`` replace the size estimate stored
when the SignedUploadUrl was issued.

F-05 -- device health surfacing: ``device.health_score`` (0..1) and
``.spoke_status`` (JSON: per-spoke state summary) from the periodic
AgentReport document.

Revision ID: d6f1a9c2e548
Revises: b7e4d9a13c02
Create Date: 2026-09-17

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd6f1a9c2e548'
down_revision: Union[str, Sequence[str], None] = 'b7e4d9a13c02'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('device') as batch:
        batch.add_column(sa.Column('agent_pubkey', sa.String(), nullable=True))
        batch.add_column(sa.Column('health_score', sa.Float(), nullable=True))
        batch.add_column(sa.Column('spoke_status', sa.JSON(), nullable=True))

    with op.batch_alter_table('alarms') as batch:
        batch.add_column(sa.Column('owner', sa.String(), nullable=True))
        batch.add_column(sa.Column('additional_text', sa.Text(), nullable=True))
        batch.add_column(sa.Column('count', sa.Integer(), nullable=True))
        batch.add_column(
            sa.Column('acknowledged', sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch.add_column(
            sa.Column('needs_snapshot', sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch.add_column(sa.Column('first_seen_at', sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column('correlated', sa.JSON(), nullable=True))

    with op.batch_alter_table('telemetry_sample') as batch:
        batch.add_column(sa.Column('unit', sa.String(), nullable=True))
        batch.add_column(sa.Column('metric_type', sa.String(), nullable=True))

    with op.batch_alter_table('backup') as batch:
        batch.add_column(sa.Column('name', sa.String(), nullable=True))
        batch.add_column(sa.Column('checksum_sha256', sa.String(), nullable=True))
        batch.add_column(
            sa.Column('upload_completed_at', sa.DateTime(timezone=True), nullable=True)
        )
        batch.add_column(
            sa.Column('success', sa.Boolean(), nullable=False, server_default=sa.true())
        )


def downgrade() -> None:
    with op.batch_alter_table('backup') as batch:
        batch.drop_column('success')
        batch.drop_column('upload_completed_at')
        batch.drop_column('checksum_sha256')
        batch.drop_column('name')
    with op.batch_alter_table('telemetry_sample') as batch:
        batch.drop_column('metric_type')
        batch.drop_column('unit')
    with op.batch_alter_table('alarms') as batch:
        batch.drop_column('correlated')
        batch.drop_column('last_seen_at')
        batch.drop_column('first_seen_at')
        batch.drop_column('needs_snapshot')
        batch.drop_column('acknowledged')
        batch.drop_column('count')
        batch.drop_column('additional_text')
        batch.drop_column('owner')
    with op.batch_alter_table('device') as batch:
        batch.drop_column('spoke_status')
        batch.drop_column('health_score')
        batch.drop_column('agent_pubkey')