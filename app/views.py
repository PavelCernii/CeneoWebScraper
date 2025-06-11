import os, json
from app import app
import requests
from flask import render_template, request, redirect, url_for
from config import headers
from app import utils
from bs4 import BeautifulSoup
import pandas as pd
from flask import send_file
from matplotlib import pyplot as plt
import matplotlib
matplotlib.use("Agg")

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/extract")
def display_form():
    return render_template("extract.html")

@app.route("/extract", methods=["POST"])
def extract():
    product_id = request.form.get('product_id')
    next_page = f"https://www.ceneo.pl/{product_id}#tab=reviews"
    response = requests.get(next_page, headers=headers)
    if response.status_code == 200:
        page_dom = BeautifulSoup(response.text, "html.parser")
        product_name = utils.extract_feature(page_dom, "h1")
        opinions_count = utils.extract_feature(page_dom, "a.product-review__link > span")
        if not opinions_count:
            error = "Dla produktu o podanym id nie ma jeszcze żadnych opinii"
            return render_template("extract.html", error=error)
    else:
        error = "Nie znaleziono produktu o podanym id"
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
                next_page = "https://www.ceneo.pl" + utils.extract_feature(page_dom, "a.pagination__next", "href")
            except TypeError:
                next_page = None
        else:
            print(response.status_code)

    if not os.path.exists("./app/data"):
        os.mkdir("./app/data")
    if not os.path.exists("./app/data/opinions"):
        os.mkdir("./app/data/opinions")
    with open(f"./app/data/opinions/{product_id}.json", "w", encoding="UTF-8") as jf:
        json.dump(all_opinions, jf, indent=4, ensure_ascii=False)
    opinions = pd.DataFrame.from_dict(all_opinions)
    opinions.stars = opinions.stars.apply(lambda s: s.split("/")[0].replace(",", ".")).astype(float)
    opinions.useful = opinions.useful.astype(int)
    opinions.unuseful = opinions.unuseful.astype(int)

    stats = {
        'product_id': product_id,
        'product_name': product_name,
        "opinions_count": opinions.shape[0],
        "pros_count": int(opinions.pros.astype(bool).sum()),
        "cons_count": int(opinions.cons.astype(bool).sum()),
        "pros_cons_count": int(opinions.apply(lambda o: bool(o.pros) and bool(o.cons), axis=1).sum()),
        "average_stars": float(opinions.stars.mean()),
        "pros": opinions.pros.explode().dropna().value_counts().to_dict(),
        "cons": opinions.cons.explode().dropna().value_counts().to_dict(),
        "recommendations": opinions.recommendation.value_counts(dropna=False).reindex(['Nie polecam','Polecam', None], fill_value=0).to_dict(),
    }

    if not os.path.exists("./app/data/products"):
        os.mkdir("./app/data/products")

    with open(f"./app/data/products/{product_id}.json", "w", encoding="UTF-8") as f:
        json.dump(stats, f, indent=4, ensure_ascii=False)

    return redirect(url_for('product', product_id=product_id, product_name=product_name))

@app.route("/products")
def products():
    products_list = []
    opinions_dir = "./app/data/opinions"
    for filename in os.listdir(opinions_dir):
        if filename.endswith(".json"):
            product_id = filename.replace(".json", "")
            with open(os.path.join(opinions_dir, filename), "r", encoding="utf-8") as f:
                opinions = json.load(f)
                if not opinions:
                    continue
                opinion_count = len(opinions)
                stars = []
                pros_count = 0
                cons_count = 0

                for o in opinions:
                    if o.get("stars"):
                        stars.append(float(o["stars"].split("/")[0].replace(",", ".")))
                    pros_count += len(o.get("pros", []))
                    cons_count += len(o.get("cons", []))

                avg_rating = round(sum(stars)/len(stars), 2) if stars else "brak danych"

                name = opinions[0].get("content", "Nieznany")[:30] + "..."

                products_list.append({
                    "id": product_id,
                    "name": name,
                    "opinion_count": opinion_count,
                    "avg_rating": avg_rating,
                    "pros_count": pros_count,
                    "cons_count": cons_count
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
    opinions = df.to_dict(orient="records")
    return render_template(
        "product.html",
        product_id=product_id,
        product_name=product_name,
        opinions=opinions,
        avg_rating=avg_rating,
        opinion_count=opinion_count,
        pros_count=pros_count,
        cons_count=cons_count
    )


@app.route("/charts/<product_id>")
def charts(product_id):
    if not os.path.exists("./app/static/images"):
        os.mkdir("./app/static/images")
    if not os.path.exists("./app/static/images/charts"):
        os.mkdir("./app/static/images/charts")

    with open(f"./app/data/products/{product_id}.json", "r", encoding="UTF-8") as jf:
        stats = json.load(jf)

    recommendations = pd.Series(stats['recommendations'])
    recommendations.plot.pie(
        label="",
        title=f"Rozkład rekomendacji – {stats['product_name']}",
        labels=['Nie polecam', 'Polecam', 'Nie mam zdania'],
        colors=["crimson", 'forestgreen', "lightgrey"],
        autopct="%1.1f%%"
    )
    plt.savefig(f"./app/static/images/charts/{product_id}_pie.png")
    plt.close()

    return render_template("charts.html", product_id=product_id, product_name=stats["product_name"])

@app.route("/download/<product_id>/<file_format>")
def download_file(product_id, file_format):
    df = pd.read_json(os.path.join("app", "data", "opinions", f"{product_id}.json"))
    file_path = os.path.join(os.getcwd(), "app", "data", f"{product_id}.{file_format}")

    if file_format == "json":
        df.to_json(file_path, orient="records", force_ascii=False, indent=4)
    elif file_format == "csv":
        df.to_csv(file_path, index=False)
    elif file_format == "xlsx":
        df.to_excel(file_path, index=False)
    else:
        return "Nieobsługiwany format", 400

    return send_file(file_path, as_attachment=True)