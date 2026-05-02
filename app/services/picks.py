from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Iterable, Optional

from sqlalchemy.orm import Session

from app.db.models import Game, ModelPick
from app.services.odds import NormalizedOddsEvent, fetch_odds, parse_moneyline_events
from app.services.predictions import predict_matchup_win_probability


def _iso_date_from_commence_time(commence_time: str) -> str:
    # Odds API returns ISO timestamps (UTC). We store game_date as YYYY-MM-DD,
    # which matches the existing `games.game_date` format.
    return commence_time[:10]


def _confidence_tier(edge: float) -> str:
    edge_abs = abs(edge)
    if edge_abs >= 0.08:
        return "high"
    if edge_abs >= 0.05:
        return "medium"
    if edge_abs >= 0.03:
        return "low"
    return "none"


def generate_model_picks(
    db: Session,
    *,
    target_date: Optional[str] = None,
    last_n: int = 10,
    edge_threshold: float = 0.03,
    odds_events: Optional[Iterable[NormalizedOddsEvent]] = None,
) -> dict:
    """
    Create or update today's model picks.

    Idempotency: `model_picks` has UNIQUE(game_date, home_team, away_team). If a
    pick already exists and is not settled, we update it in-place so repeated
    runs refine odds/model fields without duplicating rows.
    """
    if odds_events is None:
        raw = fetch_odds()
        odds_events = parse_moneyline_events(raw)

    inserted = 0
    updated = 0
    skipped = 0

    for event in odds_events:
        game_date = target_date or _iso_date_from_commence_time(event.commence_time)
        if target_date and game_date != target_date:
            continue

        # Model endpoint assumes "team_a" is home and "team_b" is away.
        prediction = predict_matchup_win_probability(db, event.home_team, event.away_team, last_n)
        if not prediction:
            skipped += 1
            continue

        model_home = float(prediction["win_probability"][event.home_team])
        model_away = float(prediction["win_probability"][event.away_team])

        implied_home = float(event.implied_home_win_prob)
        implied_away = float(event.implied_away_win_prob)
        edge_home = model_home - implied_home
        edge_away = model_away - implied_away

        if max(edge_home, edge_away) < edge_threshold:
            skipped += 1
            continue

        pick = event.home_team if edge_home >= edge_away else event.away_team
        edge = max(edge_home, edge_away)
        tier = _confidence_tier(edge)
        reason = (
            f"Model prob {model_home:.3f}/{model_away:.3f} vs implied "
            f"{implied_home:.3f}/{implied_away:.3f} (edge={edge:.3f})."
        )

        existing = (
            db.query(ModelPick)
            .filter(ModelPick.game_date == game_date)
            .filter(ModelPick.home_team == event.home_team)
            .filter(ModelPick.away_team == event.away_team)
            .first()
        )

        payload = dict(
            game_date=game_date,
            game_id=event.game_id,
            home_team=event.home_team,
            away_team=event.away_team,
            model_home_win_prob=model_home,
            model_away_win_prob=model_away,
            home_moneyline=event.home_moneyline,
            away_moneyline=event.away_moneyline,
            implied_home_win_prob=implied_home,
            implied_away_win_prob=implied_away,
            edge=edge,
            pick=pick,
            confidence_tier=tier,
            pick_reason=reason,
            model_version=prediction.get("model_version"),
            odds_source=event.odds_source,
        )

        if existing:
            if existing.settled:
                skipped += 1
                continue
            for key, value in payload.items():
                setattr(existing, key, value)
            updated += 1
        else:
            db.add(ModelPick(**payload))
            inserted += 1

    db.commit()
    return {
        "status": "success",
        "mode": "upsert",
        "target_date": target_date,
        "rows_inserted": inserted,
        "rows_updated": updated,
        "rows_skipped": skipped,
    }


def settle_model_picks(
    db: Session,
    *,
    settle_before_date: Optional[str] = None,
) -> dict:
    """
    Settle any picks with results available in the `games` table.

    Settlement uses (game_date, home_team, away_team) matching, then checks the
    home team W/L result to determine the winner.
    """
    now = datetime.now(timezone.utc)
    settle_cutoff = settle_before_date
    if not settle_cutoff:
        # Default: settle anything strictly before today (UTC).
        settle_cutoff = date.today().isoformat()

    picks = (
        db.query(ModelPick)
        .filter(ModelPick.settled.is_(False))
        .filter(ModelPick.game_date < settle_cutoff)
        .order_by(ModelPick.game_date.asc(), ModelPick.id.asc())
        .all()
    )

    settled = 0
    missing_results = 0

    for pick in picks:
        home_row = (
            db.query(Game)
            .filter(Game.game_date == pick.game_date)
            .filter(Game.team == pick.home_team)
            .filter(Game.opponent == pick.away_team)
            .filter(Game.is_home.is_(True))
            .first()
        )
        away_row = (
            db.query(Game)
            .filter(Game.game_date == pick.game_date)
            .filter(Game.team == pick.away_team)
            .filter(Game.opponent == pick.home_team)
            .filter(Game.is_home.is_(False))
            .first()
        )
        if not home_row or not away_row:
            missing_results += 1
            continue

        actual_winner = pick.home_team if home_row.wl == "W" else pick.away_team
        pick.actual_winner = actual_winner
        pick.correct = pick.pick == actual_winner if pick.pick else None
        pick.settled = True
        pick.settled_at = now
        pick.game_id = home_row.game_id
        settled += 1

    db.commit()
    return {
        "status": "success",
        "settled_count": settled,
        "missing_results_count": missing_results,
        "settle_before_date": settle_cutoff,
    }


def serialize_pick(pick: ModelPick) -> dict:
    return {
        "id": pick.id,
        "game_date": pick.game_date,
        "game_id": pick.game_id,
        "home_team": pick.home_team,
        "away_team": pick.away_team,
        "model_home_win_prob": pick.model_home_win_prob,
        "model_away_win_prob": pick.model_away_win_prob,
        "home_moneyline": pick.home_moneyline,
        "away_moneyline": pick.away_moneyline,
        "implied_home_win_prob": pick.implied_home_win_prob,
        "implied_away_win_prob": pick.implied_away_win_prob,
        "edge": pick.edge,
        "pick": pick.pick,
        "confidence_tier": pick.confidence_tier,
        "pick_reason": pick.pick_reason,
        "actual_winner": pick.actual_winner,
        "correct": pick.correct,
        "settled": pick.settled,
        "model_version": pick.model_version,
        "odds_source": pick.odds_source,
        "created_at": pick.created_at,
        "settled_at": pick.settled_at,
    }
