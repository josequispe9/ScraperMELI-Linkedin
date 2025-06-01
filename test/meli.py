import asyncio
from playwright.async_api import async_playwright
import csv
from datetime import datetime

async def scrape_mercadolibre():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto("https://listado.mercadolibre.com.ar/zapatillas")

        productos_info = []
        fecha_extraccion = datetime.now().strftime("%Y-%m-%d")

        productos = await page.query_selector_all(".ui-search-layout__item")
        print(f"Se encontraron {len(productos)} productos en la página.")

        for producto in productos[:3]:
            try:
                # Nombre
                nombre_el = await producto.query_selector(".poly-component__title")
                nombre = await nombre_el.inner_text() if nombre_el else "Sin nombre"

                # Precio
                precio_el = await producto.query_selector(".andes-money-amount__fraction")
                precio = await precio_el.inner_text() if precio_el else "Sin precio"

                # Link
                link_el = await producto.query_selector("a.poly-component__title")
                link = await link_el.get_attribute("href") if link_el else "Sin link"

                # Vendedor
                vendedor_el = await producto.query_selector(".poly-component__seller")
                vendedor = await vendedor_el.inner_text() if vendedor_el else "Desconocido"

                # Envío gratis
                envio = "Sí" if await producto.query_selector(".poly-component__shipping") else "No"

                # Disponible (si está publicado, asumimos que sí)
                disponible = "Sí"

                # Categoría
                categoria = "Zapatillas"

                # Visitar la página del producto para obtener: ubicación y reputación
                ubicacion = "Desconocida"
                reputacion = "Desconocida"

                if link and link.startswith("http"):
                    producto_page = await browser.new_page()
                    await producto_page.goto(link)
                    await producto_page.wait_for_load_state("domcontentloaded")

                    try:
                        ubicacion_el = await producto_page.query_selector("div.ui-seller-info__status-info__subtitle")
                        if ubicacion_el:
                            ubicacion = await ubicacion_el.inner_text()
                    except:
                        pass

                    try:
                        reputacion_el = await producto_page.query_selector("div.ui-seller-info__header__title + div span")
                        if reputacion_el:
                            reputacion = await reputacion_el.get_attribute("class") or "Desconocida"
                    except:
                        pass

                    await producto_page.close()

                productos_info.append({
                    "producto": nombre.strip(),
                    "precio": f"${precio.strip()}",
                    "vendedor": vendedor.strip(),
                    "ubicacion": ubicacion.strip(),
                    "reputacion_vendedor": reputacion.strip(),
                    "fecha_extraccion": fecha_extraccion,
                    "url_producto": link.strip(),
                    "disponible": disponible,
                    "envio_gratis": envio,
                    "categoria": categoria
                })

            except Exception as e:
                print("❌ Error al extraer un producto:", e)

        if productos_info:
            with open("productos_mercadolibre_5.csv", "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=productos_info[0].keys())
                writer.writeheader()
                writer.writerows(productos_info)
            print("✅ Datos guardados en productos_mercadolibre_5.csv")
        else:
            print("⚠ No se extrajo ningún producto.")

        await browser.close()

# Ejecutar
asyncio.run(scrape_mercadolibre())
