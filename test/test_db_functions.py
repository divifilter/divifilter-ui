import unittest
from unittest.mock import patch, MagicMock
from dividend_stocks_filterer.db_functions import MysqlConnection


class TestMysqlConnection(unittest.TestCase):

    @patch('dividend_stocks_filterer.db_functions.PooledDB')
    def setUp(self, mock_pooled_db_cls):
        # Each PooledDB instance is a separate mock
        self.mock_pool = MagicMock()
        self.mock_dict_pool = MagicMock()
        mock_pooled_db_cls.side_effect = [self.mock_pool, self.mock_dict_pool]

        # Set up default mock connections and cursors
        self.mock_conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.mock_conn.cursor.return_value = self.mock_cursor
        self.mock_pool.connection.return_value = self.mock_conn

        self.mock_dict_conn = MagicMock()
        self.mock_dict_cursor = MagicMock()
        self.mock_dict_conn.cursor.return_value = self.mock_dict_cursor
        self.mock_dict_pool.connection.return_value = self.mock_dict_conn

        self.db = MysqlConnection(
            db_host="localhost", db_port=3306, db_user="root",
            db_password="pass", db_schema="testdb"
        )

    def test_init_creates_two_pools(self):
        self.assertIs(self.db._pool, self.mock_pool)
        self.assertIs(self.db._dict_pool, self.mock_dict_pool)

    def test_run_sql_query_tuple(self):
        self.mock_cursor.fetchall.return_value = [("row1",), ("row2",)]

        result = self.db.run_sql_query("SELECT 1", "tuple")

        self.mock_cursor.execute.assert_called_once_with("SELECT 1")
        self.assertEqual(result, [("row1",), ("row2",)])

    def test_run_sql_query_dict(self):
        self.mock_dict_cursor.fetchall.return_value = [{"col": "val"}]

        result = self.db.run_sql_query("SELECT 1", "dict")

        self.mock_dict_cursor.execute.assert_called_once_with("SELECT 1")
        self.assertEqual(result, [{"col": "val"}])

    def test_run_sql_query_invalid_mode_raises(self):
        with self.assertRaises(ValueError):
            self.db.run_sql_query("SELECT 1", "invalid")

    def test_check_db_update_dates(self):
        self.mock_cursor.fetchall.return_value = [
            ("radar_file", "2024-01-01"),
            ("yahoo_finance", "2024-01-02")
        ]

        result = self.db.check_db_update_dates()

        self.assertEqual(result, {"radar_file": "2024-01-01", "yahoo_finance": "2024-01-02"})

    def test_min_max_all_values_maps_row_to_keys(self):
        # 28 aggregate values in the SELECT, returned as one row of 28 columns.
        row = tuple(float(i) for i in range(28))
        self.mock_cursor.fetchall.return_value = [row]

        result = self.db.min_max_all_values()

        executed_query = self.mock_cursor.execute.call_args[0][0]
        self.assertIn("MAX(`Div Yield`)", executed_query)
        self.assertIn("MAX(`Payout Ratio`)", executed_query)
        # First and last keys map to the first and last selected aggregates.
        self.assertEqual(result["yield_max_raw"], 0.0)
        self.assertEqual(result["payout_ratio_max_raw"], 27.0)
        self.assertEqual(len(result), 28)

    def test_list_values_of_key_in_db(self):
        self.mock_cursor.fetchall.return_value = [("AAPL",), ("MSFT",), ("GOOG",)]

        result = self.db.list_values_of_key_in_db("Symbol")

        self.assertEqual(result, ["AAPL", "MSFT", "GOOG"])
        executed_query = self.mock_cursor.execute.call_args[0][0]
        self.assertIn("DISTINCT", executed_query)
        self.assertIn("Symbol", executed_query)

    def test_run_filter_query_no_exclusions(self):
        self.mock_dict_cursor.fetchall.return_value = [
            {"Symbol": "AAPL", "Price": 150.0},
            {"Symbol": "MSFT", "Price": 300.0}
        ]

        result = self.db.run_filter_query(
            min_streak_years=10, yield_range_min=0.0, yield_range_max=10.0,
            min_dgr=0.0, chowder_number=0, price_range_min=1.0, price_range_max=500.0,
            fair_value=25, min_revenue=0.0, min_npm=0.0,
            min_cf_per_share=0.0, min_roe=0.0, pe_range_min=0.0, pe_range_max=50.0,
            max_price_per_book_value=100.0, max_debt_per_capital_value=1.0,
            max_payout_ratio=100.0,
            excluded_symbols=[], excluded_sectors=[], excluded_industries=[]
        )

        self.assertEqual(len(result), 2)
        self.assertIn("AAPL", result)
        self.assertIn("MSFT", result)
        executed_query = self.mock_dict_cursor.execute.call_args[0][0]
        self.assertNotIn("NOT IN", executed_query)

    def test_run_filter_query_with_exclusions(self):
        self.mock_dict_cursor.fetchall.return_value = [
            {"Symbol": "MSFT", "Price": 300.0}
        ]

        result = self.db.run_filter_query(
            min_streak_years=10, yield_range_min=0.0, yield_range_max=10.0,
            min_dgr=0.0, chowder_number=0, price_range_min=1.0, price_range_max=500.0,
            fair_value=25, min_revenue=0.0, min_npm=0.0,
            min_cf_per_share=0.0, min_roe=0.0, pe_range_min=0.0, pe_range_max=50.0,
            max_price_per_book_value=100.0, max_debt_per_capital_value=1.0,
            max_payout_ratio=100.0,
            excluded_symbols=["AAPL"], excluded_sectors=["Technology"],
            excluded_industries=["Software"]
        )

        self.assertEqual(len(result), 1)
        self.assertIn("MSFT", result)
        executed_query = self.mock_dict_cursor.execute.call_args[0][0]
        executed_params = self.mock_dict_cursor.execute.call_args[0][1]
        # Exclusion columns and placeholders are in the query; the values are bound params, not interpolated.
        self.assertIn("`Symbol` NOT IN", executed_query)
        self.assertIn("`Sector` NOT IN", executed_query)
        self.assertIn("`Industry` NOT IN", executed_query)
        self.assertIn("AAPL", executed_params)
        self.assertIn("Technology", executed_params)
        self.assertIn("Software", executed_params)
        # The raw values must NOT appear quoted in the SQL string itself.
        self.assertNotIn("'AAPL'", executed_query)

    def test_run_sql_query_default_mode(self):
        self.mock_cursor.fetchall.return_value = [("row1",)]

        result = self.db.run_sql_query("SELECT 1")

        self.mock_pool.connection.assert_called()
        self.mock_dict_pool.connection.assert_not_called()
        self.assertEqual(result, [("row1",)])

    def test_run_sql_query_empty_result(self):
        self.mock_cursor.fetchall.return_value = []

        result = self.db.run_sql_query("SELECT 1")

        self.assertEqual(result, [])

    def test_check_db_update_dates_empty(self):
        self.mock_cursor.fetchall.return_value = []

        result = self.db.check_db_update_dates()

        self.assertEqual(result, {})

    def test_check_db_update_dates_single_row(self):
        self.mock_cursor.fetchall.return_value = [("radar_file", "2024-01-01")]

        result = self.db.check_db_update_dates()

        self.assertEqual(result, {"radar_file": "2024-01-01"})

    def test_list_values_of_key_rejects_unlisted_column(self):
        # Guards against arbitrary column identifiers reaching the SQL string.
        with self.assertRaises(ValueError):
            self.db.list_values_of_key_in_db("Symbol; DROP TABLE dividend_data_table")
        self.mock_cursor.execute.assert_not_called()

    def test_list_values_of_key_empty_result(self):
        self.mock_cursor.fetchall.return_value = []

        result = self.db.list_values_of_key_in_db("Symbol")

        self.assertEqual(result, [])

    def test_list_values_of_key_single_result(self):
        self.mock_cursor.fetchall.return_value = [("AAPL",)]

        result = self.db.list_values_of_key_in_db("Symbol")

        self.assertEqual(result, ["AAPL"])

    def test_run_filter_query_empty_result(self):
        self.mock_dict_cursor.fetchall.return_value = []

        result = self.db.run_filter_query(
            min_streak_years=10, yield_range_min=0.0, yield_range_max=10.0,
            min_dgr=0.0, chowder_number=0, price_range_min=1.0, price_range_max=500.0,
            fair_value=25, min_revenue=0.0, min_npm=0.0,
            min_cf_per_share=0.0, min_roe=0.0, pe_range_min=0.0, pe_range_max=50.0,
            max_price_per_book_value=100.0, max_debt_per_capital_value=1.0,
            max_payout_ratio=100.0,
            excluded_symbols=[], excluded_sectors=[], excluded_industries=[]
        )

        self.assertEqual(result, {})

    def test_run_filter_query_partial_exclusions_symbols_only(self):
        self.mock_dict_cursor.fetchall.return_value = []

        self.db.run_filter_query(
            min_streak_years=5, yield_range_min=0.0, yield_range_max=10.0,
            min_dgr=0.0, chowder_number=0, price_range_min=1.0, price_range_max=500.0,
            fair_value=25, min_revenue=0.0, min_npm=0.0,
            min_cf_per_share=0.0, min_roe=0.0, pe_range_min=0.0, pe_range_max=50.0,
            max_price_per_book_value=100.0, max_debt_per_capital_value=1.0,
            max_payout_ratio=100.0,
            excluded_symbols=["AAPL"], excluded_sectors=[], excluded_industries=[]
        )

        executed_query = self.mock_dict_cursor.execute.call_args[0][0]
        self.assertIn("`Symbol` NOT IN", executed_query)
        self.assertNotIn("`Sector` NOT IN", executed_query)
        self.assertNotIn("`Industry` NOT IN", executed_query)

    def test_run_filter_query_partial_exclusions_sectors_only(self):
        self.mock_dict_cursor.fetchall.return_value = []

        self.db.run_filter_query(
            min_streak_years=5, yield_range_min=0.0, yield_range_max=10.0,
            min_dgr=0.0, chowder_number=0, price_range_min=1.0, price_range_max=500.0,
            fair_value=25, min_revenue=0.0, min_npm=0.0,
            min_cf_per_share=0.0, min_roe=0.0, pe_range_min=0.0, pe_range_max=50.0,
            max_price_per_book_value=100.0, max_debt_per_capital_value=1.0,
            max_payout_ratio=100.0,
            excluded_symbols=[], excluded_sectors=["Energy"], excluded_industries=[]
        )

        executed_query = self.mock_dict_cursor.execute.call_args[0][0]
        self.assertNotIn("`Symbol` NOT IN", executed_query)
        self.assertIn("`Sector` NOT IN", executed_query)
        self.assertNotIn("`Industry` NOT IN", executed_query)

    def test_run_filter_query_partial_exclusions_industries_only(self):
        self.mock_dict_cursor.fetchall.return_value = []

        self.db.run_filter_query(
            min_streak_years=5, yield_range_min=0.0, yield_range_max=10.0,
            min_dgr=0.0, chowder_number=0, price_range_min=1.0, price_range_max=500.0,
            fair_value=25, min_revenue=0.0, min_npm=0.0,
            min_cf_per_share=0.0, min_roe=0.0, pe_range_min=0.0, pe_range_max=50.0,
            max_price_per_book_value=100.0, max_debt_per_capital_value=1.0,
            max_payout_ratio=100.0,
            excluded_symbols=[], excluded_sectors=[], excluded_industries=["Banking"]
        )

        executed_query = self.mock_dict_cursor.execute.call_args[0][0]
        self.assertNotIn("`Symbol` NOT IN", executed_query)
        self.assertNotIn("`Sector` NOT IN", executed_query)
        self.assertIn("`Industry` NOT IN", executed_query)

    def test_run_filter_query_verifies_all_filter_columns(self):
        self.mock_dict_cursor.fetchall.return_value = []

        self.db.run_filter_query(
            min_streak_years=5, yield_range_min=1.0, yield_range_max=8.0,
            min_dgr=2.0, chowder_number=10, price_range_min=20.0, price_range_max=200.0,
            fair_value=15, min_revenue=3.0, min_npm=5.0,
            min_cf_per_share=1.5, min_roe=10.0, pe_range_min=5.0, pe_range_max=30.0,
            max_price_per_book_value=50.0, max_debt_per_capital_value=0.8,
            max_payout_ratio=60.0,
            excluded_symbols=[], excluded_sectors=[], excluded_industries=[]
        )

        executed_query = self.mock_dict_cursor.execute.call_args[0][0]
        executed_params = self.mock_dict_cursor.execute.call_args[0][1]
        # `FV %` is escaped to `FV %%` in the parameterized query string.
        for col in ["`No Years`", "`Div Yield`", "`5Y Avg Yield`", "`DGR 1Y`", "`DGR 3Y`",
                    "`DGR 5Y`", "`DGR 10Y`", "`Chowder Number`", "`Price`", "`FV %%`",
                    "`Revenue 1Y`", "`NPM`", "`CF/Share`", "`ROE`", "`P/E`", "`P/BV`",
                    "`Debt/Capital`", "`Payout Ratio`"]:
            self.assertIn(col, executed_query)
        # Verify specific filter values are passed as bound params (not interpolated into the query string).
        self.assertIn(5, executed_params)    # min_streak_years
        self.assertIn(10, executed_params)   # chowder_number
        self.assertIn(15, executed_params)   # fair_value

    def test_run_filter_query_uses_dict_pool(self):
        self.mock_dict_cursor.fetchall.return_value = [{"Symbol": "AAPL", "Price": 150.0}]

        self.db.run_filter_query(
            min_streak_years=5, yield_range_min=0.0, yield_range_max=10.0,
            min_dgr=0.0, chowder_number=0, price_range_min=1.0, price_range_max=500.0,
            fair_value=25, min_revenue=0.0, min_npm=0.0,
            min_cf_per_share=0.0, min_roe=0.0, pe_range_min=0.0, pe_range_max=50.0,
            max_price_per_book_value=100.0, max_debt_per_capital_value=1.0,
            max_payout_ratio=100.0,
            excluded_symbols=[], excluded_sectors=[], excluded_industries=[]
        )

        self.mock_dict_pool.connection.assert_called()
        self.mock_pool.connection.assert_not_called()

    def test_run_filter_query_multiple_exclusion_values(self):
        self.mock_dict_cursor.fetchall.return_value = []

        self.db.run_filter_query(
            min_streak_years=5, yield_range_min=0.0, yield_range_max=10.0,
            min_dgr=0.0, chowder_number=0, price_range_min=1.0, price_range_max=500.0,
            fair_value=25, min_revenue=0.0, min_npm=0.0,
            min_cf_per_share=0.0, min_roe=0.0, pe_range_min=0.0, pe_range_max=50.0,
            max_price_per_book_value=100.0, max_debt_per_capital_value=1.0,
            max_payout_ratio=100.0,
            excluded_symbols=["AAPL", "MSFT", "GOOG"], excluded_sectors=[],
            excluded_industries=[]
        )

        executed_query = self.mock_dict_cursor.execute.call_args[0][0]
        executed_params = self.mock_dict_cursor.execute.call_args[0][1]
        # Three placeholders for three excluded symbols, values bound as params.
        self.assertIn("`Symbol` NOT IN (%s, %s, %s)", executed_query)
        self.assertIn("AAPL", executed_params)
        self.assertIn("MSFT", executed_params)
        self.assertIn("GOOG", executed_params)

    def test_run_filter_query_exclusion_values_are_parameterized_not_injectable(self):
        """A malicious exclusion value must be bound as a parameter, never interpolated into the SQL string."""
        self.mock_dict_cursor.fetchall.return_value = []
        malicious = "AAPL'); DROP TABLE dividend_data_table; --"

        self.db.run_filter_query(
            min_streak_years=5, yield_range_min=0.0, yield_range_max=10.0,
            min_dgr=0.0, chowder_number=0, price_range_min=1.0, price_range_max=500.0,
            fair_value=25, min_revenue=0.0, min_npm=0.0,
            min_cf_per_share=0.0, min_roe=0.0, pe_range_min=0.0, pe_range_max=50.0,
            max_price_per_book_value=100.0, max_debt_per_capital_value=1.0,
            max_payout_ratio=100.0,
            excluded_symbols=[malicious], excluded_sectors=[], excluded_industries=[]
        )

        executed_query = self.mock_dict_cursor.execute.call_args[0][0]
        executed_params = self.mock_dict_cursor.execute.call_args[0][1]
        # The dangerous string is carried only as a bound parameter...
        self.assertIn(malicious, executed_params)
        # ...and never appears in the SQL text, so it cannot terminate the statement or inject a new one.
        self.assertNotIn("DROP TABLE", executed_query)
        self.assertNotIn(malicious, executed_query)

    def test_run_sql_query_passes_params_to_execute(self):
        self.mock_cursor.fetchall.return_value = []

        self.db.run_sql_query("SELECT * FROM t WHERE a = %s", "tuple", ["x"])

        self.mock_cursor.execute.assert_called_once_with("SELECT * FROM t WHERE a = %s", ["x"])

    def test_run_sql_query_returns_connection_to_pool(self):
        self.mock_cursor.fetchall.return_value = [("row1",)]

        self.db.run_sql_query("SELECT 1", "tuple")

        self.mock_conn.close.assert_called_once()

    def test_run_sql_query_returns_connection_on_error(self):
        self.mock_cursor.execute.side_effect = Exception("DB error")

        with self.assertRaises(Exception):
            self.db.run_sql_query("SELECT 1", "tuple")

        self.mock_conn.close.assert_called_once()
