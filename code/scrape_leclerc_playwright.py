from playwright.sync_api import sync_playwright
import urllib.parse
import csv
import time
import yaml
import os


def scrape_leclerc(query, headless=True, max_scrolls=8):
    q = urllib.parse.quote(query)
    url = f"https://www.e.leclerc/recherche?q={q}"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page()
        page.goto(url, wait_until="networkidle")

        # try accept cookies
        try:
            page.click("button:has-text('Tout accepter')", timeout=3000)
        except:
            pass

        # scroll to load lazy items
        for i in range(max_scrolls):
            page.evaluate("window.scrollBy(0, document.body.scrollHeight)")
            time.sleep(1)

        # save page HTML for debugging / selector inspection
        try:
            html = page.content()
            with open('leclerc_page_debug.html', 'w', encoding='utf-8') as f:
                f.write(html)
        except:
            pass

        # prefer structured JSON-LD data when available
        items = page.evaluate(r"""
        () => {
            const results = [];
            const scripts = Array.from(document.querySelectorAll('script[type="application/ld+json"]'));
            for(const s of scripts){
                try{
                    const j = JSON.parse(s.textContent);
                    const arr = Array.isArray(j) ? j : [j];
                    for(const obj of arr){
                        const types = obj['@type'] || obj['@type'];
                        if(!types) continue;
                        const isProduct = (types === 'Product') || (Array.isArray(types) && types.includes('Product'));
                        if(isProduct){
                            const name = obj.name || obj['name'];
                            let price = null;
                            const offers = obj.offers;
                            if(offers){
                                if(Array.isArray(offers)){
                                    price = offers[0].price || (offers[0].priceSpecification && offers[0].priceSpecification.price);
                                } else {
                                    price = offers.price || (offers.priceSpecification && offers.priceSpecification.price);
                                }
                            }
                            if(name && price){
                                results.push({produit: name, prix: String(price) + ' €'});
                            }
                        }
                    }
                } catch(e){ }
            }
            return results;
        }
        """)

        # structured selector fallback: target Leclerc product cards rendered in search results
        if not items:
            items = page.evaluate(r"""
            () => {
                const results = [];
                const nodes = Array.from(document.querySelectorAll('li.product-container'));
                for(const li of nodes){
                    try{
                        const nameEl = li.querySelector('.product-label, .product-label .product-label, p.product-label');
                        const priceUnit = li.querySelector('#price .price-unit');
                        const priceCents = li.querySelector('#price .price-cents');
                        let name = nameEl ? nameEl.innerText.replace(/\s+/g,' ').trim() : null;
                        if(!name) continue;
                        let price = null;
                        if(priceUnit){
                            const unit = priceUnit.innerText.replace(/\s+/g,'').trim();
                            const cents = priceCents ? priceCents.innerText.replace(/\s+/g,'').trim() : '';
                            // normalize cents (many pages render ",70" with a leading comma)
                            price = unit + '€' + (cents ? (' ' + cents) : '');
                        } else {
                            // fallback: any price-like text inside the card
                            const text = li.innerText.replace(/\s+/g,' ');
                            const m = text.match(/\d+[\d\s,.]*[,\.]?\d*\s*€/);
                            if(m) price = m[0].trim();
                        }
                        results.push({produit: name, prix: price});
                    } catch(e){ }
                }
                return results;
            }
            """)

        # if nothing found, save page content for inspection
        if not items:
            html = page.content()
            with open('leclerc_page_debug.html', 'w', encoding='utf-8') as f:
                f.write(html)

        browser.close()

    return items


def save_csv(data, path="yaourts_fraise_leclerc_playwright.csv"):
    keys = ["produit", "prix"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(data)
    print("Sauvegardé ->", path)


def save_yaml_leclerc(items, path="data/leclerc.yaml"):
    os.makedirs(os.path.dirname(path), exist_ok=True)

    produits = []
    for it in items:
        nom = it.get("produit") or it.get("nom") or ""
        prix = it.get("prix") or it.get("price") or None
        produits.append({
            "lieu": "E.Leclerc",
            "nom": nom,
            "prix": prix,
            "prix_kg": None,
            "note": None,
            "avis": None
        })

    yaml_data = {"produits": produits}
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(yaml_data, f, allow_unicode=True, sort_keys=False)

    print("YAML créé ->", path)


if __name__ == '__main__':
    q = "yaourt fraise"
    data = scrape_leclerc(q, headless=False)
    if data:
        save_csv(data)
        save_yaml_leclerc(data, path="data/leclerc.yaml")
        print(f"{len(data)} produits extraits et sauvegardés")
    else:
        print("Aucun produit trouvé — page sauvegardée: leclerc_page_debug.html — relancez avec headless=False pour debug visuel.")
