"""
Parser  para LinkedIn Jobs
Basado en selectores funcionales comprobados
"""

import re
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional, List
from playwright.async_api import ElementHandle, Page

from core.logger import get_logger

logger = get_logger("linkedin_parser")

@dataclass
class JobData:
    """Estructura de datos para empleos de LinkedIn"""
    indice: int = 0
    fecha_extraccion: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"))
    titulo_puesto: str = "No encontrado"
    empresa: str = "No encontrado"
    ubicacion: str = "No encontrado"
    url_empleo: str = "No encontrado"
    modalidad: str = "No encontrado"
    fecha_publicacion: str = "No encontrado"
    descripcion_breve: str = "No disponible"
    nivel_experiencia: str = "No disponible"
    beneficios_ofrecidos: str = "No disponible"

class LinkedInParser:
    
    def __init__(self):
        self.job_container_selectors = [
            'ul li:has(a[href*="/jobs/view/"])',
            'li[data-occludable-job-id]',
            'li:has(div div div div div div a[href*="/jobs/view/"])'
        ]
    
    async def find_job_elements(self, page: Page, max_jobs: int = 5) -> List[ElementHandle]:
        """Encontrar elementos de empleos usando los selectores"""
        job_elements = []
        
        # Esperar a que carguen los resultados
        try:
            await page.wait_for_selector('ul li[data-occludable-job-id], ul li:has(a[href*="/jobs/view/"])', timeout=15000)
        except:
            logger.warning("Timeout esperando resultados, continuando...")
        
        # Probar selectores del código funcional
        for selector in self.job_container_selectors:
            try:
                elements = await page.query_selector_all(selector)
                if elements:
                    logger.info(f"✅ Encontrados {len(elements)} empleos con selector: {selector}")
                    job_elements = elements[:max_jobs]
                    break
            except:
                continue
        
        # Fallback: buscar links directamente y obtener contenedores padre
        if not job_elements:
            try:
                job_links = await page.query_selector_all('a[href*="/jobs/view/"]')
                if job_links:
                    logger.info(f"✅ Encontrados {len(job_links)} links de empleos")
                    for link in job_links[:max_jobs]:
                        parent = await link.query_selector('xpath=ancestor::li[1]')
                        if parent:
                            job_elements.append(parent)
            except Exception as e:
                logger.error(f"Error en fallback: {e}")
        
        return job_elements
    
    async def parse_job_element(self, element: ElementHandle, index: int) -> Optional[JobData]:
        """Parse de elemento empleo basado en selectores funcionales"""
        try:
            job_data = JobData()
            job_data.indice = index
            
            # TÍTULO Y URL - Selectores del código funcional
            title_selectors = [
                'a[href*="/jobs/view/"] span strong',
                'a[href*="/jobs/view/"] strong',
                'div div div div div div a[href*="/jobs/view/"] span strong',
                'a[href*="/jobs/view/"]'
            ]
            
            for selector in title_selectors:
                try:
                    title_element = await element.query_selector(selector)
                    if title_element:
                        title = await title_element.inner_text()
                        if title and title.strip():
                            job_data.titulo_puesto = title.strip()
                            
                            # Obtener URL
                            link_element = await title_element.query_selector('xpath=ancestor::a[1]')
                            if not link_element:
                                link_element = await element.query_selector('a[href*="/jobs/view/"]')
                            
                            if link_element:
                                href = await link_element.get_attribute('href')
                                if href:
                                    job_data.url_empleo = href if href.startswith('http') else f"https://www.linkedin.com{href}"
                            break
                except:
                    continue
            
            # EMPRESA - Selectores del código funcional
            company_selectors = [
                'span[dir="ltr"]:not(:has(strong))',
                'div:nth-child(2) span[dir="ltr"]',
                'div + div span[dir="ltr"]'
            ]
            
            for selector in company_selectors:
                try:
                    elements = await element.query_selector_all(selector)
                    for company_element in elements:
                        text = await company_element.inner_text()
                        if text and text.strip() and not self._is_location_text(text):
                            job_data.empresa = text.strip()
                            break
                    if job_data.empresa != "No encontrado":
                        break
                except:
                    continue
            
            # UBICACIÓN - Selectores del código funcional
            location_selectors = [
                'span[dir="ltr"]:has-text("Argentina")',
                'span[dir="ltr"]:has-text("Buenos Aires")',
                'span[dir="ltr"]:has-text("Comuna")',
                'ul li span[dir="ltr"]'
            ]
            
            for selector in location_selectors:
                try:
                    location_element = await element.query_selector(selector)
                    if location_element:
                        location = await location_element.inner_text()
                        if location and self._is_location_text(location):
                            job_data.ubicacion = re.sub(r'\s+', ' ', location.strip())
                            
                            # Extraer modalidad
                            if 'híbrido' in location.lower():
                                job_data.modalidad = "Híbrido"
                            elif 'remoto' in location.lower():
                                job_data.modalidad = "Remoto"
                            elif 'presencial' in location.lower():
                                job_data.modalidad = "Presencial"
                            break
                except:
                    continue
            
            # FECHA DE PUBLICACIÓN
            time_selectors = [
                'time[datetime]',
                'time',
                'span:has-text("Hace")',
                'span:has-text("días")'
            ]
            
            for selector in time_selectors:
                try:
                    time_element = await element.query_selector(selector)
                    if time_element:
                        if selector == 'time[datetime]':
                            datetime_attr = await time_element.get_attribute('datetime')
                            if datetime_attr:
                                job_data.fecha_publicacion = datetime_attr
                        else:
                            time_text = await time_element.inner_text()
                            if time_text:
                                job_data.fecha_publicacion = time_text.strip()
                        break
                except:
                    continue
            
            # DESCRIPCIÓN BREVE (desde el listado)
            desc_selectors = [
                '.job-search-card__snippet',
                '.job-card-container__snippet',
                'div:has-text("Descripción")',
                'span:has-text("Descripción")'
            ]
            
            for selector in desc_selectors:
                try:
                    desc_element = await element.query_selector(selector)
                    if desc_element:
                        desc = await desc_element.inner_text()
                        if desc and desc.strip():
                            job_data.descripcion_breve = desc.strip()[:200] + "..."
                            break
                except:
                    continue
            
            # Validaciones básicas
            if not job_data.titulo_puesto or job_data.titulo_puesto == "No encontrado":
                return None
            
            if not job_data.empresa or job_data.empresa == "No encontrado":
                return None
            
            return job_data
            
        except Exception as e:
            logger.debug(f"Error parseando elemento {index}: {e}")
            return None
    
    def _is_location_text(self, text: str) -> bool:
        """Verificar si el texto corresponde a ubicación"""
        location_keywords = [
            'argentina', 'buenos aires', 'comuna', 'remoto', 
            'híbrido', 'presencial', 'provincia', 'ciudad'
        ]
        return any(keyword in text.lower() for keyword in location_keywords)
    
    async def scrape_job_details(self, page: Page, url: str) -> dict:
        """Scraper simplificado para detalles de empleo individual"""
        details = {
            "descripcion_completa": "No disponible",
            "nivel_experiencia": "No disponible",
            "beneficios_ofrecidos": "No disponible"
        }
        
        try:
            if not url or url == "No encontrado" or not url.startswith("http"):
                return details
            
            await page.goto(url, wait_until='domcontentloaded', timeout=40000)
            
            # Descripción completa
            desc_selectors = [
                '.jobs-description-content__text',
                '.jobs-box__html-content',
                '.description__text'
            ]
            
            for selector in desc_selectors:
                try:
                    desc_element = await page.query_selector(selector)
                    if desc_element:
                        desc_text = await desc_element.inner_text()
                        if desc_text and desc_text.strip():
                            details["descripcion_completa"] = desc_text.strip()
                            break
                except:
                    continue
                        

            # Nivel de experiencia              
            exp_selectors = [
                # Selector principal basado en el HTML real
                'span[dir="ltr"].job-details-jobs-unified-top-card__job-insight-view-model-secondary',
                '.job-details-jobs-unified-top-card__job-insight-view-model-secondary',
                'span[dir="ltr"][class*="job-insight-view-model-secondary"]',
                # Selectores de respaldo
                'span[class*="job-details-jobs-unified-top-card__job-insight-view-model-secondary"]',
                '.job-details-jobs-unified-top-card__job-insight',
                '.jobs-unified-top-card__job-insight'
            ]

            # Palabras clave para niveles de experiencia en LinkedIn español
            experience_keywords = [
                # Formato de LinkedIn (con mayúscula inicial)
                'prácticas', 'sin experiencia', 'algo de responsabilidad', 
                'intermedio', 'director', 'ejecutivo',
                # Formato inglés (por si acaso)
                'entry', 'senior', 'mid', 'junior', 'level',
                # Variantes adicionales
                'práctica', 'entry level', 'mid level', 'senior level'
            ]
            # Esperar a que el elemento se cargue
            await page.wait_for_selector('.job-details-jobs-unified-top-card__job-insight-view-model-secondary', timeout=5000)
            for selector in exp_selectors:
                try:
                    exp_elements = await page.query_selector_all(selector)
                    for exp_element in exp_elements:
                        exp_text = await exp_element.inner_text()
                        if exp_text:
                            # Limpiar el texto de comillas, espacios extra y comentarios HTML
                            exp_text_clean = exp_text.strip().replace('"', '').replace("'", "").replace('\n', ' ')
                            # Limpiar múltiples espacios
                            exp_text_clean = ' '.join(exp_text_clean.split())
                            if any(keyword in exp_text_clean.lower()
                                for keyword in experience_keywords):
                                details["nivel_experiencia"] = exp_text_clean
                                break
                                            
                    # Si encontramos el nivel, salimos del bucle principal
                    if details["nivel_experiencia"] != "No disponible":
                        break
                                            
                except Exception as e:
                    continue

            
            # Beneficios ofrecidos
            benefits_selectors = [
                '.jobs-unified-top-card__job-insight:has-text("beneficios")',
                '.job-details-jobs-unified-top-card__job-insight:has-text("beneficios")',
                '.jobs-benefits'
            ]
            
            for selector in benefits_selectors:
                try:
                    benefits_element = await page.query_selector(selector)
                    if benefits_element:
                        benefits_text = await benefits_element.inner_text()
                        if benefits_text and benefits_text.strip():
                            details["beneficios_ofrecidos"] = benefits_text.strip()
                            break
                except:
                    continue
            
            return details
            
        except Exception as e:
            logger.error(f"Error scrapeando detalles de {url}: {e}")
            return details