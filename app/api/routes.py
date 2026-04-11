from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import case, func
from typing import Optional
from app.db.database import get_db
from app.db.models import Game, PipelineRun

router = APIRouter()

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

@router.get("/games")
def get_games(
    limit: int = Query(default=20, ge=1, le=100),
    team: Optional[str] = None,
    season: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    result: Optional[str] = Query(default=None, pattern="^(W|L)$"),
    db: Session = Depends(get_db),
):
    query = db.query(Game)

    if team:
        query = query.filter(Game.team.ilike(f"%{team}%"))

    if season:
        query = query.filter(Game.season == season)

    if start_date:
        if len(start_date) != 10:
            raise HTTPException(status_code=400, detail="start_date must be YYYY-MM-DD")
        query = query.filter(Game.game_date >= start_date)

    if end_date:
        if len(end_date) != 10:
            raise HTTPException(status_code=400, detail="end_date must be YYYY-MM-DD")
        query = query.filter(Game.game_date <= end_date)

    if result:
        query = query.filter(Game.wl == result)

    games = (
        query.order_by(Game.game_date.desc(), Game.game_id.desc(), Game.team_id.asc())
        .limit(limit)
        .all()
    )

    return [
        {
            "game_id": g.game_id,
            "game_date": g.game_date,
            "season": g.season,
            "team_id": g.team_id,
            "team": g.team,
            "opponent": g.opponent,
            "matchup": g.matchup,
            "wl": g.wl,
            "points": g.points,
            "rebounds": g.rebounds,
            "assists": g.assists,
            "fg_pct": g.fg_pct,
            "fg3_pct": g.fg3_pct,
            "ft_pct": g.ft_pct,
        }
        for g in games
    ]

@router.get("/teams/{team_name}/summary")
def team_summary(team_name: str, db: Session = Depends(get_db)):
    result = db.query(
        Game.team,
        func.count(Game.id).label("games_played"),
        func.avg(Game.points).label("avg_points"),
        func.avg(Game.rebounds).label("avg_rebounds"),
        func.avg(Game.assists).label("avg_assists"),
        func.avg(Game.fg_pct).label("avg_fg_pct")
    ).filter(Game.team == team_name).group_by(Game.team).first()

    if not result:
        return {"error": "Team not found"}

    return {
        "team": result.team,
        "games_played": result.games_played,
        "avg_points": round(float(result.avg_points), 2) if result.avg_points is not None else None,
        "avg_rebounds": round(float(result.avg_rebounds), 2) if result.avg_rebounds is not None else None,
        "avg_assists": round(float(result.avg_assists), 2) if result.avg_assists is not None else None,
        "avg_fg_pct": round(float(result.avg_fg_pct), 3) if result.avg_fg_pct is not None else None,
    }


@router.get("/teams/{team_name}/trends")
def team_trends(
    team_name: str,
    last_n: int = Query(default=10, ge=1, le=25),
    db: Session = Depends(get_db),
):
    recent_games = (
        db.query(Game)
        .filter(Game.team == team_name)
        .order_by(Game.game_date.desc(), Game.game_id.desc())
        .limit(last_n)
        .all()
    )

    if not recent_games:
        return {"error": "Team not found"}

    wins = sum(1 for game in recent_games if game.wl == "W")
    losses = sum(1 for game in recent_games if game.wl == "L")

    avg_points = sum(game.points for game in recent_games) / len(recent_games)
    avg_rebounds = sum((game.rebounds or 0) for game in recent_games) / len(recent_games)
    avg_assists = sum((game.assists or 0) for game in recent_games) / len(recent_games)

    fg_pct_values = [game.fg_pct for game in recent_games if game.fg_pct is not None]
    fg3_pct_values = [game.fg3_pct for game in recent_games if game.fg3_pct is not None]

    return {
        "team": team_name,
        "sample_size": len(recent_games),
        "record": f"{wins}-{losses}",
        "wins": wins,
        "losses": losses,
        "avg_points": round(avg_points, 2),
        "avg_rebounds": round(avg_rebounds, 2),
        "avg_assists": round(avg_assists, 2),
        "avg_fg_pct": round(sum(fg_pct_values) / len(fg_pct_values), 3) if fg_pct_values else None,
        "avg_fg3_pct": round(sum(fg3_pct_values) / len(fg3_pct_values), 3) if fg3_pct_values else None,
        "recent_games": [
            {
                "game_date": game.game_date,
                "opponent": game.opponent,
                "matchup": game.matchup,
                "wl": game.wl,
                "points": game.points,
                "rebounds": game.rebounds,
                "assists": game.assists,
            }
            for game in recent_games
        ],
    }

@router.get("/leaders/points")
def scoring_leaders(db: Session = Depends(get_db)):
    results = db.query(
        Game.team,
        func.avg(Game.points).label("avg_points")
    ).group_by(Game.team).order_by(func.avg(Game.points).desc()).limit(10).all()

    return [
        {
            "team": r.team,
            "avg_points": round(float(r.avg_points), 2)
        }
        for r in results
    ]


@router.get("/analytics/team-rankings")
def team_rankings(
    metric: str = Query(default="points", pattern="^(points|rebounds|assists|fg_pct|fg3_pct)$"),
    limit: int = Query(default=10, ge=1, le=30),
    db: Session = Depends(get_db),
):
    metric_columns = {
        "points": Game.points,
        "rebounds": Game.rebounds,
        "assists": Game.assists,
        "fg_pct": Game.fg_pct,
        "fg3_pct": Game.fg3_pct,
    }
    metric_column = metric_columns[metric]
    avg_metric = func.avg(metric_column).label("average")

    results = (
        db.query(
            Game.team,
            func.count(Game.id).label("games_played"),
            avg_metric,
            func.sum(case((Game.wl == "W", 1), else_=0)).label("wins"),
        )
        .group_by(Game.team)
        .order_by(avg_metric.desc())
        .limit(limit)
        .all()
    )

    return [
        {
            "rank": index + 1,
            "team": row.team,
            "metric": metric,
            "average": round(float(row.average), 3) if row.average is not None else None,
            "games_played": row.games_played,
            "wins": int(row.wins or 0),
        }
        for index, row in enumerate(results)
    ]


@router.get("/pipeline/runs")
def get_pipeline_runs(limit: int = 10, db: Session = Depends(get_db)):
    runs = (
        db.query(PipelineRun)
        .order_by(PipelineRun.started_at.desc(), PipelineRun.id.desc())
        .limit(limit)
        .all()
    )

    return [
        {
            "pipeline_name": run.pipeline_name,
            "season": run.season,
            "mode": run.mode,
            "rows_fetched": run.rows_fetched,
            "rows_inserted": run.rows_inserted,
            "rows_skipped": run.rows_skipped,
            "status": run.status,
            "error_message": run.error_message,
            "started_at": run.started_at,
            "completed_at": run.completed_at,
        }
        for run in runs
    ]
