from html import escape

from fastapi import APIRouter, Depends, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import ModelPick
from app.services.picks import picks_performance_summary, serialize_pick


router = APIRouter(tags=["picks"])


@router.get("/picks")
def list_picks(
    limit: int = Query(default=25, ge=1, le=200),
    game_date: str = None,
    settled: bool = None,
    db: Session = Depends(get_db),
):
    query = db.query(ModelPick).order_by(ModelPick.game_date.desc(), ModelPick.id.desc())
    if game_date:
        query = query.filter(ModelPick.game_date == game_date)
    if settled is not None:
        query = query.filter(ModelPick.settled.is_(settled))

    rows = query.limit(limit).all()
    return [serialize_pick(row) for row in rows]


@router.get("/picks/summary")
def picks_summary(
    since_date: str = None,
    db: Session = Depends(get_db),
):
    return picks_performance_summary(db, since_date=since_date)


@router.get("/picks/view")
def picks_view(
    limit: int = Query(default=50, ge=1, le=200),
    game_date: str = None,
    settled: bool = None,
    db: Session = Depends(get_db),
):
    query = db.query(ModelPick).order_by(ModelPick.game_date.desc(), ModelPick.id.desc())
    if game_date:
        query = query.filter(ModelPick.game_date == game_date)
    if settled is not None:
        query = query.filter(ModelPick.settled.is_(settled))

    rows = query.limit(limit).all()
    table_rows = "\n".join(
        f"""
        <tr>
            <td>{escape(row.game_date)}</td>
            <td>{escape(row.home_team)} vs {escape(row.away_team)}</td>
            <td>{escape(row.pick or "n/a")}</td>
            <td>{escape(str(round(row.edge, 4)) if row.edge is not None else "n/a")}</td>
            <td>{escape(row.confidence_tier or "n/a")}</td>
            <td>{'yes' if row.settled else 'no'}</td>
            <td>{escape(str(row.correct) if row.settled else 'n/a')}</td>
        </tr>
        """
        for row in rows
    )
    safe_game_date = escape(game_date or "")
    settled_value = "" if settled is None else ("true" if settled else "false")

    return HTMLResponse(
        f"""
        <!doctype html>
        <html lang="en">
        <head>
          <meta charset="utf-8">
          <meta name="viewport" content="width=device-width, initial-scale=1">
          <title>Model Picks</title>
          <style>
            :root {{
              --bg: #fdfefe;
              --ink: #23485f;
              --muted: #6f93a8;
              --line: rgba(151, 204, 232, 0.42);
              --shadow: rgba(129, 189, 219, 0.14);
              --panel: rgba(255, 255, 255, 0.95);
              --font: "Avenir Next", "Trebuchet MS", "Segoe UI", "Helvetica Neue", Arial, sans-serif;
              --mono: "SFMono-Regular", "SF Mono", "IBM Plex Mono", "Cascadia Code", Consolas, monospace;
            }}
            * {{ box-sizing: border-box; }}
            body {{
              margin: 0;
              font-family: var(--font);
              color: var(--ink);
              background: linear-gradient(180deg, #ffffff 0%, #f4fbff 50%, #edf8ff 100%);
              min-height: 100vh;
            }}
            main {{
              width: min(1180px, calc(100% - 32px));
              margin: 0 auto;
              padding: 34px 0 48px;
            }}
            header {{
              display: flex;
              justify-content: space-between;
              align-items: end;
              gap: 16px;
              margin-bottom: 18px;
            }}
            h1 {{
              margin: 0;
              font-size: 2.4rem;
              letter-spacing: -0.04em;
            }}
            nav a {{
              font-family: var(--mono);
              color: #4d8fb5;
              font-weight: 700;
              text-decoration: none;
              margin-left: 14px;
            }}
            .card {{
              background: var(--panel);
              border: 1px solid var(--line);
              border-radius: 24px;
              box-shadow: 0 18px 46px var(--shadow), inset 0 1px 0 rgba(255, 255, 255, 0.96);
              padding: 18px;
            }}
            form {{
              display: grid;
              grid-template-columns: 1fr 220px 140px 140px;
              gap: 12px;
              align-items: end;
              margin-bottom: 14px;
            }}
            label {{
              font-family: var(--mono);
              font-size: 0.78rem;
              letter-spacing: 0.14em;
              text-transform: uppercase;
              color: var(--muted);
              display: block;
              margin-bottom: 6px;
            }}
            input, select {{
              width: 100%;
              border: 1px solid var(--line);
              border-radius: 16px;
              padding: 12px 14px;
              font-family: var(--font);
              font-size: 1rem;
              background: rgba(255, 255, 255, 0.9);
            }}
            button {{
              border: 1px solid rgba(120, 198, 233, 0.45);
              border-radius: 16px;
              padding: 12px 14px;
              font-weight: 800;
              color: #2f657f;
              background: linear-gradient(180deg, #ffffff, #dff5ff);
              cursor: pointer;
            }}
            table {{
              width: 100%;
              border-collapse: collapse;
            }}
            th, td {{
              text-align: left;
              padding: 12px 10px;
              border-bottom: 1px solid rgba(151, 204, 232, 0.28);
              font-size: 0.98rem;
            }}
            th {{
              font-family: var(--mono);
              color: var(--muted);
              letter-spacing: 0.14em;
              text-transform: uppercase;
              font-size: 0.75rem;
            }}
            .muted {{
              color: var(--muted);
              font-family: var(--mono);
              font-size: 0.9rem;
              margin-top: 10px;
            }}
            @media (max-width: 940px) {{
              form {{ grid-template-columns: 1fr; }}
            }}
          </style>
        </head>
        <body>
          <main>
            <header>
              <div>
                <div class="muted">V2 Picks Tracking</div>
                <h1>Model Picks</h1>
              </div>
              <nav>
                <a href="/dashboard">Dashboard</a>
                <a href="/picks/summary">Summary JSON</a>
                <a href="/docs">API Docs</a>
              </nav>
            </header>
            <section class="card">
              <form method="get" action="/picks/view">
                <div>
                  <label for="game_date">Game Date (YYYY-MM-DD)</label>
                  <input id="game_date" name="game_date" value="{safe_game_date}" placeholder="2026-05-01">
                </div>
                <div>
                  <label for="settled">Settled</label>
                  <select id="settled" name="settled">
                    <option value="" {"selected" if settled is None else ""}>All</option>
                    <option value="true" {"selected" if settled_value == "true" else ""}>Settled</option>
                    <option value="false" {"selected" if settled_value == "false" else ""}>Unsettled</option>
                  </select>
                </div>
                <div>
                  <label for="limit">Limit</label>
                  <input id="limit" name="limit" type="number" min="1" max="200" value="{limit}">
                </div>
                <div>
                  <button type="submit">Filter</button>
                </div>
              </form>
              <table>
                <thead>
                  <tr><th>Date</th><th>Matchup</th><th>Pick</th><th>Edge</th><th>Tier</th><th>Settled</th><th>Correct</th></tr>
                </thead>
                <tbody>
                  {table_rows or "<tr><td colspan='7' class='muted'>No picks found.</td></tr>"}
                </tbody>
              </table>
              <div class="muted">Tip: use `GET /picks` for raw JSON.</div>
            </section>
          </main>
        </body>
        </html>
        """
    )
