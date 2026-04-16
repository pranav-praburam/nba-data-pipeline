from html import escape
from urllib.parse import quote_plus

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.api.constants import NBA_TEAMS
from app.db.database import get_db
from app.db.models import ModelPrediction
from app.services.predictions import (
    predict_matchup_win_probability,
    recent_team_profile,
    record_model_prediction,
)


router = APIRouter()


TEAM_ALIASES = {
    team.lower(): team
    for team in NBA_TEAMS
}
# The portfolio UI accepts recruiter-friendly shorthand such as "Bulls" or
# "Thunder" while the database/model still use official NBA team names.
TEAM_ALIASES.update(
    {
        "76ers": "Philadelphia 76ers",
        "blazers": "Portland Trail Blazers",
        "bucks": "Milwaukee Bucks",
        "bulls": "Chicago Bulls",
        "cavs": "Cleveland Cavaliers",
        "cavaliers": "Cleveland Cavaliers",
        "celtics": "Boston Celtics",
        "clippers": "LA Clippers",
        "grizzlies": "Memphis Grizzlies",
        "hawks": "Atlanta Hawks",
        "heat": "Miami Heat",
        "hornets": "Charlotte Hornets",
        "jazz": "Utah Jazz",
        "kings": "Sacramento Kings",
        "knicks": "New York Knicks",
        "lakers": "Los Angeles Lakers",
        "magic": "Orlando Magic",
        "mavs": "Dallas Mavericks",
        "mavericks": "Dallas Mavericks",
        "nets": "Brooklyn Nets",
        "nuggets": "Denver Nuggets",
        "pacers": "Indiana Pacers",
        "pelicans": "New Orleans Pelicans",
        "pistons": "Detroit Pistons",
        "raptors": "Toronto Raptors",
        "rockets": "Houston Rockets",
        "sixers": "Philadelphia 76ers",
        "spurs": "San Antonio Spurs",
        "suns": "Phoenix Suns",
        "thunder": "Oklahoma City Thunder",
        "timberwolves": "Minnesota Timberwolves",
        "twolves": "Minnesota Timberwolves",
        "warriors": "Golden State Warriors",
        "wizards": "Washington Wizards",
        "wolves": "Minnesota Timberwolves",
    }
)


def resolve_team_name(team_name: str):
    # First try exact aliases, then allow a single unambiguous partial match.
    normalized = team_name.strip().lower()
    if normalized in TEAM_ALIASES:
        return TEAM_ALIASES[normalized]

    matches = [
        team
        for team in NBA_TEAMS
        if normalized and normalized in team.lower()
    ]
    if len(matches) == 1:
        return matches[0]
    return None


@router.get("/predictions/matchup")
def matchup_prediction(
    team_a: str,
    team_b: str,
    last_n: int = Query(default=10, ge=3, le=25),
    db: Session = Depends(get_db),
):
    # Machine-readable endpoint: resolves names, serves the model prediction, and
    # records the request so /predictions/history can show real model usage.
    resolved_team_a = resolve_team_name(team_a)
    resolved_team_b = resolve_team_name(team_b)
    unresolved = []
    if not resolved_team_a:
        unresolved.append(team_a)
    if not resolved_team_b:
        unresolved.append(team_b)
    if unresolved:
        raise HTTPException(
            status_code=404,
            detail=f"Could not resolve NBA team name: {', '.join(unresolved)}",
        )

    prediction = predict_matchup_win_probability(db, resolved_team_a, resolved_team_b, last_n)
    if prediction:
        saved_prediction = record_model_prediction(db, prediction)
        return {
            **prediction,
            "prediction_id": saved_prediction.id,
            "disclaimer": "Baseline ML model trained on historical rolling team form. This is for portfolio/demo use and is not betting advice.",
        }

    missing = []
    team_a_profile = recent_team_profile(db, resolved_team_a, last_n)
    team_b_profile = recent_team_profile(db, resolved_team_b, last_n)
    if not team_a_profile:
        missing.append(team_a)
    if not team_b_profile:
        missing.append(team_b)

    raise HTTPException(
        status_code=404,
        detail=f"No recent games found for: {', '.join(missing)}",
    )


