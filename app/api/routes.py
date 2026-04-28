from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy import func
from sqlalchemy.orm import Session
from typing import Optional
from html import escape
from urllib.parse import quote_plus
from app.api.admin import router as admin_router
from app.api.analytics import router as analytics_router
from app.api.analytics import team_rankings
from app.api.games import router as games_router
from app.api.pipeline import router as pipeline_router
from app.api.pipeline import get_pipeline_runs
from app.api.predictions import router as predictions_router
from app.api.query_helpers import (
    latest_season_year,
    nba_team_query,
    normalize_season_year,
    season_display_name,
    season_query,
)
from app.db.database import get_db
from app.db.models import Game
from app.services.predictions import load_win_probability_metrics, predict_matchup_win_probability

router = APIRouter()
router.include_router(games_router)
router.include_router(analytics_router)
router.include_router(predictions_router)
router.include_router(pipeline_router)
router.include_router(admin_router)

@router.get("/")
def home(db: Session = Depends(get_db)):
    # The landing page uses live database/model metadata so the portfolio homepage
    # proves the pipeline is deployed, populated, and model-backed.
    total_rows = nba_team_query(db.query(func.count(Game.id))).scalar() or 0
    unique_games = nba_team_query(db.query(func.count(func.distinct(Game.game_id)))).scalar() or 0
    latest_run = get_pipeline_runs(limit=1, db=db)
    run_status = latest_run[0].get("status", "unknown") if latest_run else "unknown"
    model_metrics = load_win_probability_metrics()
    model_accuracy = model_metrics.get("accuracy", "n/a")
    model_precision = model_metrics.get("precision", "n/a")
    # Keep this as a normal template string with placeholders because CSS braces
    # are much easier to maintain here than inside one large f-string.
    html = """
        <!doctype html>
        <html lang="en">
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <title>NBA Data Pipeline</title>
            <style>
                :root {
                    --bg: #fdfefe;
                    --ink: #23485f;
                    --muted: #6f93a8;
                    --aqua: #a7edf0;
                    --sky: #c5e7ff;
                    --mint: #dcf7ec;
                    --ice: #eefaff;
                    --line: rgba(151, 204, 232, 0.42);
                    --shadow: rgba(129, 189, 219, 0.16);
                    --font-display: "Avenir Next", "Trebuchet MS", "Segoe UI", "Helvetica Neue", Arial, sans-serif;
                    --font-body: "Avenir Next", "Trebuchet MS", "Segoe UI", "Helvetica Neue", Arial, sans-serif;
                    --font-mono: "SFMono-Regular", "SF Mono", "IBM Plex Mono", "Cascadia Code", Consolas, monospace;
                }
                * { box-sizing: border-box; }
                body {
                    margin: 0;
                    font-family: var(--font-body);
                    color: var(--ink);
                    background:
                        radial-gradient(circle at 18% 12%, rgba(167, 237, 240, 0.65), transparent 18rem),
                        radial-gradient(circle at 84% 16%, rgba(197, 231, 255, 0.75), transparent 18rem),
                        linear-gradient(180deg, #ffffff 0%, #f4fbff 50%, #edf8ff 100%);
                    min-height: 100vh;
                }
                main {
                    width: min(1120px, calc(100% - 32px));
                    margin: 0 auto;
                    padding: 48px 0;
                }
                .hero {
                    display: grid;
                    grid-template-columns: 1.3fr 0.7fr;
                    gap: 28px;
                    align-items: stretch;
                }
                .card {
                    background:
                        linear-gradient(180deg, rgba(255, 255, 255, 0.96), rgba(245, 252, 255, 0.92));
                    border: 1px solid var(--line);
                    border-radius: 28px;
                    box-shadow:
                        0 18px 48px var(--shadow),
                        inset 0 1px 0 rgba(255, 255, 255, 0.9);
                    padding: 28px;
                    backdrop-filter: blur(10px);
                }
                h1 {
                    font-family: var(--font-display);
                    font-weight: 700;
                    font-size: clamp(2.4rem, 8vw, 5.8rem);
                    line-height: 0.92;
                    letter-spacing: -0.06em;
                    margin: 0 0 20px;
                }
                h2 {
                    font-family: var(--font-mono);
                    font-weight: 600;
                    font-size: 1.1rem;
                    text-transform: uppercase;
                    letter-spacing: 0.18em;
                    margin: 0 0 18px;
                    color: #72cdd7;
                }
                p {
                    font-size: 1.08rem;
                    line-height: 1.7;
                    color: var(--muted);
                    max-width: 62ch;
                }
                .metric-grid {
                    display: grid;
                    grid-template-columns: repeat(4, minmax(0, 1fr));
                    gap: 16px;
                    margin-top: 28px;
                }
                .metric {
                    border: 1px solid var(--line);
                    border-radius: 20px;
                    padding: 18px;
                    background: linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(239, 249, 255, 0.92));
                }
                .metric strong {
                    font-family: var(--font-display);
                    font-weight: 700;
                    display: block;
                    font-size: 2rem;
                    letter-spacing: -0.05em;
                }
                .metric span {
                    font-family: var(--font-mono);
                    color: var(--muted);
                    font-size: 0.9rem;
                }
                .court {
                    position: relative;
                    min-height: 340px;
                    overflow: hidden;
                    background:
                        radial-gradient(circle at 18% 16%, rgba(167, 237, 240, 0.7), transparent 11rem),
                        radial-gradient(circle at 84% 12%, rgba(220, 247, 236, 0.8), transparent 10rem),
                        linear-gradient(180deg, rgba(255, 255, 255, 0.85), rgba(229, 246, 255, 0.9)),
                        linear-gradient(180deg, #eefaff, #ffffff);
                }
                .court::before {
                    content: "";
                    position: absolute;
                    inset: 30px;
                    border: 3px solid rgba(113, 201, 227, 0.8);
                    border-radius: 24px;
                }
                .court::after {
                    content: "";
                    position: absolute;
                    width: 190px;
                    height: 190px;
                    border: 3px solid rgba(113, 201, 227, 0.76);
                    border-radius: 999px;
                    left: 50%;
                    top: 50%;
                    transform: translate(-50%, -50%);
                }
                .shot {
                    position: absolute;
                    width: 14px;
                    height: 14px;
                    border-radius: 999px;
                    background: linear-gradient(180deg, #72dbe8, #9ecfff);
                    box-shadow: 0 0 0 9px rgba(255, 255, 255, 0.75);
                    animation: pop 900ms ease both;
                }
                .shot:nth-child(1) { left: 22%; top: 30%; }
                .shot:nth-child(2) { left: 68%; top: 42%; animation-delay: 120ms; }
                .shot:nth-child(3) { left: 42%; top: 68%; animation-delay: 240ms; }
                .shot:nth-child(4) { left: 78%; top: 72%; animation-delay: 360ms; }
                .links {
                    display: grid;
                    grid-template-columns: repeat(2, minmax(0, 1fr));
                    gap: 14px;
                    margin-top: 22px;
                }
                a {
                    font-family: var(--font-body);
                    color: #4d8fb5;
                    font-weight: 700;
                    text-decoration: none;
                }
                .link-card {
                    display: block;
                    border: 1px solid var(--line);
                    border-radius: 18px;
                    background: linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(236, 248, 255, 0.92));
                    padding: 16px;
                    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.95);
                }
                .primary-link {
                    display: inline-block;
                    color: #2f657f;
                    background: linear-gradient(180deg, #ffffff, #dff5ff);
                    border: 1px solid rgba(120, 198, 233, 0.45);
                    border-radius: 999px;
                    box-shadow:
                        0 12px 28px rgba(129, 189, 219, 0.18),
                        inset 0 1px 0 rgba(255, 255, 255, 0.95);
                    padding: 14px 18px;
                    margin: 6px 10px 8px 0;
                }
                .secondary-link {
                    display: inline-block;
                    border: 1px solid var(--line);
                    border-radius: 999px;
                    background: linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(241, 250, 255, 0.92));
                    padding: 14px 18px;
                    margin: 6px 0 8px;
                    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.95);
                }
                .cta-row { margin-top: 22px; }
                @keyframes pop {
                    from { opacity: 0; transform: scale(0.3); }
                    to { opacity: 1; transform: scale(1); }
                }
                @media (max-width: 780px) {
                    .hero, .metric-grid, .links { grid-template-columns: 1fr; }
                    main { padding: 24px 0; }
                }
            </style>
        </head>
        <body>
            <main>
                <section class="hero">
                    <div class="card">
                        <h2>Deployed Data Engineering Project</h2>
                        <h1>NBA Data Pipeline</h1>
                        <p>
                            A FastAPI + PostgreSQL pipeline that ingests NBA game data,
                            tracks pipeline runs, serves analytics endpoints, and powers
                            a model-backed matchup prediction dashboard.
                        </p>
                        <div class="cta-row">
                            <a class="primary-link" href="/dashboard">Open Live Dashboard</a>
                            <a class="secondary-link" href="/predict">Try ML Prediction</a>
                        </div>
                        <div class="metric-grid">
                            <div class="metric"><strong>__TOTAL_ROWS__</strong><span>official team-game rows</span></div>
                            <div class="metric"><strong>__UNIQUE_GAMES__</strong><span>unique games modeled</span></div>
                            <div class="metric"><strong>__MODEL_ACCURACY__</strong><span>ML holdout accuracy</span></div>
                            <div class="metric"><strong>__MODEL_PRECISION__</strong><span>ML holdout precision</span></div>
                        </div>
                        <div class="links">
                            <a class="link-card" href="/dashboard">Dashboard</a>
                            <a class="link-card" href="/docs">Interactive API Docs</a>
                            <a class="link-card" href="/games?limit=5">Recent Games</a>
                            <a class="link-card" href="/analytics/team-rankings?metric=points&limit=10&season=2025-26">Team Rankings</a>
                            <a class="link-card" href="/teams/Indiana%20Pacers/trends?last_n=5">Pacers Trend Analysis</a>
                            <a class="link-card" href="/predictions/history?limit=10">Prediction History</a>
                            <a class="link-card" href="/pipeline/runs?limit=3">Pipeline Runs</a>
                            <a class="link-card" href="/data-quality/summary">Data Quality</a>
                        </div>
                        <p class="eyebrow">Latest pipeline status: __RUN_STATUS__</p>
                    </div>
                    <div class="card court" aria-label="Basketball court visualization">
                        <span class="shot"></span>
                        <span class="shot"></span>
                        <span class="shot"></span>
                        <span class="shot"></span>
                    </div>
                </section>
            </main>
        </body>
        </html>
        """
    return HTMLResponse(
        html.replace("__TOTAL_ROWS__", f"{total_rows:,}")
        .replace("__UNIQUE_GAMES__", f"{unique_games:,}")
        .replace("__MODEL_ACCURACY__", str(model_accuracy))
        .replace("__MODEL_PRECISION__", str(model_precision))
        .replace("__RUN_STATUS__", escape(str(run_status)))
    )

