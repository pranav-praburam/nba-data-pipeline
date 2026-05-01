"""v2_schema

Revision ID: 776a3c5cec05
Revises: 
Create Date: 2026-04-30 20:37:23.692255

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '776a3c5cec05'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('games', sa.Column('is_home', sa.Boolean(), nullable=True))
    op.execute(
        """
        UPDATE games
        SET is_home = CASE
            WHEN matchup LIKE '% vs. %' THEN TRUE
            WHEN matchup LIKE '% @ %' THEN FALSE
            ELSE NULL
        END
        """
    )

    op.create_table(
        'model_picks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('game_date', sa.String(), nullable=False),
        sa.Column('game_id', sa.String(), nullable=True),
        sa.Column('home_team', sa.String(), nullable=False),
        sa.Column('away_team', sa.String(), nullable=False),
        sa.Column('model_home_win_prob', sa.Float(), nullable=False),
        sa.Column('model_away_win_prob', sa.Float(), nullable=False),
        sa.Column('home_moneyline', sa.Integer(), nullable=True),
        sa.Column('away_moneyline', sa.Integer(), nullable=True),
        sa.Column('implied_home_win_prob', sa.Float(), nullable=True),
        sa.Column('implied_away_win_prob', sa.Float(), nullable=True),
        sa.Column('edge', sa.Float(), nullable=True),
        sa.Column('pick', sa.String(), nullable=True),
        sa.Column('confidence_tier', sa.String(), nullable=True),
        sa.Column('pick_reason', sa.Text(), nullable=True),
        sa.Column('actual_winner', sa.String(), nullable=True),
        sa.Column('correct', sa.Boolean(), nullable=True),
        sa.Column('settled', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('model_version', sa.String(), nullable=True),
        sa.Column('odds_source', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('settled_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('game_date', 'home_team', 'away_team', name='uq_model_picks_game_matchup'),
    )
    op.create_index(op.f('ix_model_picks_id'), 'model_picks', ['id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_model_picks_id'), table_name='model_picks')
    op.drop_table('model_picks')
    op.drop_column('games', 'is_home')