@router.get("/predict")
def prediction_page(
    team_a: str = "Bulls",
    team_b: str = "Lakers",
    last_n: int = Query(default=10, ge=3, le=25),
    db: Session = Depends(get_db),
):
    # Human-readable wrapper around the same prediction path. This keeps the visual
    # page and JSON API consistent instead of duplicating model-serving logic.
    result = matchup_prediction(team_a=team_a, team_b=team_b, last_n=last_n, db=db)
    teams = list(result["win_probability"].keys())
    team_a_name, team_b_name = teams[0], teams[1]
    team_a_probability = result["win_probability"][team_a_name]
    team_b_probability = result["win_probability"][team_b_name]
    favorite = result["favorite"]
    safe_team_a_input = escape(team_a)
    safe_team_b_input = escape(team_b)
    safe_team_a_name = escape(team_a_name)
    safe_team_b_name = escape(team_b_name)
    safe_favorite = escape(favorite)
    raw_json_link = (
        f"/predictions/matchup?team_a={quote_plus(team_a_name)}"
        f"&team_b={quote_plus(team_b_name)}&last_n={last_n}"
    )

    return HTMLResponse(
        f"""
        <!doctype html>
        <html lang="en">
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <title>NBA Matchup Predictor</title>
            <style>
                :root {{
                    --ink: #17202a;
                    --muted: #64748b;
                    --court: #edb458;
                    --paint: #174ea6;
                    --rim: #d1495b;
                    --paper: #fffaf0;
                    --line: rgba(23, 32, 42, 0.14);
                }}
                * {{ box-sizing: border-box; }}
                body {{
                    margin: 0;
                    min-height: 100vh;
                    font-family: Georgia, "Times New Roman", serif;
                    color: var(--ink);
                    background:
                        linear-gradient(90deg, rgba(23, 78, 166, 0.08) 1px, transparent 1px),
                        linear-gradient(0deg, rgba(23, 78, 166, 0.08) 1px, transparent 1px),
                        radial-gradient(circle at 12% 10%, rgba(237, 180, 88, 0.58), transparent 28rem),
                        linear-gradient(135deg, #fff8ea 0%, #e8f1ff 100%);
                    background-size: 48px 48px, 48px 48px, auto, auto;
                }}
                main {{
                    width: min(980px, calc(100% - 32px));
                    margin: 0 auto;
                    padding: 44px 0;
                }}
                .card {{
                    background: rgba(255, 250, 240, 0.9);
                    border: 1px solid var(--line);
                    border-radius: 30px;
                    box-shadow: 0 24px 80px rgba(23, 32, 42, 0.12);
                    padding: 28px;
                    backdrop-filter: blur(10px);
                }}
                h1 {{
                    margin: 0 0 14px;
                    font-size: clamp(2.4rem, 7vw, 5rem);
                    line-height: 0.9;
                    letter-spacing: -0.075em;
                }}
                .eyebrow {{
                    color: var(--paint);
                    font-weight: 700;
                    letter-spacing: 0.16em;
                    text-transform: uppercase;
                    font-size: 0.8rem;
                }}
                p {{ color: var(--muted); line-height: 1.65; }}
                form {{
                    display: grid;
                    grid-template-columns: 1fr 1fr 120px auto;
                    gap: 12px;
                    margin: 24px 0;
                    align-items: end;
                }}
                label {{
                    display: grid;
                    gap: 6px;
                    color: var(--muted);
                    font-weight: 700;
                }}
                input {{
                    width: 100%;
                    border: 1px solid var(--line);
                    border-radius: 16px;
                    background: #fff;
                    color: var(--ink);
                    font: inherit;
                    padding: 12px 14px;
                }}
                button, a.button {{
                    border: 0;
                    border-radius: 999px;
                    background: var(--court);
                    color: #17202a;
                    cursor: pointer;
                    display: inline-block;
                    font: inherit;
                    font-weight: 700;
                    padding: 13px 16px;
                    text-decoration: none;
                }}
                .result {{
                    display: grid;
                    grid-template-columns: 1fr 1fr;
                    gap: 18px;
                    margin-top: 22px;
                }}
                .winner {{
                    grid-column: 1 / -1;
                    background: linear-gradient(135deg, #17202a, #174ea6);
                    color: #fff;
                    border-radius: 24px;
                    padding: 24px;
                }}
                .winner strong {{
                    display: block;
                    font-size: clamp(2rem, 6vw, 4rem);
                    letter-spacing: -0.06em;
                    line-height: 0.95;
                }}
                .probability {{
                    background: #fff;
                    border: 1px solid var(--line);
                    border-radius: 20px;
                    padding: 18px;
                }}
                .probability strong {{
                    display: block;
                    font-size: 2.2rem;
                    letter-spacing: -0.05em;
                }}
                .bar {{
                    height: 12px;
                    background: rgba(23, 78, 166, 0.12);
                    border-radius: 999px;
                    margin-top: 12px;
                    overflow: hidden;
                }}
                .bar span {{
                    display: block;
                    height: 100%;
                    background: linear-gradient(90deg, var(--paint), var(--rim));
                    border-radius: inherit;
                }}
                nav {{ display: flex; gap: 12px; flex-wrap: wrap; margin-top: 22px; }}
                nav a {{ color: var(--paint); font-weight: 700; text-decoration: none; }}
                @media (max-width: 760px) {{
                    form, .result {{ grid-template-columns: 1fr; }}
                    .winner {{ grid-column: auto; }}
                }}
            </style>
        </head>
        <body>
            <main>
                <section class="card">
                    <div class="eyebrow">Interactive ML Endpoint</div>
                    <h1>NBA Matchup Predictor</h1>
                    <p>
                        Enter full team names or short names like Bulls, Lakers, Heat, Thunder, or Knicks.
                        The model uses each team's recent form and returns win probabilities.
                    </p>
                    <form action="/predict" method="get">
                        <label>Team A
                            <input name="team_a" value="{safe_team_a_input}" placeholder="Bulls">
                        </label>
                        <label>Team B
                            <input name="team_b" value="{safe_team_b_input}" placeholder="Lakers">
                        </label>
                        <label>Last N
                            <input name="last_n" type="number" min="3" max="25" value="{last_n}">
                        </label>
                        <button type="submit">Predict</button>
                    </form>
                    <div class="result">
                        <div class="winner">
                            <span class="eyebrow">Predicted Winner</span>
                            <strong>{safe_favorite}</strong>
                            <p>Model: {result["model_type"]} | Accuracy: {result["training_metrics"].get("accuracy")}</p>
                        </div>
                        <div class="probability">
                            <span>{safe_team_a_name}</span>
                            <strong>{team_a_probability:.1%}</strong>
                            <div class="bar"><span style="width: {team_a_probability * 100:.1f}%"></span></div>
                        </div>
                        <div class="probability">
                            <span>{safe_team_b_name}</span>
                            <strong>{team_b_probability:.1%}</strong>
                            <div class="bar"><span style="width: {team_b_probability * 100:.1f}%"></span></div>
                        </div>
                    </div>
                    <nav>
                        <a href="/dashboard">Dashboard</a>
                        <a href="/predictions/history?limit=10">Prediction History</a>
                        <a href="{raw_json_link}">Raw JSON</a>
                        <a href="/">Home</a>
                    </nav>
                </section>
            </main>
        </body>
        </html>
        """
    )


@router.get("/predictions/history")
def prediction_history(
    limit: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    # Simple serving audit trail for demos: latest predictions, model version, and
    # probabilities are queryable without digging through logs.
    predictions = (
        db.query(ModelPrediction)
        .order_by(ModelPrediction.created_at.desc(), ModelPrediction.id.desc())
        .limit(limit)
        .all()
    )

    return [
        {
            "id": prediction.id,
            "model_name": prediction.model_name,
            "model_version": prediction.model_version,
            "team_a": prediction.team_a,
            "team_b": prediction.team_b,
            "favorite": prediction.favorite,
            "win_probability": {
                prediction.team_a: round(prediction.team_a_probability, 3),
                prediction.team_b: round(prediction.team_b_probability, 3),
            },
            "last_n_games": prediction.last_n_games,
            "created_at": prediction.created_at,
        }
        for prediction in predictions
    ]
