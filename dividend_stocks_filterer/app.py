import logging
import os
import sys
sys.path.insert(0, os.path.dirname(__file__))

from fastapi import FastAPI, Request, Form
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from typing import List

from configure import read_configurations
from db_functions import MysqlConnection
from helper_functions import radar_dict_to_table

logger = logging.getLogger(__name__)

# Slider range caps — clamp raw DB min/max to sane bounds so a single outlier stock can't blow out a slider.
YIELD_MAX_CAP = 25.0
DGR_MIN_CAP = -25.0
DGR_MAX_CAP = 25.0
CHOWDER_MAX_CAP = 25.0
FV_MIN_CAP = -25.0
FV_MAX_FLOOR = 0.0
PE_MIN_CAP = -50.0
PE_MAX_CAP = 100.0
PAYOUT_MAX_DEFAULT = 100.0

app = FastAPI()
templates = Jinja2Templates(
    directory=os.path.join(os.path.dirname(__file__), "templates")
)

# --- One-time startup ---
# Constructing the pool does NOT open a DB connection (mincached=0), so this is safe even when the DB is down.
configuration = read_configurations()
db = MysqlConnection(
    db_host=configuration["db_host"], db_schema=configuration["db_schema"],
    db_password=configuration["db_pass"], db_port=configuration["db_port"],
    db_user=configuration["db_user"]
)


def compute_ranges() -> dict:
    """Query the DB for the min/max values that drive the slider ranges and exclusion options."""
    raw = db.min_max_all_values()
    return {
        # Dividend section
        "streak_default": 5,
        "yield_max": min(max(raw['yield_max_raw'], raw['5y_yield_max']), YIELD_MAX_CAP),
        "dgr_min": max(min(raw['dgr1y_min'], raw['dgr3y_min'], raw['dgr5y_min'], raw['dgr10y_min']), DGR_MIN_CAP),
        "dgr_max": min(max(raw['dgr1y_max'], raw['dgr3y_max'], raw['dgr5y_max'], raw['dgr10y_max']), DGR_MAX_CAP),
        "chowder_max": int(min(raw['chowder_max_raw'], CHOWDER_MAX_CAP)),
        # Financial section
        "price_max": raw['price_max_raw'],
        "fv_min": int(max(raw['fv_min_raw'], FV_MIN_CAP)),
        "fv_max": int(max(raw['fv_max_raw'], FV_MAX_FLOOR)),
        "revenue_min": raw['revenue_min'],
        "revenue_max": raw['revenue_max'],
        "npm_min": raw['npm_min'],
        "npm_max": raw['npm_max'],
        "cf_min": raw['cf_min'],
        "cf_max": raw['cf_max'],
        "roe_min": raw['roe_min'],
        "roe_max": raw['roe_max'],
        "pe_min": max(raw['pe_min_raw'], PE_MIN_CAP),
        "pe_max": min(raw['pe_max_raw'], PE_MAX_CAP),
        "pbv_min": raw['pbv_min'],
        "pbv_max": raw['pbv_max'],
        "debt_max": raw['debt_max_raw'],
        "payout_max": float(raw['payout_ratio_max_raw']) if raw['payout_ratio_max_raw'] is not None else PAYOUT_MAX_DEFAULT,
        # Exclusion options
        "symbols": db.list_values_of_key_in_db("Symbol"),
        "sectors": db.list_values_of_key_in_db("Sector"),
        "industries": db.list_values_of_key_in_db("Industry"),
    }


# Compute ranges at startup, but don't let a transient DB outage stop the app from booting — retry lazily on the
# first request that needs them (see get_ranges). This keeps /health answerable even when the DB is unreachable.
try:
    ranges = compute_ranges()
except Exception:
    logger.exception("Could not compute slider ranges at startup; will retry on first request")
    ranges = None


def get_ranges() -> dict:
    """Return the cached slider ranges, computing them on demand if startup couldn't reach the DB."""
    global ranges
    if ranges is None:
        ranges = compute_ranges()
    return ranges


@app.get("/health")
async def health():
    try:
        await run_in_threadpool(db.run_sql_query, "SELECT 1")
        return JSONResponse({"status": "ok"})
    except Exception:
        logger.exception("Health check failed: database query did not succeed")
        return JSONResponse({"status": "error"}, status_code=503)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    try:
        current_ranges = await run_in_threadpool(get_ranges)
        db_update_dates = await run_in_threadpool(db.check_db_update_dates)
    except Exception:
        logger.exception("Could not load page data from the database")
        return HTMLResponse(
            "<h1>Service temporarily unavailable</h1>"
            "<p>The dividend database is currently unreachable. Please try again shortly.</p>",
            status_code=503,
        )
    return templates.TemplateResponse(request, "index.html", {
        "ranges": current_ranges,
        "db_update_dates": db_update_dates,
        "ga_measurement_id": configuration.get("ga_measurement_id", ""),
    })


@app.post("/filter", response_class=HTMLResponse)
async def filter_stocks(
    request: Request,
    min_streak_years: int = Form(5),
    yield_range_min: float = Form(0.0),
    yield_range_max: float = Form(10.0),
    min_dgr: float = Form(0.0),
    chowder_number: int = Form(0),
    price_range_min: float = Form(1.0),
    price_range_max: float = Form(500.0),
    fair_value: int = Form(0),
    min_revenue: float = Form(0.0),
    min_npm: float = Form(0.0),
    min_cf_per_share: float = Form(0.0),
    min_roe: float = Form(0.0),
    pe_range_min: float = Form(-50.0),
    pe_range_max: float = Form(100.0),
    max_price_per_book_value: float = Form(10.0),
    max_debt_per_capital_value: float = Form(1.0),
    max_payout_ratio: float = Form(100.0),
    excluded_symbols: List[str] = Form(default=[]),
    excluded_sectors: List[str] = Form(default=[]),
    excluded_industries: List[str] = Form(default=[]),
):
    results = await run_in_threadpool(
        db.run_filter_query,
        min_streak_years, yield_range_min, yield_range_max,
        min_dgr, chowder_number, price_range_min, price_range_max,
        fair_value, min_revenue, min_npm, min_cf_per_share, min_roe,
        pe_range_min, pe_range_max, max_price_per_book_value,
        max_debt_per_capital_value, max_payout_ratio,
        excluded_symbols, excluded_sectors, excluded_industries
    )
    df = radar_dict_to_table(results)
    return templates.TemplateResponse(request, "_table.html", {
        "table_html": df.to_html(
            classes="table table-striped table-hover table-sm", border=0, index=True
        ),
        "row_count": len(df),
    })
