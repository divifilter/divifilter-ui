import pymysql
from dbutils.pooled_db import PooledDB
from typing import List


class MysqlConnection:

    def __init__(self, db_host: str, db_port: int, db_user: str, db_password: str, db_schema: str):
        """
            Initializes a new instance of the MysqlConnection class.

            Args:
                db_host (str): The hostname of the MySQL server.
                db_port (int): The port number of the MySQL server.
                db_user (str): The username for connecting to the MySQL server.
                db_password (str): The password for connecting to the MySQL server.
                db_schema (str): The name of the MySQL schema (database).

            Returns:
                None
            """
        pool_kwargs = dict(
            creator=pymysql, host=db_host, port=db_port, user=db_user,
            passwd=db_password, db=db_schema,
            connect_timeout=10, read_timeout=30,
            mincached=0, maxcached=2, maxconnections=3, blocking=True, ping=1,
        )
        self._pool = PooledDB(**pool_kwargs)
        self._dict_pool = PooledDB(**pool_kwargs, cursorclass=pymysql.cursors.DictCursor)

    def run_sql_query(self, sql_query: str, tuple_or_dict: str = "tuple", params=None) -> list:
        """
        Executes a SQL query on the database.

        Args:
            sql_query (str): The SQL query to execute.
            tuple_or_dict: a string of either "tuple" or "dict" to tell what format you want the response returned at.
            params: optional sequence of values for a parameterized query. When provided, the values are passed to
                the driver's execute() so they are safely escaped (prevents SQL injection); when None the query is
                executed as-is. Note: pymysql treats a literal "%" as a format marker once params are passed, so any
                static "%" in the query (e.g. the `FV %` column) must be written as "%%".

        Returns:
            list: A list of tuples containing the query response.
        """
        if tuple_or_dict == "tuple":
            pool = self._pool
        elif tuple_or_dict == "dict":
            pool = self._dict_pool
        else:
            raise ValueError
        conn = pool.connection()
        try:
            cur = conn.cursor()
            if params is None:
                cur.execute(sql_query)
            else:
                cur.execute(sql_query, params)
            query_response = cur.fetchall()
            cur.close()
            return query_response
        finally:
            conn.close()

    def check_db_update_dates(self) -> dict:
        """
            Checks the database for update dates.

            Returns:
                dict: A dictionary containing the query response.
            """
        db_update_query = "SELECT * FROM dividend_update_times"
        return dict(self.run_sql_query(db_update_query))

    def min_max_all_values(self) -> dict:
        """
        Fetches all min/max aggregate values needed for slider ranges in a single SQL query.

        Returns:
            dict: A dictionary mapping internal keys to their raw min/max DB values.
        """
        query = """
            SELECT
                MAX(`Div Yield`), MAX(`5Y Avg Yield`),
                MIN(`DGR 1Y`), MAX(`DGR 1Y`),
                MIN(`DGR 3Y`), MAX(`DGR 3Y`),
                MIN(`DGR 5Y`), MAX(`DGR 5Y`),
                MIN(`DGR 10Y`), MAX(`DGR 10Y`),
                MAX(`Chowder Number`),
                MAX(`Price`),
                MIN(`FV %`), MAX(`FV %`),
                MIN(`Revenue 1Y`), MAX(`Revenue 1Y`),
                MIN(`NPM`), MAX(`NPM`),
                MIN(`CF/Share`), MAX(`CF/Share`),
                MIN(`ROE`), MAX(`ROE`),
                MIN(`P/E`), MAX(`P/E`),
                MIN(`P/BV`), MAX(`P/BV`),
                MAX(`Debt/Capital`),
                MAX(`Payout Ratio`)
            FROM dividend_data_table
            WHERE `Div Yield` IS NOT NULL;
        """
        row = self.run_sql_query(query)[0]
        keys = [
            'yield_max_raw', '5y_yield_max',
            'dgr1y_min', 'dgr1y_max', 'dgr3y_min', 'dgr3y_max',
            'dgr5y_min', 'dgr5y_max', 'dgr10y_min', 'dgr10y_max',
            'chowder_max_raw', 'price_max_raw',
            'fv_min_raw', 'fv_max_raw',
            'revenue_min', 'revenue_max',
            'npm_min', 'npm_max',
            'cf_min', 'cf_max',
            'roe_min', 'roe_max',
            'pe_min_raw', 'pe_max_raw',
            'pbv_min', 'pbv_max',
            'debt_max_raw',
            'payout_ratio_max_raw',
        ]
        return dict(zip(keys, row))

    # Columns whose distinct values may be listed (used to populate the exclusion dropdowns). A SQL identifier
    # cannot be passed as a bound parameter, so we restrict it to this allowlist instead of interpolating freely.
    LISTABLE_COLUMNS = ("Symbol", "Sector", "Industry")

    def list_values_of_key_in_db(self, key_to_list: str) -> list:
        """
        Retrieve the list of distinct values for one column of 'dividend_data_table'.

        Args:
            key_to_list (str): The column whose distinct values to return. Must be one of LISTABLE_COLUMNS.

        Returns:
            list: Distinct values of the column.

        Raises:
            ValueError: if key_to_list is not an allowlisted column.
        """
        if key_to_list not in self.LISTABLE_COLUMNS:
            raise ValueError("Unsupported column for listing: {}".format(key_to_list))

        # key_to_list is constrained to the LISTABLE_COLUMNS allowlist above, so this is not an injection vector.
        query = "SELECT DISTINCT `" + key_to_list + "` FROM dividend_data_table;"  # nosec B608

        # Execute the query and fetch the results
        result = self.run_sql_query(query)

        # Extract the tickers from the result set
        tickers = [row[0] for row in result]

        return tickers

    def run_filter_query(self, min_streak_years: int, yield_range_min: float, yield_range_max: float,
                         min_dgr: float, chowder_number: float, price_range_min: float, price_range_max: float,
                         fair_value: float, min_revenue: float, min_npm: float, min_cf_per_share: float,
                         min_roe: float, pe_range_min: float, pe_range_max: float, max_price_per_book_value: float,
                         max_debt_per_capital_value: float, max_payout_ratio: float,
                         excluded_symbols: List[str], excluded_sectors: List[str],
                         excluded_industries: List[str]) -> dict:
        """
        Run a filter query on the database to fetch records based on specified criteria.

        Args:
            min_streak_years (int): Minimum number of streak years.
            yield_range_min (float): Minimum dividend yield range.
            yield_range_max (float): Maximum dividend yield range.
            min_dgr (float): Minimum Dividend Growth Rate (DGR).
            chowder_number (float): Chowder Number threshold.
            price_range_min (float): Minimum price range.
            price_range_max (float): Maximum price range.
            fair_value (float): Fair value threshold.
            min_revenue (float): Minimum revenue.
            min_npm (float): Minimum Net Profit Margin (NPM).
            min_cf_per_share (float): Minimum Cash Flow Per Share.
            min_roe (float): Minimum Return on Equity (ROE).
            pe_range_min (float): Minimum Price to Earnings (P/E) ratio range.
            pe_range_max (float): Maximum Price to Earnings (P/E) ratio range.
            max_price_per_book_value (float): Maximum Price to Book (P/BV) value.
            max_debt_per_capital_value (float): Maximum Debt to Capital value.
            max_payout_ratio (float): Maximum Payout Ratio (dividends per share / earnings per share).
            excluded_symbols (List[str]): List of symbols to be excluded.
            excluded_sectors (List[str]): List of sectors to be excluded.
            excluded_industries (List[str]): List of industries to be excluded.

        Returns:
            dict: Dictionary containing the query response.
        """
        # Build a fully parameterized query. Every user-supplied value is passed as a bound parameter (%s) rather
        # than interpolated into the SQL string, so values such as stock symbols cannot break out and inject SQL.
        # The literal "%" in the `FV %` column is escaped as "%%" because pymysql runs %-formatting once params
        # are supplied.
        filter_query = """
            SELECT *
            FROM dividend_data_table
            WHERE
                (`No Years` >= %s OR `No Years` IS NULL)
                AND (`Div Yield` BETWEEN %s AND %s OR `Div Yield` IS NULL)
                AND (`5Y Avg Yield` BETWEEN %s AND %s OR `5Y Avg Yield` IS NULL)
                AND (`DGR 1Y` >= %s OR `DGR 1Y` IS NULL)
                AND (`DGR 3Y` >= %s OR `DGR 3Y` IS NULL)
                AND (`DGR 5Y` >= %s OR `DGR 5Y` IS NULL)
                AND (`DGR 10Y` >= %s OR `DGR 10Y` IS NULL)
                AND (`Chowder Number` >= %s OR `Chowder Number` IS NULL)
                AND (`Price` BETWEEN %s AND %s OR `Price` IS NULL)
                AND (`FV %%` <= %s OR `FV %%` IS NULL)
                AND (`Revenue 1Y` >= %s OR `Revenue 1Y` IS NULL)
                AND (`NPM` >= %s OR `NPM` IS NULL)
                AND (`CF/Share` >= %s OR `CF/Share` IS NULL)
                AND (`ROE` >= %s OR `ROE` IS NULL)
                AND (`P/E` BETWEEN %s AND %s OR `P/E` IS NULL)
                AND (`P/BV` <= %s OR `P/BV` IS NULL)
                AND (`Debt/Capital` <= %s OR `Debt/Capital` IS NULL)
                AND (`Payout Ratio` <= %s OR `Payout Ratio` IS NULL)
        """
        params = [
            min_streak_years,
            yield_range_min, yield_range_max,
            yield_range_min, yield_range_max,
            min_dgr, min_dgr, min_dgr, min_dgr,
            chowder_number,
            price_range_min, price_range_max,
            fair_value,
            min_revenue, min_npm, min_cf_per_share, min_roe,
            pe_range_min, pe_range_max,
            max_price_per_book_value, max_debt_per_capital_value,
            max_payout_ratio,
        ]

        # Add NOT IN clauses only if the exclusion lists are not empty, using one bound parameter per value.
        for column, excluded_values in (
            ("Symbol", excluded_symbols),
            ("Sector", excluded_sectors),
            ("Industry", excluded_industries),
        ):
            if excluded_values:
                placeholders = ", ".join(["%s"] * len(excluded_values))
                filter_query += "AND `{}` NOT IN ({}) ".format(column, placeholders)
                params.extend(excluded_values)

        # Add semicolon to the end of the query
        filter_query += ";"

        # Execute the SQL query
        results = self.run_sql_query(filter_query, "dict", params)

        # Convert results into the desired dictionary format
        output_dict = {}
        for row in results:
            # Extract symbol from the row
            symbol = row['Symbol']
            # Update output dictionary
            output_dict[symbol] = row

        return output_dict
