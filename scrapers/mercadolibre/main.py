import asyncio
from .scraper import MercadoLibreScraper  # Import relativo al estar en el mismo módulo

async def main():
    scraper = MercadoLibreScraper()
    results = await scraper.scrape_products(["zapatillas", "notebook"])
    
    for product in results[:5]:  # Mostramos solo los primeros 5 productos
        print(product)

if __name__ == "__main__":
    asyncio.run(main())
