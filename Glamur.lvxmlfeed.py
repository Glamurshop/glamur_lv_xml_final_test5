import requests
import re
import xml.etree.ElementTree as ET
from time import sleep

SHOPIFY_DOMAIN = "xxcw0w-1f.myshopify.com"
ACCESS_TOKEN = "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"
GRAPHQL_URL = f"https://{SHOPIFY_DOMAIN}/admin/api/2023-10/graphql.json"
HEADERS = {
    "Content-Type": "application/json",
    "X-Shopify-Access-Token": ACCESS_TOKEN
}

# 🔧 Nustatymai
TEST_MODE = False  # jei True – eksportuoja tik 50 variantų
OUTPUT_FILE = "glamur_lv_xml_final_test5.xml"


def slugify(text):
    text = text.lower()
    text = re.sub(r'[^a-z0-9]+', '-', text)
    return text.strip('-')


def fetch_lv_products(country_code="LV", locale="lv"):
    all_items = []
    cursor = None
    total_scanned = 0
    total_active = 0

    while True:
        query = f"""
        {{
          productVariants(first: 100{', after: "' + cursor + '"' if cursor else ''}) {{
            pageInfo {{
              hasNextPage
            }}
            edges {{
              cursor
              node {{
                id
                sku
                barcode
                inventoryQuantity
                title
                selectedOptions {{ name value }}
                product {{
                  id
                  handle
                  title
                  vendor
                  status
                  featuredImage {{ src }}
                  collections(first: 1) {{
                    edges {{ node {{ title }} }}
                  }}
                  translations(locale: "{locale}") {{
                    key
                    value
                  }}
                }}
                contextualPricing(context: {{country: {country_code}}}) {{
                  price {{ amount }}
                }}
              }}
            }}
          }}
        }}
        """

        response = requests.post(GRAPHQL_URL, headers=HEADERS, json={"query": query})
        if response.status_code != 200:
            print(f"❌ API klaida: {response.status_code}")
            break

        data = response.json()
        if 'errors' in data:
            print(f"❌ Shopify klaida: {data['errors']}")
            break

        productVariants = data["data"]["productVariants"]
        for edge in productVariants.get("edges", []):
            total_scanned += 1
            node = edge["node"]
            product = node["product"]

            if product["status"] != "ACTIVE":
                continue

            price = float(node.get("contextualPricing", {}).get("price", {}).get("amount") or 0)
            stock = node["inventoryQuantity"]
            if price <= 0 or stock <= 0:
                continue

            total_active += 1

            translations = product.get("translations", [])
            product_title = next((t["value"] for t in translations if t.get("key") == "title"), product["title"])
            option_text = " ".join([opt["value"] for opt in node.get("selectedOptions", [])]).strip()
            full_title = f"{product_title} {option_text}".strip()

            image = product["featuredImage"]["src"] if product.get("featuredImage") else ""
            collections = product.get("collections", {}).get("edges", [])
            category = collections[0]["node"]["title"] if collections else "Parfīmi"
            category_link = f"https://glamur.lv/collections/{slugify(category)}"

            handle = product["handle"]
            variant_id = node["id"].split("/")[-1]
            link = f"https://glamur.lv/products/{handle}?variant={variant_id}&lang=lv"

            all_items.append({
                "title": full_title,
                "price": f"{price:.2f}",
                "stock": str(stock),
                "ean_code": node.get("barcode", ""),
                "sku": node.get("sku", ""),
                "image_url": image,
                "manufacturer": product["vendor"],
                "category_name": category,
                "category_full": f"Parfīmi > {category}",
                "category_link": category_link,
                "product_url": link,
                "delivery_cost_riga": "2.89",
                "used": "0"
            })

            # 🧪 sustoja po 50 variantų testui
            if TEST_MODE and len(all_items) >= 50:
                print("🧪 Testinis limitas pasiektas (50 variantų).")
                return all_items

        print(f"🔍 Nuskaityta: {total_scanned}, aktyvūs variantai: {total_active}, įtraukti į XML: {len(all_items)}")

        if not productVariants["pageInfo"]["hasNextPage"]:
            break

        cursor = productVariants["edges"][-1]["cursor"]
        sleep(0.5)

    return all_items


def build_lv_xml(products):
    root = ET.Element("products")
    for p in products:
        prod = ET.SubElement(root, "product")
        for key, val in p.items():
            child = ET.SubElement(prod, key)
            if key in ["ean_code", "title", "manufacturer"]:
                child.text = f"<![CDATA[{val}]]>"
            else:
                child.text = str(val)

    tree = ET.ElementTree(root)
    # 🔹 gražus formatavimas (Python 3.9+)
    ET.indent(tree, space="  ", level=0)
    tree.write(OUTPUT_FILE, encoding="utf-8", xml_declaration=True)
    print(f"✅ Sugeneruota: {OUTPUT_FILE} ({len(products)} variantai)")


if __name__ == "__main__":
    print("🚀 Pradedamas glamur.lv testinis XML eksportas (50 variantų)...")
    try:
        items = fetch_lv_products()
        build_lv_xml(items)
    except Exception as e:
        print(f"❌ Klaida: {e}")
    input("✅ Atlikta. Paspausk Enter, kad uždarytum.")
