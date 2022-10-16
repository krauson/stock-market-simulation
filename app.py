from asyncio.log import logger
import logging
import os

from datetime import datetime
from config import FLASK_DEBUG
from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd
from typing import Dict, List

# Configure application
app = Flask(__name__)


# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True


# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

create_users_table = """CREATE TABLE IF NOT EXISTS users (
                                    id INTEGER PRIMARY KEY,
                                    username TEXT,
                                    hash TEXT,
                                    cash INTEGER
                                );"""

create_purchases_table = """CREATE TABLE IF NOT EXISTS purchases (
                                    user_id INTEGER,
                                    symbol TEXT,
                                    shares INTEGER,
                                    stock_price INTEGER,
                                    total_price INTEGER,
                                    time_stamp TIMESTAMP,
                                    FOREIGN KEY(user_id) REFERENCES users(id)
                                );"""

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


def is_symbol_exist(stock_symbol):
    stock_data = lookup(stock_symbol)
    if stock_data is None:
        return False
    else:
        return True


def convert_to_usd(stocks_summary: List, money_data: Dict):
    for row in stocks_summary:
        row["price"] = usd(row["price"])
        row["total value"] = usd(row["total value"])

    money_data["cash"] = usd(money_data["cash"])
    money_data["total"] = usd(money_data["total"])

    return stocks_summary, money_data


def get_stocks_summary():
    print(f"I am in get stocks summary")
    stocks_summary = db.execute(
        "SELECT symbol, SUM(shares) as 'total shares' from purchases WHERE user_id = ? AND 'total shares' > 0 GROUP BY symbol HAVING SUM(shares) > 0", session.get("user_id"))

    for row in stocks_summary:
        stock_data = lookup(row["symbol"])
        row["price"] = stock_data["price"]
        row["total value"] = stock_data["price"] * row["total shares"]
        row["name"] = stock_data["name"]

    money_data = db.execute(
        "SELECT cash from users WHERE id=?", session.get("user_id"))[0]
    print("money_data:")
    print(money_data)
    sum = 0
    for stock in stocks_summary:
        sum += int(stock["total value"])
    money_data["total"] = sum + money_data["cash"]
    print(f"stocks_summary: {stocks_summary}")

    stocks_summary, money_data = convert_to_usd(stocks_summary, money_data)

    return stocks_summary, money_data

def get_username():
    username = db.execute("SELECT username FROM users WHERE id=?", session.get("user_id"))[0]
    username = username["username"].title()
    return username

@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    stocks_summary, money_data = get_stocks_summary()
    username = get_username()
    print(f"username: {username}")

    return render_template("index.html", stocks_summary=stocks_summary, money_data=money_data, username=username)


def is_valid_input_shares(shares):
    return shares >= 1


def is_enough_money(stock_symbol, shares):
    stock_data = lookup(stock_symbol)
    cur_user_data = db.execute(
        "SELECT * FROM users WHERE id = ?", session.get("user_id"))
    cur_user_data = cur_user_data[0]
    total_price = shares * stock_data["price"]
    new_cash_balance = cur_user_data["cash"] - total_price
    return new_cash_balance >= 0


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    print("buy function..")
    if request.method == "GET":
        username = get_username()
        return render_template("buy.html", username=username)

    stock_symbol = request.form.get("stock_symbol")
    if not is_symbol_exist(stock_symbol):
        return apology(f"\"{stock_symbol}\" isn't a valid stock name.")

    shares = int(request.form.get("shares"))

    if not is_valid_input_shares(shares):
        return apology("The number of shares must be a positive integer")

    if not is_enough_money(stock_symbol, shares):
        return apology("you don\'t have enough money to buy that.")

    update_purchases(stock_symbol, shares)
    update_cash(stock_symbol, -1 * shares) 

    stocks_summary, money_data = get_stocks_summary()
    username = get_username()

    return render_template("index.html", stocks_summary=stocks_summary, username=username,
                             money_data=money_data)


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    transactions = db.execute("SELECT symbol, shares, stock_price, total_price, time_stamp FROM purchases WHERE user_id = ?", session.get("user_id"))
    print("transactions:")
    print(transactions)
    username = get_username()
    return render_template("history.html", transactions=transactions, username=username)


