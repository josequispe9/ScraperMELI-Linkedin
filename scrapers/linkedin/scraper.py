"""
Scraper para LinkedIn Jobs - Versión Corregida y Simplificada
Basado en el código funcional de linkedin.py con parser modular
"""

import asyncio
import random
from datetime import datetime
from typing import List, Optional
from urllib.parse import quote_plus

from playwright.async_api import Page, Browser, BrowserContext
from core.browser import BrowserManager
from core.config import LINKEDIN_CONFIG, BROWSER_CONFIG, SCRAPING_CONFIG
from core.logger import get_logger
from .parser import LinkedInParser, JobData

logger = get_logger("linkedin_scraper")

class LinkedInJobsScraper:
    def __init__(self):
        self.browser_manager = BrowserManager()
        self.parser = LinkedInParser()
        self.jobs_data = []
        self.fecha_extraccion = datetime.now().strftime("%Y-%m-%d")
        
    async def wait_random(self, min_seconds=3, max_seconds=8):
        """Espera aleatoria"""
        wait_time = random.uniform(min_seconds, max_seconds)
        await asyncio.sleep(wait_time)
    
    async def scrape_jobs(self, search_terms: List[str] = None, max_jobs: int = 50) -> List[JobData]:
        """Scraper principal simplificado"""
        if not search_terms:
            search_terms = getattr(LINKEDIN_CONFIG, 'search_terms', ['python developer'])
        
        logger.info(f"Iniciando scraping para {len(search_terms)} términos")
        
        try:
            await self.browser_manager.start()
            context = await self.browser_manager.create_context()
            await self._setup_stealth_context(context)
            
            all_jobs = []
            
            for i, term in enumerate(search_terms):
                logger.info(f"Scrapeando término {i+1}/{len(search_terms)}: {term}")
                jobs = await self._scrape_search_term(context, term, max_jobs)
                all_jobs.extend(jobs)
                
                if i < len(search_terms) - 1:
                    await self.wait_random(5, 10)
            
            # Eliminar duplicados
            unique_jobs = self._remove_duplicates(all_jobs)
            logger.info(f"Total empleos únicos: {len(unique_jobs)}")
            
            return unique_jobs
            
        except Exception as e:
            logger.error(f"Error en scraping: {e}")
            raise
        finally:
            await self.browser_manager.close()
    
    async def _setup_stealth_context(self, context: BrowserContext):
        """Configuración stealth básica"""
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
            });
        """)
        
        await context.set_extra_http_headers({
            'Accept-Language': 'es-AR,es;q=0.9,en;q=0.8',
            'DNT': '1'
        })
    
    async def _scrape_search_term(self, context: BrowserContext, search_term: str, max_jobs: int) -> List[JobData]:
        """Scraper para un término específico - basado en linkedin.py funcional"""
        page = await context.new_page()
        page.set_default_timeout(30000)
        
        try:
            # Verificar acceso y manejar login
            if not await self._handle_access_and_login(page):
                logger.error("No se pudo acceder a LinkedIn")
                return []
            
            # Realizar búsqueda usando URL directa (método que funciona)
            search_url = f"https://www.linkedin.com/jobs/search/?keywords={quote_plus(search_term)}&location=Argentina"
            logger.info(f"Navegando a: {search_url}")
            
            await page.goto(search_url, wait_until="domcontentloaded")
            await self.wait_random(5, 8)
            
            # Usar parser para encontrar elementos
            job_elements = await self.parser.find_job_elements(page, max_jobs)
            
            if not job_elements:
                logger.warning(f"No se encontraron empleos para '{search_term}'")
                return []
            
            logger.info(f"Encontrados {len(job_elements)} elementos de empleos")
            
            # Procesar empleos usando parser
            jobs = []
            for i, job_element in enumerate(job_elements):
                try:
                    job_data = await self.parser.parse_job_element(job_element, i+1)
                    if job_data:
                        jobs.append(job_data)
                        logger.debug(f"✅ Empleo {i+1}: {job_data.titulo_puesto}")
                    
                    await self.wait_random(2, 4)
                    
                except Exception as e:
                    logger.debug(f"Error procesando empleo {i+1}: {e}")
                    continue
            
            logger.info(f"Empleos válidos extraídos: {len(jobs)}")
            return jobs
            
        except Exception as e:
            logger.error(f"Error scrapeando término '{search_term}': {e}")
            return []
        finally:
            await page.close()
    
    async def _handle_access_and_login(self, page: Page) -> bool:
        """Manejo de acceso y login simplificado - basado en linkedin.py"""
        try:
            logger.info("Verificando acceso a LinkedIn...")
            await page.goto("https://www.linkedin.com/jobs/", wait_until="domcontentloaded")
            await self.wait_random(3, 5)
            
            # Verificar si necesita login
            login_needed = await page.query_selector('a[href*="login"], .sign-in-form')
            
            if login_needed:
                logger.info("Se requiere login")
                
                if (hasattr(LINKEDIN_CONFIG, 'email') and hasattr(LINKEDIN_CONFIG, 'password') and
                    LINKEDIN_CONFIG.email and LINKEDIN_CONFIG.password):
                    return await self._auto_login(page)
                else:
                    logger.info("Login manual requerido")
                    input("Por favor, inicia sesión manualmente y presiona Enter...")
                    await self.wait_random(3, 5)
            
            return True
            
        except Exception as e:
            logger.error(f"Error en acceso/login: {e}")
            return False
    
    async def _auto_login(self, page: Page) -> bool:
        """Login automático simplificado"""
        try:
            logger.info("Intentando login automático...")
            await page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded")
            await self.wait_random(2, 3)
            
            await page.fill('#username', LINKEDIN_CONFIG.email)
            await page.fill('#password', LINKEDIN_CONFIG.password)
            await page.click('button[type="submit"]')
            await self.wait_random(5, 8)
            
            # Verificar éxito
            if "feed" in page.url or "jobs" in page.url:
                logger.info("✅ Login exitoso")
                return True
            else:
                logger.error("❌ Login falló")
                return False
                
        except Exception as e:
            logger.error(f"Error en auto-login: {e}")
            return False
    
    def _remove_duplicates(self, jobs: List[JobData]) -> List[JobData]:
        """Eliminar duplicados basados en URL"""
        seen_urls = set()
        unique_jobs = []
        
        for job in jobs:
            identifier = job.url_empleo if job.url_empleo != "No encontrado" else f"{job.titulo_puesto}_{job.empresa}"
            
            if identifier not in seen_urls:
                seen_urls.add(identifier)
                unique_jobs.append(job)
        
        return unique_jobs
    
    async def scrape_job_details(self, jobs: List[JobData], max_details: int = 20) -> List[JobData]:
        """Scraper detalles adicionales usando parser"""
        if not jobs:
            return jobs
        
        logger.info(f"Scrapeando detalles para {min(len(jobs), max_details)} empleos")
        
        try:
            context = await self.browser_manager.create_context()
            await self._setup_stealth_context(context)
            page = await context.new_page()
            
            for i, job in enumerate(jobs[:max_details]):
                if job.url_empleo and job.url_empleo != "No encontrado":
                    try:
                        logger.info(f"Detalles {i+1}/{min(len(jobs), max_details)}: {job.titulo_puesto}")
                        
                        details = await self.parser.scrape_job_details(page, job.url_empleo)
                        
                        # Actualizar job con detalles
                        if details.get('descripcion_completa', 'No disponible') != 'No disponible':
                            job.descripcion_breve = details['descripcion_completa'][:200] + "..."
                        
                        await self.wait_random(3, 6)
                        
                    except Exception as e:
                        logger.error(f"Error scrapeando detalles de {job.titulo_puesto}: {e}")
                        continue
            
            return jobs
            
        except Exception as e:
            logger.error(f"Error en scraping de detalles: {e}")
            return jobs
        finally:
            try:
                await page.close()
                await context.close()
            except:
                pass
    
    def save_results(self, jobs: List[JobData], filename: str = None) -> str:
        """Guardar resultados en CSV"""
        if not jobs:
            logger.warning("No hay empleos para guardar")
            return ""
        
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"linkedin_jobs_{timestamp}.csv"
        
        try:
            import csv
            
            # Convertir JobData a diccionarios
            jobs_dicts = []
            for job in jobs:
                job_dict = {
                    "indice": job.indice,
                    "fecha_extraccion": job.fecha_extraccion,
                    "titulo_puesto": job.titulo_puesto,
                    "empresa": job.empresa,
                    "ubicacion": job.ubicacion,
                    "url_empleo": job.url_empleo,
                    "modalidad": job.modalidad,
                    "fecha_publicacion": job.fecha_publicacion
                }
                jobs_dicts.append(job_dict)
            
            with open(filename, "w", newline="", encoding="utf-8") as f:
                if jobs_dicts:
                    fieldnames = list(jobs_dicts[0].keys())
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(jobs_dicts)
            
            logger.info(f"Resultados guardados en: {filename}")
            return filename
            
        except Exception as e:
            logger.error(f"Error guardando resultados: {e}")
            return ""

# Función principal de entrada
async def scrape_linkedin_jobs(search_terms: List[str] = None, max_jobs: int = 50, include_details: bool = False) -> List[JobData]:
    """
    Función principal para scraping
    
    Args:
        search_terms: Lista de términos de búsqueda
        max_jobs: Máximo empleos por término
        include_details: Si incluir scraping detallado
    
    Returns:
        Lista de JobData con empleos extraídos
    """
    scraper = LinkedInJobsScraper()
    
    try:
        # Scraping básico
        jobs = await scraper.scrape_jobs(search_terms, max_jobs)
        
        if not jobs:
            logger.warning("No se encontraron empleos")
            return []
        
        # Scraping detallado opcional
        if include_details:
            logger.info("Iniciando scraping detallado...")
            jobs = await scraper.scrape_job_details(jobs, max_details=min(20, len(jobs)))
        
        # Guardar resultados
        filename = scraper.save_results(jobs)
        
        logger.info(f"Scraping completado: {len(jobs)} empleos extraídos")
        if filename:
            logger.info(f"Archivo guardado: {filename}")
        
        return jobs
        
    except Exception as e:
        logger.error(f"Error en scraping principal: {e}")
        raise

# Función para ejecutar desde CLI
async def main():
    """Función principal para línea de comandos"""
    import argparse
    
    parser = argparse.ArgumentParser(description="LinkedIn Jobs Scraper")
    parser.add_argument("--terms", nargs="+", default=["python developer"], 
                       help="Términos de búsqueda")
    parser.add_argument("--max-jobs", type=int, default=50, 
                       help="Máximo empleos por término")
    parser.add_argument("--details", action="store_true", 
                       help="Incluir scraping detallado")
    
    args = parser.parse_args()
    
    try:
        jobs = await scrape_linkedin_jobs(
            search_terms=args.terms,
            max_jobs=args.max_jobs,
            include_details=args.details
        )
        
        print(f"\n🎉 Scraping completado!")
        print(f"📊 Total empleos: {len(jobs)}")
        
        if jobs:
            print(f"\n📋 Resumen por empresa:")
            companies = {}
            for job in jobs:
                companies[job.empresa] = companies.get(job.empresa, 0) + 1
            
            for company, count in sorted(companies.items(), key=lambda x: x[1], reverse=True)[:10]:
                print(f"  • {company}: {count} empleos")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1

if __name__ == "__main__":
    asyncio.run(main())