@router.get("/health")
def health():
    return {"status": "ok"}

@router.get("/dashboard")
def dashboard(
    season: Optional[str] = None,
    team_a: str = "Indiana Pacers",
    team_b: str = "Oklahoma City Thunder",
    last_n: int = 10,
    db: Session = Depends(get_db),
):
    # Server-rendered dashboard for the resume/demo path. It reuses the same API
    # helper functions as the JSON endpoints so charts, stats, and endpoints agree.
    season_year = normalize_season_year(season) or latest_season_year(db)
    season_label = season_display_name(season_year)
    top_scoring_teams = team_rankings(metric="points", limit=8, season=season_year, db=db)
    three_point_teams = team_rankings(metric="fg3_pct", limit=5, season=season_year, db=db)
    recent_games = (
        season_query(nba_team_query(db.query(Game)), season_year)
        .order_by(Game.game_date.desc(), Game.game_id.desc(), Game.team_id.asc())
        .limit(8)
        .all()
    )
    latest_run = get_pipeline_runs(limit=1, db=db)
    model_prediction = predict_matchup_win_probability(
        db=db,
        team_a=team_a,
        team_b=team_b,
        last_n=last_n,
    )
    model_metrics = load_win_probability_metrics()
    total_rows = nba_team_query(db.query(func.count(Game.id))).scalar() or 0
    unique_games = nba_team_query(db.query(func.count(func.distinct(Game.game_id)))).scalar() or 0
    latest_game_date = season_query(nba_team_query(db.query(func.max(Game.game_date))), season_year).scalar()

    max_points = max((team["average"] for team in top_scoring_teams), default=1)
    points_rows = "\n".join(
        f"""
        <div class="bar-row">
            <span>{team["rank"]}. {escape(team["team"])}</span>
            <div class="bar-track">
                <div class="bar-fill" style="width: {(team["average"] / max_points) * 100:.1f}%"></div>
            </div>
            <strong>{team["average"]}</strong>
        </div>
        """
        for team in top_scoring_teams
    )
    three_point_rows = "\n".join(
        f"<li><span>{escape(team['team'])}</span><strong>{team['average']}</strong></li>"
        for team in three_point_teams
    )
    game_rows = "\n".join(
        f"""
        <tr>
            <td>{escape(game.game_date)}</td>
            <td>{escape(game.team)}</td>
            <td>{escape(game.opponent)}</td>
            <td>{escape(game.wl or "")}</td>
            <td>{game.points}</td>
        </tr>
        """
        for game in recent_games
    )
    run = latest_run[0] if latest_run else {}
    run_status = escape(str(run.get("status", "unknown")))
    rows_inserted = run.get("rows_inserted", 0)
    completed_at = escape(str(run.get("completed_at", "not available")))
    model_accuracy = model_metrics.get("accuracy", "n/a")
    model_precision = model_metrics.get("precision", "n/a")
    model_auc = model_metrics.get("roc_auc", "n/a")
    high_confidence_accuracy = model_metrics.get("high_confidence_accuracy", "n/a")
    high_confidence_coverage = model_metrics.get("high_confidence_coverage", "n/a")
    model_rows = model_metrics.get("rows_total", "n/a")
    safe_team_a = escape(team_a)
    safe_team_b = escape(team_b)
    safe_last_n = max(3, min(last_n, 25))
    prediction_link = (
        f"/predictions/matchup?team_a={quote_plus(team_a)}"
        f"&team_b={quote_plus(team_b)}&last_n={safe_last_n}"
    )
    # The dashboard prediction is intentionally lightweight: users can edit teams
    # directly on the page, while the deeper/raw response remains one click away.
    if model_prediction:
        favorite = escape(model_prediction["favorite"])
        team_a_probability = model_prediction["win_probability"].get(team_a, 0)
        team_b_probability = model_prediction["win_probability"].get(team_b, 0)
        prediction_summary = (
            f"<span class=\"label\">Predicted winner</span>"
            f"<strong>{favorite}</strong>"
            f"<span>Home: {safe_team_a} {team_a_probability:.1%} | "
            f"Away: {safe_team_b} {team_b_probability:.1%}</span>"
        )
    else:
        prediction_summary = (
            "<span class=\"label\">Prediction unavailable</span>"
            "<strong>Need recent games</strong>"
            "<span>Try two official NBA team names with recent data.</span>"
        )

    return HTMLResponse(
        f"""
        <!doctype html>
        <html lang="en">
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <title>NBA Analytics Dashboard</title>
            <style>
                :root {{
                    --bg: #fdfefe;
                    --ink: #23485f;
                    --muted: #6f93a8;
                    --aqua: #a7edf0;
                    --sky: #c5e7ff;
                    --mint: #dcf7ec;
                    --ice: #eefaff;
                    --panel: rgba(255, 255, 255, 0.95);
                    --panel-soft: rgba(243, 251, 255, 0.94);
                    --line: rgba(151, 204, 232, 0.42);
                    --shadow: rgba(129, 189, 219, 0.14);
                    --font-display: "Avenir Next", "Trebuchet MS", "Segoe UI", "Helvetica Neue", Arial, sans-serif;
                    --font-body: "Avenir Next", "Trebuchet MS", "Segoe UI", "Helvetica Neue", Arial, sans-serif;
                    --font-mono: "SFMono-Regular", "SF Mono", "IBM Plex Mono", "Cascadia Code", Consolas, monospace;
                }}
                * {{ box-sizing: border-box; }}
                body {{
                    margin: 0;
                    font-family: var(--font-body);
                    color: var(--ink);
                    background:
                        linear-gradient(90deg, rgba(188, 224, 245, 0.12) 1px, transparent 1px),
                        linear-gradient(0deg, rgba(188, 224, 245, 0.12) 1px, transparent 1px),
                        radial-gradient(circle at 14% 12%, rgba(167, 237, 240, 0.68), transparent 18rem),
                        radial-gradient(circle at 86% 16%, rgba(197, 231, 255, 0.72), transparent 17rem),
                        linear-gradient(180deg, #ffffff 0%, #f4fbff 48%, #eef8ff 100%);
                    background-size: 48px 48px, 48px 48px, auto, auto, auto;
                    min-height: 100vh;
                }}
                main {{
                    width: min(1180px, calc(100% - 32px));
                    margin: 0 auto;
                    padding: 42px 0;
                }}
                .topline {{
                    display: flex;
                    justify-content: space-between;
                    gap: 18px;
                    align-items: end;
                    margin-bottom: 24px;
                }}
                h1 {{
                    margin: 0;
                    font-family: var(--font-display);
                    font-weight: 700;
                    font-size: clamp(2.4rem, 7vw, 5rem);
                    line-height: 0.92;
                    letter-spacing: -0.055em;
                }}
                .eyebrow {{
                    color: #72cdd7;
                    font-family: var(--font-mono);
                    font-weight: 700;
                    letter-spacing: 0.16em;
                    text-transform: uppercase;
                    font-size: 0.8rem;
                }}
                a {{ color: #4d8fb5; font-family: var(--font-body); font-weight: 700; text-decoration: none; }}
                .grid {{
                    display: grid;
                    grid-template-columns: 1.35fr 0.65fr;
                    gap: 22px;
                }}
                .hero-strip {{
                    display: grid;
                    grid-template-columns: repeat(4, minmax(0, 1fr));
                    gap: 14px;
                    margin-bottom: 22px;
                }}
                .card {{
                    background:
                        linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(243, 251, 255, 0.94)),
                        var(--panel);
                    border: 1px solid var(--line);
                    border-radius: 28px;
                    box-shadow:
                        0 18px 46px var(--shadow),
                        inset 0 1px 0 rgba(255, 255, 255, 0.96);
                    padding: 24px;
                    backdrop-filter: blur(10px);
                }}
                h2 {{ margin: 0 0 18px; font-family: var(--font-display); font-size: 1.1rem; font-weight: 650; letter-spacing: -0.01em; }}
                .bar-row {{
                    display: grid;
                    grid-template-columns: 190px 1fr 64px;
                    gap: 12px;
                    align-items: center;
                    margin: 14px 0;
                }}
                .bar-track {{
                    height: 16px;
                    background: rgba(197, 231, 255, 0.52);
                    border-radius: 999px;
                    overflow: hidden;
                }}
                .bar-fill {{
                    height: 100%;
                    background: linear-gradient(90deg, #9be7ee, #b5dcff);
                    border-radius: inherit;
                }}
                .stat {{
                    background: linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(241, 250, 255, 0.94));
                    border: 1px solid var(--line);
                    border-radius: 20px;
                    padding: 18px;
                    margin-bottom: 16px;
                    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.95);
                }}
                .stat strong {{ display: block; font-size: 2rem; letter-spacing: -0.05em; }}
                .stat strong, .mini-stat strong {{ font-family: var(--font-display); font-weight: 700; }}
                .stat span {{ color: var(--muted); font-family: var(--font-mono); }}
                .mini-stat {{
                    background: linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(241, 250, 255, 0.94));
                    border: 1px solid var(--line);
                    border-radius: 22px;
                    padding: 16px;
                    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.95);
                }}
                .mini-stat strong {{
                    display: block;
                    font-size: 1.7rem;
                    letter-spacing: -0.05em;
                }}
                .mini-stat span {{
                    font-family: var(--font-mono);
                    color: var(--muted);
                    font-size: 0.9rem;
                }}
                .prediction-card {{
                    margin-top: 16px;
                    background:
                        radial-gradient(circle at top left, rgba(167, 237, 240, 0.7), transparent 10rem),
                        radial-gradient(circle at top right, rgba(197, 231, 255, 0.7), transparent 10rem),
                        linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(239, 249, 255, 0.94));
                    color: var(--ink);
                }}
                .prediction-card p {{
                    color: var(--muted);
                    line-height: 1.55;
                }}
                .prediction-card a {{
                    display: inline-block;
                    color: #2f657f;
                    background: linear-gradient(180deg, #ffffff, #dff5ff);
                    border-radius: 999px;
                    padding: 10px 14px;
                    margin-top: 6px;
                    box-shadow: 0 12px 24px rgba(129, 189, 219, 0.16);
                }}
                .prediction-result {{
                    display: grid;
                    gap: 4px;
                    background: rgba(255, 255, 255, 0.64);
                    border: 1px solid rgba(120, 198, 233, 0.28);
                    border-radius: 18px;
                    padding: 14px;
                    margin: 12px 0;
                }}
                .prediction-result strong {{ font-size: 1.5rem; }}
                .prediction-result span {{ color: var(--muted); }}
                .prediction-result .label {{
                    color: #72cdd7;
                    font-size: 0.78rem;
                    font-weight: 700;
                    letter-spacing: 0.16em;
                    text-transform: uppercase;
                }}
                .prediction-form {{
                    display: grid;
                    gap: 10px;
                    margin-top: 14px;
                }}
                .prediction-form label {{
                    color: var(--muted);
                    font-size: 0.82rem;
                    font-weight: 700;
                }}
                .prediction-form input {{
                    width: 100%;
                    border: 1px solid rgba(120, 198, 233, 0.28);
                    border-radius: 14px;
                    background: rgba(255, 255, 255, 0.98);
                    color: var(--ink);
                    padding: 10px 12px;
                    font: inherit;
                }}
                .prediction-form input::placeholder {{ color: #7eabc2; }}
                .prediction-form button {{
                    border: 0;
                    border-radius: 999px;
                    background: linear-gradient(180deg, #ffffff, #dff5ff);
                    color: #2f657f;
                    cursor: pointer;
                    font: inherit;
                    font-weight: 700;
                    padding: 10px 14px;
                    box-shadow: 0 12px 24px rgba(129, 189, 219, 0.16);
                }}
                ul {{ list-style: none; margin: 0; padding: 0; }}
                li {{
                    display: flex;
                    justify-content: space-between;
                    border-bottom: 1px solid var(--line);
                    padding: 12px 0;
                }}
                table {{ width: 100%; border-collapse: collapse; }}
                th, td {{
                    text-align: left;
                    border-bottom: 1px solid var(--line);
                    padding: 12px 8px;
                    font-size: 0.95rem;
                }}
                th {{ color: var(--muted); font-weight: 700; }}
                th {{ font-family: var(--font-mono); letter-spacing: 0.08em; text-transform: uppercase; font-size: 0.78rem; }}
                .full {{ grid-column: 1 / -1; }}
                .nav {{ display: flex; gap: 12px; flex-wrap: wrap; }}
                .pill {{
                    font-family: var(--font-mono);
                    display: inline-block;
                    padding: 8px 12px;
                    border-radius: 999px;
                    background: rgba(255, 255, 255, 0.76);
                    color: #1a739f;
                    font-weight: 700;
                    margin: 0 8px 8px 0;
                }}
                @media (max-width: 860px) {{
                    .grid, .bar-row, .hero-strip {{ grid-template-columns: 1fr; }}
                    .topline {{ align-items: start; flex-direction: column; }}
                }}
            </style>
        </head>
        <body>
            <main>
                <div class="topline">
                    <div>
                        <div class="eyebrow">Live Database Analytics | {season_label}</div>
                        <h1>NBA Team Dashboard</h1>
                    </div>
                    <nav class="nav">
                        <a href="/">Home</a>
                        <a href="/docs">API Docs</a>
                        <a href="/predictions/matchup?team_a=Indiana%20Pacers&team_b=Oklahoma%20City%20Thunder&last_n=10">Prediction</a>
                        <a href="/predictions/history?limit=10">Prediction History</a>
                        <a href="/pipeline/runs?limit=3">Pipeline Runs</a>
                    </nav>
                </div>

                <section class="hero-strip">
                    <div class="mini-stat">
                        <strong>{total_rows:,}</strong>
                        <span>official NBA team-game rows</span>
                    </div>
                    <div class="mini-stat">
                        <strong>{unique_games:,}</strong>
                        <span>unique games modeled</span>
                    </div>
                    <div class="mini-stat">
                        <strong>{model_accuracy}</strong>
                        <span>ML holdout accuracy</span>
                    </div>
                    <div class="mini-stat">
                        <strong>{model_precision}</strong>
                        <span>ML holdout precision</span>
                    </div>
                </section>

                <section class="grid">
                    <article class="card">
                        <h2>Top Teams by Average Points</h2>
                        {points_rows}
                    </article>

                    <aside>
                        <div class="stat">
                            <strong>{rows_inserted}</strong>
                            <span>rows inserted in latest pipeline run</span>
                        </div>
                        <div class="stat">
                            <strong>{run_status}</strong>
                            <span>latest pipeline status</span>
                        </div>
                        <div class="stat">
                            <strong>{escape(str(latest_game_date or "n/a"))}</strong>
                            <span>latest loaded game date</span>
                        </div>
                        <div class="card">
                            <h2>Top 3PT% Teams</h2>
                            <ul>{three_point_rows}</ul>
                        </div>
                        <div class="card prediction-card">
                            <h2>ML Matchup Prediction</h2>
                            <div class="prediction-result">{prediction_summary}</div>
                            <p>
                                Logistic regression trained on {model_rows} historical matchup rows
                                using rolling 10-game team form, points allowed, and point-differential
                                features. The first team is treated as home and the second as away.
                                ROC-AUC: {model_auc};
                                high-confidence accuracy: {high_confidence_accuracy}
                                across {high_confidence_coverage} of holdout games.
                            </p>
                            <form class="prediction-form" action="/dashboard" method="get">
                                <input type="hidden" name="season" value="{escape(str(season_year or ""))}">
                                <label for="team-a">Home Team</label>
                                <input id="team-a" name="team_a" value="{safe_team_a}" placeholder="Indiana Pacers">
                                <label for="team-b">Away Team</label>
                                <input id="team-b" name="team_b" value="{safe_team_b}" placeholder="Oklahoma City Thunder">
                                <label for="last-n">Recent games window</label>
                                <input id="last-n" name="last_n" type="number" min="3" max="25" value="{safe_last_n}">
                                <button type="submit">Update Dashboard Prediction</button>
                            </form>
                            <a href="{prediction_link}">
                                Open Raw Prediction JSON
                            </a>
                            <a href="/predictions/history?limit=10">
                                Prediction History
                            </a>
                        </div>
                    </aside>

                    <article class="card full">
                        <h2>Recent Games</h2>
                        <table>
                            <thead>
                                <tr><th>Date</th><th>Team</th><th>Opponent</th><th>Result</th><th>Points</th></tr>
                            </thead>
                            <tbody>{game_rows}</tbody>
                        </table>
                        <p class="eyebrow">Latest run completed: {completed_at}</p>
                        <p>
                            <span class="pill">FastAPI</span>
                            <span class="pill">PostgreSQL</span>
                            <span class="pill">GitHub Actions</span>
                            <span class="pill">scikit-learn</span>
                            <span class="pill">AWS Lightsail</span>
                        </p>
                    </article>
                </section>
            </main>
        </body>
        </html>
        """
    )
