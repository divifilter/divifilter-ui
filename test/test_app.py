import sys
import types
import unittest
import importlib
from unittest.mock import MagicMock

import pandas


class TestApp(unittest.TestCase):

    def setUp(self):
        mock_mysql = MagicMock()
        mock_mysql.check_db_update_dates.return_value = {
            "radar_file": "2024-01-01",
            "yahoo_finance": "2024-01-02"
        }
        mock_mysql.min_max_all_values.return_value = {
            'yield_max_raw': 10.0, '5y_yield_max': 10.0,
            'dgr1y_min': 0.0, 'dgr1y_max': 10.0,
            'dgr3y_min': 0.0, 'dgr3y_max': 10.0,
            'dgr5y_min': 0.0, 'dgr5y_max': 10.0,
            'dgr10y_min': 0.0, 'dgr10y_max': 10.0,
            'chowder_max_raw': 10.0, 'price_max_raw': 500.0,
            'fv_min_raw': -10.0, 'fv_max_raw': 10.0,
            'revenue_min': 0.0, 'revenue_max': 10.0,
            'npm_min': 0.0, 'npm_max': 10.0,
            'cf_min': 0.0, 'cf_max': 10.0,
            'roe_min': 0.0, 'roe_max': 10.0,
            'pe_min_raw': -50.0, 'pe_max_raw': 100.0,
            'pbv_min': 0.0, 'pbv_max': 10.0,
            'debt_max_raw': 1.0,
            'payout_ratio_max_raw': 100.0,
        }
        mock_mysql.list_values_of_key_in_db.return_value = ["AAPL", "MSFT"]
        mock_mysql.run_filter_query.return_value = {}
        self.mock_mysql = mock_mysql

        mock_configure = types.ModuleType('configure')
        mock_configure.read_configurations = MagicMock(return_value={
            "db_host": "h", "db_port": 3306, "db_user": "u",
            "db_pass": "p", "db_schema": "s", "ga_measurement_id": ""
        })
        mock_db_mod = types.ModuleType('db_functions')
        mock_db_mod.MysqlConnection = MagicMock(return_value=mock_mysql)
        mock_helper = types.ModuleType('helper_functions')
        mock_helper.radar_dict_to_table = MagicMock(return_value=pandas.DataFrame())

        self.mocks = {
            'configure': mock_configure,
            'helper_functions': mock_helper,
            'db_functions': mock_db_mod,
        }
        self.saved = {k: sys.modules.get(k) for k in self.mocks}
        for k, v in self.mocks.items():
            sys.modules[k] = v

        app_key = 'dividend_stocks_filterer.app'
        sys.modules.pop(app_key, None)
        self.app_module = importlib.import_module(app_key)

        from fastapi.testclient import TestClient
        self.client = TestClient(self.app_module.app)

    def tearDown(self):
        for k in self.mocks:
            if self.saved[k] is not None:
                sys.modules[k] = self.saved[k]
            elif k in sys.modules:
                del sys.modules[k]
        sys.modules.pop('dividend_stocks_filterer.app', None)

    def test_health_returns_ok(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_index_returns_200(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)

    def test_index_contains_form(self):
        response = self.client.get("/")
        self.assertIn('hx-post="/filter"', response.text)

    def test_index_contains_update_dates(self):
        response = self.client.get("/")
        self.assertIn("2024-01-01", response.text)

    def test_post_filter_returns_200(self):
        response = self.client.post("/filter", data={
            "min_streak_years": 5,
            "yield_range_min": 0.0,
            "yield_range_max": 10.0,
            "min_dgr": 0.0,
            "chowder_number": 0,
            "price_range_min": 1.0,
            "price_range_max": 500.0,
            "fair_value": 0,
            "min_revenue": 0.0,
            "min_npm": 0.0,
            "min_cf_per_share": 0.0,
            "min_roe": 0.0,
            "pe_range_min": -50.0,
            "pe_range_max": 100.0,
            "max_price_per_book_value": 10.0,
            "max_debt_per_capital_value": 1.0,
            "max_payout_ratio": 100.0,
        })
        self.assertEqual(response.status_code, 200)

    def test_post_filter_calls_run_filter_query(self):
        self.mock_mysql.run_filter_query.reset_mock()
        self.client.post("/filter", data={
            "min_streak_years": 10,
            "yield_range_min": 1.0,
            "yield_range_max": 8.0,
            "min_dgr": 0.5,
            "chowder_number": 5,
            "price_range_min": 10.0,
            "price_range_max": 200.0,
            "fair_value": 5,
            "min_revenue": 0.01,
            "min_npm": 1.0,
            "min_cf_per_share": 0.5,
            "min_roe": 5.0,
            "pe_range_min": 0.0,
            "pe_range_max": 30.0,
            "max_price_per_book_value": 3.0,
            "max_debt_per_capital_value": 0.6,
            "max_payout_ratio": 80.0,
        })
        self.mock_mysql.run_filter_query.assert_called_once()

    def test_post_filter_returns_table_html(self):
        self.mocks['helper_functions'].radar_dict_to_table.return_value = pandas.DataFrame(
            {"Symbol": ["AAPL"], "Price": [150.0]}
        )
        response = self.client.post("/filter", data={
            "min_streak_years": 5,
            "yield_range_min": 0.0,
            "yield_range_max": 10.0,
            "min_dgr": 0.0,
            "chowder_number": 0,
            "price_range_min": 1.0,
            "price_range_max": 500.0,
            "fair_value": 0,
            "min_revenue": 0.0,
            "min_npm": 0.0,
            "min_cf_per_share": 0.0,
            "min_roe": 0.0,
            "pe_range_min": -50.0,
            "pe_range_max": 100.0,
            "max_price_per_book_value": 10.0,
            "max_debt_per_capital_value": 1.0,
            "max_payout_ratio": 100.0,
        })
        self.assertIn("<table", response.text)

    def test_post_filter_empty_results(self):
        self.mock_mysql.run_filter_query.return_value = {}
        self.mocks['helper_functions'].radar_dict_to_table.return_value = pandas.DataFrame()
        response = self.client.post("/filter", data={
            "min_streak_years": 50,
            "yield_range_min": 0.0,
            "yield_range_max": 0.0,
            "min_dgr": 0.0,
            "chowder_number": 0,
            "price_range_min": 1.0,
            "price_range_max": 500.0,
            "fair_value": 0,
            "min_revenue": 0.0,
            "min_npm": 0.0,
            "min_cf_per_share": 0.0,
            "min_roe": 0.0,
            "pe_range_min": -50.0,
            "pe_range_max": 100.0,
            "max_price_per_book_value": 10.0,
            "max_debt_per_capital_value": 1.0,
            "max_payout_ratio": 100.0,
        })
        self.assertIn("No stocks match your filters", response.text)

    def test_post_filter_max_payout_ratio_forwarded(self):
        self.mock_mysql.run_filter_query.reset_mock()
        self.client.post("/filter", data={
            "min_streak_years": 5,
            "yield_range_min": 0.0,
            "yield_range_max": 10.0,
            "min_dgr": 0.0,
            "chowder_number": 0,
            "price_range_min": 1.0,
            "price_range_max": 500.0,
            "fair_value": 0,
            "min_revenue": 0.0,
            "min_npm": 0.0,
            "min_cf_per_share": 0.0,
            "min_roe": 0.0,
            "pe_range_min": -50.0,
            "pe_range_max": 100.0,
            "max_price_per_book_value": 10.0,
            "max_debt_per_capital_value": 1.0,
            "max_payout_ratio": 55.0,
        })
        args = self.mock_mysql.run_filter_query.call_args
        self.assertEqual(args[0][16], 55.0)

    def test_post_filter_excluded_symbols_forwarded(self):
        self.mock_mysql.run_filter_query.reset_mock()
        self.client.post("/filter", data={
            "min_streak_years": 5,
            "yield_range_min": 0.0,
            "yield_range_max": 10.0,
            "min_dgr": 0.0,
            "chowder_number": 0,
            "price_range_min": 1.0,
            "price_range_max": 500.0,
            "fair_value": 0,
            "min_revenue": 0.0,
            "min_npm": 0.0,
            "min_cf_per_share": 0.0,
            "min_roe": 0.0,
            "pe_range_min": -50.0,
            "pe_range_max": 100.0,
            "max_price_per_book_value": 10.0,
            "max_debt_per_capital_value": 1.0,
            "max_payout_ratio": 100.0,
            "excluded_symbols": ["AAPL", "MSFT"],
        })
        args = self.mock_mysql.run_filter_query.call_args
        self.assertIn("AAPL", args[0][17])
        self.assertIn("MSFT", args[0][17])

    def test_health_returns_503_on_db_error(self):
        self.mock_mysql.run_sql_query.side_effect = Exception("db down")
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"status": "error"})

    def test_index_returns_503_when_db_unreachable(self):
        self.mock_mysql.check_db_update_dates.side_effect = Exception("db down")
        response = self.client.get("/")
        self.assertEqual(response.status_code, 503)
        self.assertIn("temporarily unavailable", response.text)

    def test_get_ranges_recomputes_lazily_when_startup_failed(self):
        # Simulate startup having failed to reach the DB (ranges left as None), then a request arrives.
        self.app_module.ranges = None
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        # Ranges were recomputed on demand and cached.
        self.assertIsNotNone(self.app_module.ranges)
        self.mock_mysql.min_max_all_values.assert_called()

    def test_startup_survives_db_outage(self):
        # Re-import the app with the startup range query failing; the module must still import (app boots),
        # leaving ranges=None for later lazy retry instead of crashing the process.
        self.mock_mysql.min_max_all_values.side_effect = Exception("db down")
        sys.modules.pop('dividend_stocks_filterer.app', None)
        reloaded = importlib.import_module('dividend_stocks_filterer.app')
        self.assertIsNone(reloaded.ranges)

    def test_post_filter_excluded_sectors_forwarded(self):
        self.mock_mysql.run_filter_query.reset_mock()
        self.client.post("/filter", data={
            "min_streak_years": 5,
            "yield_range_min": 0.0,
            "yield_range_max": 10.0,
            "min_dgr": 0.0,
            "chowder_number": 0,
            "price_range_min": 1.0,
            "price_range_max": 500.0,
            "fair_value": 0,
            "min_revenue": 0.0,
            "min_npm": 0.0,
            "min_cf_per_share": 0.0,
            "min_roe": 0.0,
            "pe_range_min": -50.0,
            "pe_range_max": 100.0,
            "max_price_per_book_value": 10.0,
            "max_debt_per_capital_value": 1.0,
            "max_payout_ratio": 100.0,
            "excluded_sectors": ["Technology"],
        })
        args = self.mock_mysql.run_filter_query.call_args
        self.assertIn("Technology", args[0][18])

    def test_post_filter_excluded_industries_forwarded(self):
        self.mock_mysql.run_filter_query.reset_mock()
        self.client.post("/filter", data={
            "min_streak_years": 5,
            "yield_range_min": 0.0,
            "yield_range_max": 10.0,
            "min_dgr": 0.0,
            "chowder_number": 0,
            "price_range_min": 1.0,
            "price_range_max": 500.0,
            "fair_value": 0,
            "min_revenue": 0.0,
            "min_npm": 0.0,
            "min_cf_per_share": 0.0,
            "min_roe": 0.0,
            "pe_range_min": -50.0,
            "pe_range_max": 100.0,
            "max_price_per_book_value": 10.0,
            "max_debt_per_capital_value": 1.0,
            "max_payout_ratio": 100.0,
            "excluded_industries": ["Banking"],
        })
        args = self.mock_mysql.run_filter_query.call_args
        self.assertIn("Banking", args[0][19])

    # ── Large-number formatting (Market Cap etc.) ─────────────────────────

    def test_human_format_abbreviations(self):
        hf = self.app_module.human_format
        self.assertEqual(hf(1.2e12), "1.20T")
        self.assertEqual(hf(3.6671e10), "36.67B")
        self.assertEqual(hf(5.374e8), "537.40M")
        self.assertEqual(hf(12345), "12,345")
        self.assertEqual(hf(None), "")
        self.assertEqual(hf(float("nan")), "")

    def test_filter_abbreviates_large_columns_in_html(self):
        self.mocks['helper_functions'].radar_dict_to_table.return_value = pandas.DataFrame(
            {"Market Cap": [3.6671e10, 5.374e8], "Div Yield": [3.5, 2.1]},
            index=["AAPL", "MSFT"],
        )
        response = self.client.post("/filter", data={"min_streak_years": 5})
        self.assertIn("36.67B", response.text)
        self.assertIn("537.40M", response.text)
        # No scientific notation, and small columns are left alone.
        self.assertNotIn("e+10", response.text)
        self.assertIn("3.5", response.text)

    def test_export_csv_keeps_raw_large_numbers(self):
        self.mocks['helper_functions'].radar_dict_to_table.return_value = pandas.DataFrame(
            {"Market Cap": [3.6671e10]}, index=["AAPL"]
        )
        response = self.client.post("/export.csv", data={"min_streak_years": 5})
        # CSV stays unformatted (no abbreviation) so the precise value is preserved.
        self.assertIn("36671000000", response.text)
        self.assertNotIn("36.67B", response.text)

    # ── CSV export ────────────────────────────────────────────────────────

    def test_export_csv_returns_csv_download(self):
        self.mocks['helper_functions'].radar_dict_to_table.return_value = pandas.DataFrame(
            {"Price": [150.0, 300.0]}, index=["AAPL", "MSFT"]
        )
        response = self.client.post("/export.csv", data={
            "min_streak_years": 5, "yield_range_min": 0.0, "yield_range_max": 10.0,
            "min_dgr": 0.0, "chowder_number": 0, "price_range_min": 1.0,
            "price_range_max": 500.0, "fair_value": 0, "min_revenue": 0.0, "min_npm": 0.0,
            "min_cf_per_share": 0.0, "min_roe": 0.0, "pe_range_min": -50.0,
            "pe_range_max": 100.0, "max_price_per_book_value": 10.0,
            "max_debt_per_capital_value": 1.0, "max_payout_ratio": 100.0,
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.headers["content-type"].startswith("text/csv"))
        self.assertIn("attachment; filename=divifilter_export.csv", response.headers["content-disposition"])
        # Ticker (index) and a column both appear in the CSV body.
        self.assertIn("AAPL", response.text)
        self.assertIn("Price", response.text)

    def test_export_csv_calls_run_filter_query(self):
        self.mock_mysql.run_filter_query.reset_mock()
        self.client.post("/export.csv", data={
            "min_streak_years": 5, "yield_range_min": 0.0, "yield_range_max": 10.0,
            "min_dgr": 0.0, "chowder_number": 0, "price_range_min": 1.0,
            "price_range_max": 500.0, "fair_value": 0, "min_revenue": 0.0, "min_npm": 0.0,
            "min_cf_per_share": 0.0, "min_roe": 0.0, "pe_range_min": -50.0,
            "pe_range_max": 100.0, "max_price_per_book_value": 10.0,
            "max_debt_per_capital_value": 1.0, "max_payout_ratio": 100.0,
            "excluded_symbols": ["AAPL"],
        })
        self.mock_mysql.run_filter_query.assert_called_once()
        # The exclusion list is forwarded to the same DB method as /filter.
        self.assertIn("AAPL", self.mock_mysql.run_filter_query.call_args[0][17])

    # ── Structural / Layout ──────────────────────────────────────────────

    def test_index_contains_sidebar(self):
        response = self.client.get("/")
        self.assertIn('id="sidebarOffcanvas"', response.text)

    def test_index_contains_results_div(self):
        response = self.client.get("/")
        self.assertIn('id="results"', response.text)

    def test_index_contains_main_col(self):
        response = self.client.get("/")
        self.assertIn('id="main-col"', response.text)

    # ── HTMX attributes ───────────────────────────────────────────────

    def test_index_form_has_htmx_target(self):
        response = self.client.get("/")
        self.assertIn('hx-target="#results"', response.text)

    def test_index_form_has_htmx_trigger(self):
        response = self.client.get("/")
        self.assertIn('hx-trigger=', response.text)
        self.assertIn('load', response.text)

    def test_index_form_has_htmx_swap(self):
        response = self.client.get("/")
        self.assertIn('hx-swap="innerHTML"', response.text)

    # ── Loading spinners ──────────────────────────────────────────────

    def test_index_contains_inline_spinner(self):
        response = self.client.get("/")
        self.assertIn('id="spinner"', response.text)

    def test_index_contains_initial_loading_spinner(self):
        response = self.client.get("/")
        self.assertIn('class="initial-loader"', response.text)
        self.assertIn('spinner-border text-primary', response.text)
        self.assertIn('class="shimmer-text"', response.text)

    # ── Filter sections (collapsible) ─────────────────────────────────

    def test_index_contains_dividend_section(self):
        response = self.client.get("/")
        self.assertIn('id="collapse-dividend"', response.text)

    def test_index_contains_financial_section(self):
        response = self.client.get("/")
        self.assertIn('id="collapse-financial"', response.text)

    def test_index_contains_exclusions_section(self):
        response = self.client.get("/")
        self.assertIn('id="collapse-exclusions"', response.text)

    def test_index_contains_presets_section(self):
        response = self.client.get("/")
        self.assertIn('id="collapse-presets"', response.text)
        self.assertIn('id="preset-select"', response.text)
        self.assertIn('id="btn-save-preset"', response.text)
        self.assertIn('id="btn-delete-preset"', response.text)
        self.assertNotIn('id="preset-name"', response.text)
        self.assertNotIn('id="btn-load-preset"', response.text)

    # ── Sliders ───────────────────────────────────────────────────────

    def test_index_contains_all_sliders(self):
        response = self.client.get("/")
        slider_ids = [
            'sl-streak', 'sl-yield', 'sl-dgr', 'sl-chowder',
            'sl-price', 'sl-fv', 'sl-revenue', 'sl-npm',
            'sl-cf', 'sl-roe', 'sl-pe', 'sl-pbv', 'sl-debt', 'sl-payout',
        ]
        for sid in slider_ids:
            with self.subTest(slider=sid):
                self.assertIn(f'id="{sid}"', response.text)

    # ── Multiselects ──────────────────────────────────────────────────

    def test_index_contains_exclusion_selects(self):
        response = self.client.get("/")
        for sel_id in ['sel-symbols', 'sel-sectors', 'sel-industries']:
            with self.subTest(select=sel_id):
                self.assertIn(f'id="{sel_id}"', response.text)

    def test_index_exclusion_selects_have_options(self):
        response = self.client.get("/")
        self.assertIn('<option value="AAPL">AAPL</option>', response.text)
        self.assertIn('<option value="MSFT">MSFT</option>', response.text)

    # ── Settings menu ────────────────────────────────────────────────

    def test_index_contains_settings_menu(self):
        response = self.client.get("/")
        self.assertIn('id="settings-toggle"', response.text)
        self.assertIn('id="darkmode-switch"', response.text)
        self.assertIn('id="disclaimerModal"', response.text)

    def test_index_contains_export_share_reset_controls(self):
        response = self.client.get("/")
        self.assertIn('id="btn-export-csv"', response.text)
        self.assertIn('id="btn-share-filter"', response.text)
        self.assertIn('id="btn-reset-filters"', response.text)

    def test_index_contains_results_search(self):
        response = self.client.get("/")
        self.assertIn('id="results-search"', response.text)

    # ── Google Analytics ─────────────────────────────────────────────

    def test_index_no_ga_when_id_empty(self):
        response = self.client.get("/")
        self.assertNotIn("googletagmanager.com/gtag/js", response.text)

    def test_index_ga_script_when_id_set(self):
        self.app_module.configuration["ga_measurement_id"] = "G-TESTID123"
        response = self.client.get("/")
        self.assertIn("googletagmanager.com/gtag/js?id=G-TESTID123", response.text)
        self.assertIn("gtag('config', 'G-TESTID123')", response.text)
        self.app_module.configuration["ga_measurement_id"] = ""

    # ── Slider range values from DB ───────────────────────────────────

    def test_index_slider_ranges_use_db_values(self):
        response = self.client.get("/")
        # price_max comes from mock: 500.0
        self.assertIn('500.0', response.text)
        # pe_min comes from mock: max(-50.0, -50.0) = -50.0
        self.assertIn('-50.0', response.text)
        # pe_max comes from mock: min(100.0, 100.0) = 100.0
        self.assertIn('100.0', response.text)

    def test_post_filter_row_count_in_response(self):
        self.mocks['helper_functions'].radar_dict_to_table.return_value = pandas.DataFrame(
            {"Symbol": ["AAPL", "MSFT"], "Price": [150.0, 300.0]}
        )
        response = self.client.post("/filter", data={
            "min_streak_years": 5,
            "yield_range_min": 0.0,
            "yield_range_max": 10.0,
            "min_dgr": 0.0,
            "chowder_number": 0,
            "price_range_min": 1.0,
            "price_range_max": 500.0,
            "fair_value": 0,
            "min_revenue": 0.0,
            "min_npm": 0.0,
            "min_cf_per_share": 0.0,
            "min_roe": 0.0,
            "pe_range_min": -50.0,
            "pe_range_max": 100.0,
            "max_price_per_book_value": 10.0,
            "max_debt_per_capital_value": 1.0,
            "max_payout_ratio": 100.0,
        })
        self.assertIn("2 stock(s) found", response.text)
