import asyncio
from playwright.async_api import async_playwright
import csv
from datetime import datetime
import random
import re
from core.config import BROWSER_CONFIG, SCRAPING_CONFIG, LINKEDIN_CONFIG

class LinkedInJobsScraper:
    def __init__(self):
        self.jobs_data = []
        self.fecha_extraccion = datetime.now().strftime("%Y-%m-%d")
        
    async def wait_random(self, min_seconds=3, max_seconds=8):
        """Espera aleatoria"""
        wait_time = random.uniform(min_seconds, max_seconds)
        print(f"⏳ Esperando {wait_time:.1f} segundos...")
        await asyncio.sleep(wait_time)
    
    async def setup_browser(self, playwright):
        """Configuración básica del navegador"""
        print("🔧 Configurando navegador...")
        
        browser = await playwright.chromium.launch(
            headless=BROWSER_CONFIG.headless,
            slow_mo=BROWSER_CONFIG.slow_mo,
            args=['--no-sandbox', '--disable-blink-features=AutomationControlled']
        )
        
        context = await browser.new_context(
            user_agent=BROWSER_CONFIG.get_random_user_agent(),
            viewport={'width': 1920, 'height': 1080},
            locale='es-AR'
        )
        
        page = await context.new_page()
        page.set_default_timeout(30000)
        
        # Script anti-detección básico
        await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        """)
        
        return browser, page
    
    async def handle_login(self, page):
        """Manejo simplificado de login"""
        try:
            print("🔐 Verificando si necesita login...")
            await page.goto("https://www.linkedin.com/jobs/", wait_until="domcontentloaded")
            await self.wait_random(3, 5)
            
            # Verificar si hay elementos de login
            login_needed = await page.query_selector('a[href*="login"], .sign-in-form')
            
            if login_needed:
                print("🔑 Se requiere login")
                
                if LINKEDIN_CONFIG.email and LINKEDIN_CONFIG.password:
                    return await self.auto_login(page)
                else:
                    print("⚠️  Por favor, inicia sesión manualmente en la ventana del navegador")
                    input("✋ Presiona Enter después de iniciar sesión...")
                    await self.wait_random(3, 5)
            
            return True
            
        except Exception as e:
            print(f"❌ Error en login: {e}")
            return False
    
    async def auto_login(self, page):
        """Login automático simplificado"""
        try:
            print("🔄 Intentando login automático...")
            await page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded")
            await self.wait_random(2, 3)
            
            # Rellenar campos
            await page.fill('#username', LINKEDIN_CONFIG.email)
            await page.fill('#password', LINKEDIN_CONFIG.password)
            await page.click('button[type="submit"]')
            await self.wait_random(5, 8)
            
            # Verificar éxito
            if "feed" in page.url or "jobs" in page.url:
                print("✅ Login exitoso")
                return True
            else:
                print("❌ Login falló")
                return False
                
        except Exception as e:
            print(f"❌ Error en auto-login: {e}")
            return False
    
    async def search_jobs(self, page, search_term, max_jobs=5):
        """Búsqueda de empleos simplificada y corregida"""
        try:
            print(f"🔍 Buscando: {search_term}")
            
            # Navegar directamente con parámetros de búsqueda
            search_url = f"https://www.linkedin.com/jobs/search/?keywords={search_term.replace(' ', '%20')}&location=Argentina"
            print(f"🌐 Navegando a: {search_url}")
            
            await page.goto(search_url, wait_until="domcontentloaded")
            await self.wait_random(5, 8)
            
            # Esperar a que carguen los resultados - SELECTORES CORREGIDOS
            print("⏳ Esperando que carguen los resultados...")
            try:
                # Basado en el HTML real, buscar elementos <li> que contienen trabajos
                await page.wait_for_selector('ul li[data-occludable-job-id], ul li:has(a[href*="/jobs/view/"])', timeout=15000)
                print("✅ Resultados cargados")
            except:
                print("⚠️  Timeout esperando resultados, continuando...")
            
            # SELECTORES CORREGIDOS basados en el HTML real
            job_elements = []
            selectors_to_try = [
                'ul li:has(a[href*="/jobs/view/"])',  # Selector más específico basado en el HTML
                'li[data-occludable-job-id]',         # Backup selector
                'li:has(div div div div div div a[href*="/jobs/view/"])'  # Selector muy específico
            ]
            
            for selector in selectors_to_try:
                try:
                    elements = await page.query_selector_all(selector)
                    if elements:
                        print(f"✅ Encontrados {len(elements)} empleos con selector: {selector}")
                        job_elements = elements[:max_jobs]
                        break
                except:
                    continue
            
            # Si no funciona, intentar con un enfoque más directo
            if not job_elements:
                print("🔄 Probando selectores alternativos...")
                # Buscar directamente los links de trabajos
                job_links = await page.query_selector_all('a[href*="/jobs/view/"]')
                if job_links:
                    print(f"✅ Encontrados {len(job_links)} links de empleos")
                    # Obtener los elementos padre que contienen toda la información
                    job_elements = []
                    for link in job_links[:max_jobs]:
                        # Navegar hacia arriba para encontrar el contenedor del trabajo
                        parent = await link.query_selector('xpath=ancestor::li[1]')
                        if parent:
                            job_elements.append(parent)
            
            if not job_elements:
                print("❌ No se encontraron empleos")
                await self.debug_page(page)
                return False
            
            # Extraer datos
            print(f"📊 Extrayendo datos de {len(job_elements)} empleos...")
            for i, element in enumerate(job_elements, 1):
                job_data = await self.extract_job_data(element, i)
                if job_data:
                    self.jobs_data.append(job_data)
                    print(f"✅ Extraído: {job_data['titulo_puesto']}")
                
                await self.wait_random(2, 4)
            
            return True
            
        except Exception as e:
            print(f"❌ Error en búsqueda: {e}")
            return False
    
    async def extract_job_data(self, job_element, index):
        """Extracción de datos CORREGIDA basada en el HTML real"""
        try:
            job_data = {
                "indice": index,
                "fecha_extraccion": self.fecha_extraccion,
                "titulo_puesto": "No encontrado",
                "empresa": "No encontrado",
                "ubicacion": "No encontrado",
                "url_empleo": "No encontrado",
                "modalidad": "No encontrado",
                "fecha_publicacion": "No encontrado"
            }
            
            # TÍTULO Y URL - Basado en la estructura real del HTML
            title_selectors = [
                'a[href*="/jobs/view/"] span strong',  # Selector específico del HTML
                'a[href*="/jobs/view/"] strong',
                'div div div div div div a[href*="/jobs/view/"] span strong',
                'a[href*="/jobs/view/"]'  # Fallback
            ]
            
            for selector in title_selectors:
                try:
                    element = await job_element.query_selector(selector)
                    if element:
                        title = await element.inner_text()
                        if title and title.strip():
                            job_data["titulo_puesto"] = title.strip()
                            
                            # Obtener URL del link padre
                            link_element = await element.query_selector('xpath=ancestor::a[1]')
                            if not link_element:
                                link_element = await job_element.query_selector('a[href*="/jobs/view/"]')
                            
                            if link_element:
                                href = await link_element.get_attribute('href')
                                if href:
                                    job_data["url_empleo"] = href if href.startswith('http') else f"https://www.linkedin.com{href}"
                            break
                except:
                    continue
            
            # EMPRESA - Basado en la estructura del HTML
            company_selectors = [
                'span[dir="ltr"]:not(:has(strong))',  # Span con dirección ltr que no tiene strong (título)
                'div:nth-child(2) span[dir="ltr"]',   # Segundo div con span
                'div + div span[dir="ltr"]'           # Span en div siguiente
            ]
            
            for selector in company_selectors:
                try:
                    elements = await job_element.query_selector_all(selector)
                    for element in elements:
                        text = await element.inner_text()
                        if text and text.strip() and not any(keyword in text.lower() for keyword in ['comuna', 'provincia', 'argentina', 'híbrido', 'remoto', 'presencial']):
                            job_data["empresa"] = text.strip()
                            break
                    if job_data["empresa"] != "No encontrado":
                        break
                except:
                    continue
            
            # UBICACIÓN - Buscar spans que contengan información de ubicación
            location_selectors = [
                'span[dir="ltr"]:has-text("Argentina")',
                'span[dir="ltr"]:has-text("Buenos Aires")',
                'span[dir="ltr"]:has-text("Comuna")',
                'ul li span[dir="ltr"]'
            ]
            
            for selector in location_selectors:
                try:
                    element = await job_element.query_selector(selector)
                    if element:
                        location = await element.inner_text()
                        if location and any(keyword in location.lower() for keyword in ['argentina', 'buenos aires', 'comuna', 'remoto', 'híbrido', 'presencial']):
                            job_data["ubicacion"] = re.sub(r'\s+', ' ', location.strip())
                            
                            # Extraer modalidad de trabajo
                            if 'híbrido' in location.lower():
                                job_data["modalidad"] = "Híbrido"
                            elif 'remoto' in location.lower():
                                job_data["modalidad"] = "Remoto"
                            elif 'presencial' in location.lower():
                                job_data["modalidad"] = "Presencial"
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
                    element = await job_element.query_selector(selector)
                    if element:
                        if selector == 'time[datetime]':
                            datetime_attr = await element.get_attribute('datetime')
                            if datetime_attr:
                                job_data["fecha_publicacion"] = datetime_attr
                        else:
                            time_text = await element.inner_text()
                            if time_text:
                                job_data["fecha_publicacion"] = time_text.strip()
                        break
                except:
                    continue
            
            return job_data
            
        except Exception as e:
            print(f"⚠️  Error extrayendo empleo {index}: {e}")
            return None
    
    async def debug_page(self, page):
        """Debug mejorado para entender la estructura"""
        try:
            print("🔍 Debug: Información de la página actual")
            print(f"📄 URL: {page.url}")
            print(f"📄 Título: {await page.title()}")
            
            # Buscar elementos con diferentes selectores para debug
            debug_selectors = [
                'ul li',
                'a[href*="/jobs/view/"]',
                'li[data-occludable-job-id]',
                '.job-search-card',
                'strong'
            ]
            
            for selector in debug_selectors:
                try:
                    elements = await page.query_selector_all(selector)
                    print(f"🔍 Selector '{selector}': {len(elements)} elementos encontrados")
                    
                    if elements and len(elements) > 0:
                        # Mostrar texto del primer elemento para debug
                        first_text = await elements[0].inner_text()
                        print(f"   Primer elemento: {first_text[:100]}...")
                except:
                    print(f"❌ Error con selector: {selector}")
            
            # Tomar screenshot para debug
            await page.screenshot(path='debug_linkedin.png')
            print("📸 Screenshot guardada: debug_linkedin.png")
            
        except Exception as e:
            print(f"⚠️  Error en debug: {e}")
    
    def save_results(self, filename=None):
        """Guardar resultados"""
        if not self.jobs_data:
            print("⚠️  No hay datos para guardar")
            return
        
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"linkedin_jobs_{timestamp}.csv"
        
        try:
            with open(filename, "w", newline="", encoding="utf-8") as f:
                fieldnames = list(self.jobs_data[0].keys())
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(self.jobs_data)
            
            print(f"✅ Datos guardados en: {filename}")
            print(f"📊 Total empleos: {len(self.jobs_data)}")
            
            # Mostrar resumen de datos extraídos
            print("\n📋 RESUMEN DE DATOS EXTRAÍDOS:")
            print("-" * 40)
            for i, job in enumerate(self.jobs_data, 1):
                print(f"{i}. {job['titulo_puesto']} | {job['empresa']} | {job['ubicacion']}")
            
        except Exception as e:
            print(f"❌ Error guardando: {e}")

async def main():
    """Función principal simplificada"""
    print("🚀 INICIANDO SCRAPER LINKEDIN CORREGIDO")
    print("=" * 50)
    
    scraper = LinkedInJobsScraper()
    
    async with async_playwright() as p:
        browser, page = await scraper.setup_browser(p)
        
        try:
            # Login
            if not await scraper.handle_login(page):
                print("❌ No se pudo completar el login")
                return
            
            # Búsqueda
            search_term = "Python Developer"
            success = await scraper.search_jobs(page, search_term, max_jobs=5)
            
            if success:
                print("✅ Scraping completado")
                scraper.save_results()
            else:
                print("❌ Scraping falló")
            
        except Exception as e:
            print(f"❌ Error general: {e}")
        
        finally:
            await browser.close()
            print("🔄 Navegador cerrado")

if __name__ == "__main__":
    asyncio.run(main())