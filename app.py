from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = "secret123"

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///store.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


# --------------------
# MODELS
# --------------------
class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    stock = db.Column(db.Integer, default=0)
    capital_per_unit = db.Column(db.Float, nullable=False)
    selling_price = db.Column(db.Float, nullable=False)
    cashier_bonus = db.Column(db.Float, default=0.0)   # custom peso bonus per unit


class Sale(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey("item.id"))
    quantity = db.Column(db.Integer, nullable=False)
    selling_price = db.Column(db.Float, nullable=False)
    capital_per_unit = db.Column(db.Float, nullable=False)
    cashier_bonus = db.Column(db.Float, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)


class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    amount = db.Column(db.Float, nullable=False)
    month = db.Column(db.String(20), nullable=False)   # YYYY-MM


# --------------------
# CREATE DB + DEFAULT EXPENSES
# --------------------
with app.app_context():
    db.create_all()

    now = datetime.utcnow()
    current_month = f"{now.year}-{now.month:02d}"

    default_expenses = {
        "Electricity": 6000,
        "Water": 1000,
        "Rent": 25000,
        "BIR tax": 900,
        "Munisipyo": 1000,
    }

    for name, amt in default_expenses.items():
        exists = Expense.query.filter_by(name=name, month=current_month).first()
        if not exists:
            db.session.add(Expense(name=name, amount=amt, month=current_month))

    db.session.commit()


# --------------------
# LOGIN
# --------------------
@app.route("/")
def index():
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")

        if username == "manager" and password == "MarlaSchr":
            session["role"] = "manager"
            return redirect(url_for("manager_panel"))

        if username == "cashier" and password == "Glitz":
            session["role"] = "cashier"
            return redirect(url_for("cashier_panel"))

        flash("Invalid credentials", "danger")
        return redirect(url_for("login"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# --------------------
# MANAGER PANEL
# --------------------
@app.route("/manager")
def manager_panel():
    if session.get("role") != "manager":
        return redirect(url_for("login"))

    items = Item.query.all()

    now = datetime.utcnow()
    month = f"{now.year}-{now.month:02d}"

    expenses = Expense.query.filter_by(month=month).all()
    total_expenses = sum(e.amount for e in expenses)

    sales = Sale.query.filter(
        db.extract("year", Sale.timestamp) == now.year,
        db.extract("month", Sale.timestamp) == now.month,
    ).all()

    revenue = sum(s.selling_price * s.quantity for s in sales)
    profit = revenue - total_expenses

    return render_template(
        "manager.html",
        items=items,
        expenses=expenses,
        revenue=revenue,
        profit=profit,
        total_expenses=total_expenses,
    )


@app.route("/manager/add_item", methods=["POST"])
def manager_add_item():
    if session.get("role") != "manager":
        return redirect(url_for("login"))

    name = request.form["name"]
    stock = int(request.form["stock"])
    capital = float(request.form["capital"])
    selling = float(request.form["selling"])
    bonus = float(request.form["bonus"])

    db.session.add(
        Item(
            name=name,
            stock=stock,
            capital_per_unit=capital,
            selling_price=selling,
            cashier_bonus=bonus,
        )
    )
    db.session.commit()

    return redirect(url_for("manager_panel"))


@app.route("/manager/delete_item/<int:item_id>")
def manager_delete_item(item_id):
    if session.get("role") != "manager":
        return redirect(url_for("login"))

    item = Item.query.get_or_404(item_id)
    db.session.delete(item)
    db.session.commit()

    return redirect(url_for("manager_panel"))


# --------------------
# CASHIER PANEL
# --------------------
@app.route("/cashier")
def cashier_panel():
    if session.get("role") != "cashier":
        return redirect(url_for("login"))

    items = Item.query.all()

    now = datetime.utcnow()
    month = now.month
    year = now.year

    sales = Sale.query.filter(
        db.extract("year", Sale.timestamp) == year,
        db.extract("month", Sale.timestamp) == month,
    ).all()

    total_bonus = sum(s.cashier_bonus * s.quantity for s in sales)

    return render_template(
        "cashier.html", items=items, sales=sales, total_bonus=total_bonus
    )


@app.route("/cashier/sell", methods=["POST"])
def cashier_sell():
    if session.get("role") != "cashier":
        return redirect(url_for("login"))

    item_id = int(request.form["item_id"])
    qty = int(request.form["quantity"])

    item = Item.query.get_or_404(item_id)

    if item.stock < qty:
        flash("Not enough stock!", "danger")
        return redirect(url_for("cashier_panel"))

    sale = Sale(
        item_id=item.id,
        quantity=qty,
        selling_price=item.selling_price,
        capital_per_unit=item.capital_per_unit,
        cashier_bonus=item.cashier_bonus,
    )

    item.stock -= qty

    db.session.add(sale)
    db.session.commit()

    return redirect(url_for("cashier_panel"))


if __name__ == "__main__":
    app.run(debug=True)
