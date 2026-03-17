from playwright.sync_api import sync_playwright
import urllib.parse
import yaml
import os
import re

LATITUDE = 48.8566
LONGITUDE = 2.3522


def extract_infos(text):

    prix = None
    prix_kg = None
    reduction = None
    quantite = None

    # prix au kg
    match_kg = re.search(r"(\d+[,.]\d+)\s*€\s*/\s*kg", text.lower())
    if match_kg:
        prix_kg = match_kg.group(1).replace(",", ".") + " € / KG"

    # prix normal
    match_price = re.search(r"(\d+[,.]\d+)\s*€(?!\s*/)", text)
    if match_price:
        prix = match_price.group(1).replace(",", ".") + " €"

    # réduction (ex: -20%)
    match_reduc = re.search(r"-\s*\d+\s*%", text)
    if match_reduc:
        reduction = match_reduc.group(0).replace(" ", "")

    # quantité (ex: 4x125g, 500g, 1kg, 1L)
    match_qte = re.search(r"\d+\s?[xX]\s?\d+\s?(g|kg|ml|l)|\d+\s?(g|kg|ml|l)", text.lower())
    if match_qte:
        quantite = match_qte.group(0)

    return prix, prix_kg, reduction, quantite


def scrape_carrefour(produit, lat, lon):

    query = urllib.parse.quote(produit)
    url = f"https://www.carrefour.fr/s?q={query}&sort=price_asc"

    resultats = []

    with sync_playwright() as p:

        browser = p.chromium.launch(headless=False)

        context = browser.new_context(
            geolocation={"latitude": lat, "longitude": lon},
            permissions=["geolocation"]
        )

        page = context.new_page()
        page.goto(url)

        try:
            page.click("button:has-text('Tout accepter')", timeout=5000)
        except:
            pass

        page.wait_for_load_state("networkidle")

        magasin = "Carrefour le plus proche"

        cartes = page.locator("article").all()

        for c in cartes:

            nom = None
            prix = None
            prix_kg = None
            reduction = None
            quantite = None
            note = None
            avis = None

            if c.locator("h3").count() > 0:
                nom = c.locator("h3").first.inner_text().strip()

            texte = c.inner_text()

            p, pk, r, q = extract_infos(texte)

            prix = p
            prix_kg = pk
            reduction = r
            quantite = q

            # note et avis
            aria = c.locator("[aria-label]").all()

            for a in aria:

                label = a.get_attribute("aria-label")

                if label and "avis" in label:

                    note_match = re.search(r"(\d+\.\d+)", label)
                    avis_match = re.search(r"(\d+)\s*avis", label)

                    if note_match:
                        note = note_match.group(1)

                    if avis_match:
                        avis = avis_match.group(1)

            if nom:

                resultats.append({
                    "lieu": magasin,
                    "nom": nom,
                    "quantite": quantite,
                    "prix": prix,
                    "prix_kg": prix_kg,
                    "reduction": reduction,
                    "note": note,
                    "avis": avis
                })

        browser.close()

    return resultats


def save_yaml(data):

    path = "../data/resume.yaml"
    os.makedirs(os.path.dirname(path), exist_ok=True)

    yaml_data = {"produits": data}

    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(yaml_data, f, allow_unicode=True, sort_keys=False)

    print("YAML créé :", path)


if __name__ == "__main__":

    produits = scrape_carrefour(
        "glace pistache",
        LATITUDE,
        LONGITUDE
    )

    save_yaml(produits)