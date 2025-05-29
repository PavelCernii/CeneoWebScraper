import os, json
from app import app
import requests
from flask import render_template, request, redirect, url_for
from config import headers
from app import utils
from bs4 import BeautifulSoup
import pandas as pd

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/extract")
def display_form():
    return render_template("extract.html")

@app.route("/", methods=["POST"])
def extract():
    product_id =  request.form.get("product_id")
    next_page = f"https://www.ceneo.pl/{product_id}#tab=reviews"
    response = requests.get(next_page, headers=headers)
    if response.status_code == 200:
        page_dom = BeautifulSoup(response.text, "html.parser")
        product_name = utils.extract_feature(page_dom, "h1")
        opinions_count = utils.extract_feature(page_dom, "a.product-review__link > span")
        if not opinions_count:
            error="Dla produktu o podanym id nie ma jeszcze żadnych opinii"
            return render_template("extract.html", error=error)
    else:
        error="Nie znaleziono produktu o podanym id"
        return render_template("extract.html", error=error)
    all_opinions = []
    while next_page:
        print(next_page)
        response = requests.get(next_page, headers=headers)
        if response.status_code == 200:
            page_dom = BeautifulSoup(response.text, "html.parser")
            opinions = page_dom.select("div.js_product-review:not(.user-post--highlight)")
            for opinion in opinions:
                single_opinion = {
                    key: utils.extract_feature(opinion, *value)
                    for key, value in utils.selectors.items()
                }
                all_opinions.append(single_opinion)
            try:
                next_page = "https://www.ceneo.pl"+utils.extract_feature(page_dom, "a.pagination__next", "href")
            except TypeError:
                next_page = None
        else: print(response.status_code)

    if not os.path.exists("./app/data"):
        os.mkdir("./app/data")

    if not os.path.exists("./app/data/opinions"):
        os.mkdir("./app/data/opinions")

    with open(f"./app/data/opinions/{product_id}.json", "w", encoding="UTF-8") as jf:
        json.dump(all_opinions, jf, indent=4, ensure_ascii=False)

    return redirect(url_for("product", product_id=product_id, product_name=product_name))

@app.route("/products")
def products():
    products_list = []
    opinions_dir = "./app/data/opinions"
    for filename in os.listdir(opinions_dir):
        if filename.endswith(".json"):
            product_id = filename.replace(".json", "")
            with open(os.path.join(opinions_dir, filename), "r", encoding="utf-8") as f:
                opinions = json.load(f)
                opinion_count = len(opinions)
                stars = []
                pros = 0
                cons = 0
                for o in opinions:
                    stars.append(float(o["stars"].split("/")[0].replace(",", ".")) if o["stars"] else 0)
                    pros += len(o["pros"]) if o.get("pros") else 0
                    cons += len(o["cons"]) if o.get("cons") else 0
                avg_rating = round(sum(stars)/len(stars), 2) if stars else 0
                products_list.append({
                    "id": product_id,
                    "name": opinions[0].get("content", "Nieznany"),
                    "opinion_count": opinion_count,
                    "avg_rating": avg_rating
                })
    return render_template("products.html", products=products_list)


@app.route("/author")
def author():
    return render_template("author.html")

@app.route("/product/<product_id>")
def product(product_id):
    product_name = request.args.get("product_name", "Nieznany")
    df = pd.read_json(f"./app/data/opinions/{product_id}.json")

    opinion_count = len(df)
    stars = df["stars"].dropna().apply(lambda x: float(x.split("/")[0].replace(",", ".")))
    avg_rating = round(stars.mean(), 2) if not stars.empty else "brak danych"
    pros_count = df["pros"].dropna().apply(len).sum()
    cons_count = df["cons"].dropna().apply(len).sum()

    return render_template(
        "product.html",
        product_id=product_id,
        product_name=product_name,
        opinions=df.to_html(classes="display", table_id="opinions"),
        avg_rating=avg_rating,
        opinion_count=opinion_count,
        pros_count=pros_count,
        cons_count=cons_count
    )
