from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from typing import Optional
from html import escape
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

router = APIRouter()
router.include_router(games_router)
router.include_router(analytics_router)
router.include_router(predictions_router)
router.include_router(pipeline_router)
router.include_router(admin_router)

@router.get("/")
def home():
    return HTMLResponse(
        """
        <!doctype html>
        <html lang="en">
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <title>NBA Data Pipeline</title>
            <style>
                :root {
                    --ink: #17202a;
                    --muted: #65758b;
                    --court: #f3b562;
                    --paint: #174ea6;
                    --paper: #fffaf0;
                    --line: rgba(23, 32, 42, 0.14);
                }
                * { box-sizing: border-box; }
                body {
                    margin: 0;
                    font-family: Georgia, "Times New Roman", serif;
                    color: var(--ink);
                    background:
                        radial-gradient(circle at top left, rgba(243, 181, 98, 0.55), transparent 32rem),
                        linear-gradient(135deg, #fff8ea 0%, #e7f0ff 100%);
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
                    background: rgba(255, 250, 240, 0.88);
                    border: 1px solid var(--line);
                    border-radius: 28px;
                    box-shadow: 0 24px 80px rgba(23, 32, 42, 0.12);
                    padding: 28px;
                    backdrop-filter: blur(10px);
                }
                h1 {
                    font-size: clamp(2.4rem, 8vw, 5.8rem);
                    line-height: 0.9;
                    letter-spacing: -0.08em;
                    margin: 0 0 20px;
                }
                h2 {
                    font-size: 1.1rem;
                    text-transform: uppercase;
                    letter-spacing: 0.16em;
                    margin: 0 0 18px;
                    color: var(--paint);
                }
                p {
                    font-size: 1.08rem;
                    line-height: 1.7;
                    color: var(--muted);
                    max-width: 62ch;
                }
                .metric-grid {
                    display: grid;
                    grid-template-columns: repeat(3, minmax(0, 1fr));
                    gap: 16px;
                    margin-top: 28px;
                }
                .metric {
                    border: 1px solid var(--line);
                    border-radius: 20px;
                    padding: 18px;
                    background: #fff;
                }
                .metric strong {
                    display: block;
                    font-size: 2rem;
                    letter-spacing: -0.05em;
                }
                .metric span {
                    color: var(--muted);
                    font-size: 0.9rem;
                }
                .court {
                    position: relative;
                    min-height: 340px;
                    overflow: hidden;
                    background: linear-gradient(180deg, #f7c06e, #d98f42);
                }
                .court::before {
                    content: "";
                    position: absolute;
                    inset: 30px;
                    border: 3px solid rgba(255, 255, 255, 0.8);
                    border-radius: 24px;
                }
                .court::after {
                    content: "";
                    position: absolute;
                    width: 190px;
                    height: 190px;
                    border: 3px solid rgba(255, 255, 255, 0.75);
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
                    background: var(--paint);
                    box-shadow: 0 0 0 8px rgba(23, 78, 166, 0.16);
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
                    color: var(--paint);
                    font-weight: 700;
                    text-decoration: none;
                }
                .link-card {
                    display: block;
                    border: 1px solid var(--line);
                    border-radius: 18px;
                    background: #fff;
                    padding: 16px;
                }
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
                            tracks pipeline runs, and serves analytics-ready endpoints
                            for team summaries, trends, leaders, and filtered game search.
                        </p>
                        <div class="metric-grid">
                            <div class="metric"><strong>2,802</strong><span>team-game rows loaded</span></div>
                            <div class="metric"><strong>6</strong><span>API endpoints</span></div>
                            <div class="metric"><strong>1</strong><span>Render deployment</span></div>
                        </div>
                        <div class="links">
                            <a class="link-card" href="/docs">Interactive API Docs</a>
                            <a class="link-card" href="/games?limit=5">Recent Games</a>
                            <a class="link-card" href="/analytics/team-rankings?metric=points&limit=10">Team Rankings</a>
                            <a class="link-card" href="/teams/Indiana%20Pacers/trends?last_n=5">Pacers Trend Analysis</a>
                            <a class="link-card" href="/pipeline/runs?limit=3">Pipeline Runs</a>
                        </div>
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
    )

@router.get("/health")
def health():
    return {"status": "ok"}

@router.get("/dashboard")
def dashboard(
    season: Optional[str] = None,
    db: Session = Depends(get_db),
):
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
                    --ink: #17202a;
                    --muted: #64748b;
                    --court: #edb458;
                    --paint: #174ea6;
                    --rim: #d1495b;
                    --paper: #fffaf0;
                    --panel: rgba(255, 250, 240, 0.9);
                    --line: rgba(23, 32, 42, 0.14);
                }}
                * {{ box-sizing: border-box; }}
                body {{
                    margin: 0;
                    font-family: Georgia, "Times New Roman", serif;
                    color: var(--ink);
                    background:
                        linear-gradient(90deg, rgba(23, 78, 166, 0.08) 1px, transparent 1px),
                        linear-gradient(0deg, rgba(23, 78, 166, 0.08) 1px, transparent 1px),
                        radial-gradient(circle at 15% 10%, rgba(237, 180, 88, 0.6), transparent 28rem),
                        linear-gradient(135deg, #fff8ea 0%, #e8f1ff 100%);
                    background-size: 48px 48px, 48px 48px, auto, auto;
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
                a {{ color: var(--paint); font-weight: 700; text-decoration: none; }}
                .grid {{
                    display: grid;
                    grid-template-columns: 1.35fr 0.65fr;
                    gap: 22px;
                }}
                .card {{
                    background: var(--panel);
                    border: 1px solid var(--line);
                    border-radius: 28px;
                    box-shadow: 0 24px 80px rgba(23, 32, 42, 0.12);
                    padding: 24px;
                    backdrop-filter: blur(10px);
                }}
                h2 {{ margin: 0 0 18px; font-size: 1.1rem; letter-spacing: -0.02em; }}
                .bar-row {{
                    display: grid;
                    grid-template-columns: 190px 1fr 64px;
                    gap: 12px;
                    align-items: center;
                    margin: 14px 0;
                }}
                .bar-track {{
                    height: 16px;
                    background: rgba(23, 78, 166, 0.12);
                    border-radius: 999px;
                    overflow: hidden;
                }}
                .bar-fill {{
                    height: 100%;
                    background: linear-gradient(90deg, var(--paint), var(--rim));
                    border-radius: inherit;
                }}
                .stat {{
                    background: #fff;
                    border: 1px solid var(--line);
                    border-radius: 20px;
                    padding: 18px;
                    margin-bottom: 16px;
                }}
                .stat strong {{ display: block; font-size: 2rem; letter-spacing: -0.05em; }}
                .stat span {{ color: var(--muted); }}
                .prediction-card {{
                    margin-top: 16px;
                    background: linear-gradient(135deg, #17202a, #174ea6);
                    color: #fff;
                }}
                .prediction-card p {{
                    color: rgba(255, 255, 255, 0.78);
                    line-height: 1.55;
                }}
                .prediction-card a {{
                    display: inline-block;
                    color: #17202a;
                    background: var(--court);
                    border-radius: 999px;
                    padding: 10px 14px;
                    margin-top: 6px;
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
                .full {{ grid-column: 1 / -1; }}
                .nav {{ display: flex; gap: 12px; flex-wrap: wrap; }}
                @media (max-width: 860px) {{
                    .grid, .bar-row {{ grid-template-columns: 1fr; }}
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
                        <a href="/pipeline/runs?limit=3">Pipeline Runs</a>
                    </nav>
                </div>

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
                        <div class="card">
                            <h2>Top 3PT% Teams</h2>
                            <ul>{three_point_rows}</ul>
                        </div>
                        <div class="card prediction-card">
                            <h2>Heuristic Matchup Prediction</h2>
                            <p>
                                A transparent recent-form score, not a trained ML model.
                                Useful for showing how pipeline data can power model-ready features.
                            </p>
                            <a href="/predictions/matchup?team_a=Indiana%20Pacers&team_b=Oklahoma%20City%20Thunder&last_n=10">
                                Pacers vs Thunder
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
                    </article>
                </section>
            </main>
        </body>
        </html>
        """
    )