@app.route("/login", methods=["GET", "POST"])
def login():
    db.execute(create_users_table)
    db.execute(create_purchases_table)
    """Log user in"""
    print("I'm in login route")

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?",
                          request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    print(f"I'm in quote route")

    if request.method == "GET":
        print("In quote get method")
        username = get_username()
        return render_template("quote.html", username=username)
    else:
        stock_symbol = request.form.get("stock_symbol")
        is_symbol_exist(stock_symbol)
        stock_data = lookup(stock_symbol)
        return render_template("quoted.html",
                               stock_data=stock_data,
                               )


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    print("I\'m in regiseter")
    session.clear()
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        confimation = request.form.get("confimation")
        # Ensure username was submitted
        if not username:
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not password:
            return apology("must provide password", 403)

        elif password != confimation:
            return apology("confirmation doesn't match the password", 403)

        # Check whether this username already exist.
        is_exist = db.execute("SELECT * FROM users WHERE username = ?",
                              username)

        if is_exist:
            return apology("username already exist", 409)

        # insert user into database:
        hashed_password = generate_password_hash(password)
        db.execute("INSERT INTO users (username, hash, cash) VALUES (?, ?, ?)",
                   username, hashed_password, 10_000)

        user_id = db.execute("SELECT id FROM users WHERE username = ?",
                             username)

        # Remember which user has logged in
        session["user_id "] = user_id

        print(f"user_id = {user_id}")
        print(f"session = {session}")

        # Redirect user to home page
        return redirect("/")

    else:
        print("A get method!")
        return render_template("/register.html")


def update_cash(stock_symbol, shares_to_sell):
    stock_data = lookup(stock_symbol)
    change_in_cash = stock_data["price"] * shares_to_sell

    user_cash_data = db.execute(
        "SELECT cash FROM users WHERE id = ?", session.get("user_id"))
    user_cash_data = user_cash_data[0]
    new_user_cash = float(user_cash_data["cash"]) + change_in_cash
    db.execute("UPDATE users SET cash=? WHERE id=?",
               new_user_cash, session.get("user_id"))


def update_purchases(stock_symbol, shares):
    stock_data = lookup(stock_symbol)
    time = datetime.now().strftime("%B %d, %Y %I:%M%p")
    total_price = abs(stock_data["price"] * shares)

    db.execute("INSERT INTO purchases (user_id, symbol, shares, stock_price, total_price, time_stamp) VALUES(?, ?, ?, ?, ?, ?)",
    session.get("user_id"), stock_symbol, shares, stock_data["price"],total_price, time)
    return


def is_sell_valid(stock_symbol, shares_to_sell):
    print("im in is_sell valid")
    if not is_symbol_exist(stock_symbol):
        return False
    user_spec_stock = db.execute(
        "SELECT SUM(shares) as total_shares from purchases WHERE user_id=? AND symbol=? GROUP BY symbol", session.get("user_id"), stock_symbol)

    print(f"user_spec_stock: {user_spec_stock}")
    if len(user_spec_stock) == 0:
        return False
    user_spec_stock = user_spec_stock[0]
    if int(user_spec_stock["total_shares"]) - shares_to_sell >= 0:
        print("valid sale!")
        return True
    else:
        print("Not a valid sale")
        return False


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    stocks_summary, money_data = get_stocks_summary()
    if request.method == "GET":
        username = get_username()
        return render_template("sell.html", stocks_summary=stocks_summary, username=username)

    stock_symbol = request.form.get("symbol")
    shares_to_sell = int(request.form.get("shares"))
    if not is_sell_valid(stock_symbol, shares_to_sell):
        return apology(f"You wanted to sell more shares of {stock_symbol} than you have.")
    update_purchases(stock_symbol, -1 * shares_to_sell)
    update_cash(stock_symbol, shares_to_sell)
    return redirect("/")


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


if __name__ == '__main__':
    app.run(debug=True)