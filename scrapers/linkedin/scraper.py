"""
Scraper para LinkedIn Jobs - Versión Corregida y Simplificada

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
                        
                        # Actualizar job con detalles completos
                        if details.get('descripcion_completa', 'No disponible') != 'No disponible':
                            job.descripcion_breve = details['descripcion_completa'][:200] + "..."
                        
                        if details.get('nivel_experiencia', 'No disponible') != 'No disponible':
                            job.nivel_experiencia = details['nivel_experiencia']
                        
                        if details.get('beneficios_ofrecidos', 'No disponible') != 'No disponible':
                            job.beneficios_ofrecidos = details['beneficios_ofrecidos']
                        
                        await self.wait_random(3, 6)
                        
                    except Exception as e:
                        logger.debug(f"Error obteniendo detalles para {job.titulo_puesto}: {e}")
                        continue
            
            await page.close()
            return jobs
            
        except Exception as e:
            logger.error(f"Error scrapeando detalles: {e}")
            return jobs


# Función de conveniencia para usar desde main.py
async def scrape_linkedin_jobs(search_terms: List[str] = None, max_jobs: int = 50, include_details: bool = False) -> List[JobData]:
    """Función principal de scraping"""
    scraper = LinkedInJobsScraper()
    
    try:
        # Scraping básico
        jobs = await scraper.scrape_jobs(search_terms, max_jobs)
        
        # Scraping de detalles si se solicita
        if include_details and jobs:
            jobs = await scraper.scrape_job_details(jobs, min(len(jobs), 20))
        
        return jobs
        
    except Exception as e:
        logger.error(f"Error en scrape_linkedin_jobs: {e}")
        return []