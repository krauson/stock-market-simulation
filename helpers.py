import os
import requests
import urllib.parse

from cs50 import SQL
from flask import redirect, render_template, request, session
from functools import wraps

db = SQL("sqlite:///finance.db")


def update_stocks_price(stock_symbol):
    stocks_summary = db.execute("SELECT symbol, SUM(shares) as total shares from purchases WHERE user_id = ?  GROUP BY symbol", session.get("user_id"))

    stocks_symbols = db.execute("SELECT DISTINCT(symbol) from purchases")
    print(stocks_symbols)
    stock_cur_prices = {}
    for stock in stocks_summary:
        stock_symbol = stocks_summary["symbol"]
        stock_data = lookup(stock_symbol)
        stock_cur_prices[symbol] = stock_data["price"]
        db.execute("UPDATE purchases SET stock_price = ? WHERE id = ?")
    
    return stocks_summary


def get_user_data(session):
    stocks_summary = db.execute("SELECT symbol, SUM(shares) as total shares from purchases WHERE user_id = ?  GROUP BY symbol", session.get("user_id"))

    stock_data = lookup(stocks_summary["symbol"])


def apology(message, code=400):
    """Render message as an apology to user."""
    def escape(s):
        """
        Escape special characters.

        https://github.com/jacebrowning/memegen#special-characters
        """
        for old, new in [("-", "--"), (" ", "-"), ("_", "__"), ("?", "~q"),
                         ("%", "~p"), ("#", "~h"), ("/", "~s"), ("\"", "''")]:
            s = s.replace(old, new)
        return s
    return render_template("apology.html", top=code, bottom=escape(message)), code


def login_required(f):
    """
    Decorate routes to require login.

    https://flask.palletsprojects.com/en/1.1.x/patterns/viewdecorators/
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function


def lookup(symbol):
    """Look up quote for symbol."""

    # Contact API
    try:
        api_key = os.environ.get("API_KEY")
        url = f"https://cloud.iexapis.com/stable/stock/{urllib.parse.quote_plus(symbol)}/quote?token={api_key}"
        response = requests.get(url)
        response.raise_for_status()
    except requests.RequestException:
        return None

    # Parse response
    try:
        quote = response.json()
        return {
            "name": quote["companyName"],
            "price": float(quote["latestPrice"]),
            "symbol": quote["symbol"]
        }
    except (KeyError, TypeError, ValueError):
        return None


def usd(value):
    """Format value as USD."""
    return f"${value:,.2f}"
