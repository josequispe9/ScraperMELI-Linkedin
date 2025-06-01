import asyncio
from playwright.async_api import async_playwright
import csv
from datetime import datetime
import random
import re
import time
from core.config import BROWSER_CONFIG, SCRAPING_CONFIG, LINKEDIN_CONFIG

class LinkedInJobsScraperTest:
    def __init__(self):
        self.jobs_data = []
        self.fecha_extraccion = datetime.now().strftime("%Y-%m-%d")
        
    async def wait_random(self, min_seconds=None, max_seconds=None):
        """Espera aleatoria usando configuración"""
        if min_seconds is None or max_seconds is None:
            min_seconds, max_seconds = SCRAPING_CONFIG.delay_range
        
        # Para pruebas, usar esperas más largas
        min_seconds = max(min_seconds, 3)
        max_seconds = max(max_seconds, 8)
        
        wait_time = random.uniform(min_seconds, max_seconds)
        print(f"⏳ Esperando {wait_time:.1f} segundos...")
        await asyncio.sleep(wait_time)
    
    async def setup_browser(self, playwright):
        """Configuración del navegador usando config module"""
        print("🔧 Configurando navegador...")
        browser = await playwright.chromium.launch(
            headless=BROWSER_CONFIG.headless,
            slow_mo=BROWSER_CONFIG.slow_mo,
            args=[
                '--no-sandbox',
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--disable-extensions',
                '--no-first-run',
                '--disable-default-apps',
                '--disable-automation',
                '--disable-web-security',
                '--allow-running-insecure-content',
                '--disable-features=VizDisplayCompositor'  # Añadido para mejor compatibilidad
            ]
        )
        
        # Contexto con configuración del módulo
        context = await browser.new_context(
            user_agent=BROWSER_CONFIG.get_random_user_agent(),
            viewport={
                'width': BROWSER_CONFIG.viewport_width, 
                'height': BROWSER_CONFIG.viewport_height
            },
            locale='es-AR',
            timezone_id='America/Argentina/Buenos_Aires',
            permissions=[],
            extra_http_headers={
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                'Accept-Language': 'es-AR,es;q=0.9,en;q=0.8',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
                'Cache-Control': 'max-age=0'
            }
        )
        
        page = await context.new_page()
        page.set_default_timeout(BROWSER_CONFIG.timeout)
        
        # Scripts para ocultar automation
        await page.add_init_script("""
            // Ocultar webdriver
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
            });
            
            // Ocultar chrome automation
            window.chrome = {
                runtime: {},
            };
            
            // Ocultar plugins automation
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5],
            });
            
            // Ocultar languages automation
            Object.defineProperty(navigator, 'languages', {
                get: () => ['es-AR', 'es', 'en'],
            });
        """)
        
        return browser, page
    
    async def check_linkedin_access(self, page):
        """Verificar que podemos acceder a LinkedIn sin problemas"""
        try:
            print("🌐 Verificando acceso a LinkedIn...")
            await page.goto("https://www.linkedin.com", wait_until="domcontentloaded", timeout=30000)
            await self.wait_random(5, 8)
            
            # Verificar si estamos bloqueados
            title = await page.title()
            print(f"📄 Título de página: {title}")
            
            if "blocked" in title.lower() or "security" in title.lower():
                print("🚫 ADVERTENCIA: Posible bloqueo detectado")
                return False
                
            # Verificar si hay CAPTCHA
            captcha = await page.query_selector('iframe[title*="captcha"], div[class*="captcha"]')
            if captcha:
                print("🔒 CAPTCHA detectado - necesitarás resolverlo manualmente")
                input("Resuelve el CAPTCHA y presiona Enter para continuar...")
            
            return True
            
        except Exception as e:
            print(f"❌ Error accediendo a LinkedIn: {e}")
            return False
    
    async def handle_auth_check(self, page):
        """Manejo de autenticación usando credenciales del config"""
        try:
            await self.wait_random(3, 5)
            
            # Verificar múltiples formas de login
            login_selectors = [
                'form[data-id="sign-in-form"]',
                '.sign-in-form',
                'a[href*="login"]',
                'button[data-tracking-control-name="guest_homepage-basic_nav-header-signin"]'
            ]
            
            for selector in login_selectors:
                login_element = await page.query_selector(selector)
                if login_element:
                    print("🔐 LinkedIn requiere autenticación")
                    
                    # Verificar si tenemos credenciales en el config
                    if LINKEDIN_CONFIG.email and LINKEDIN_CONFIG.password:
                        print("🔑 Usando credenciales del archivo de configuración")
                        success = await self.auto_login(page)
                        if success:
                            print("✅ Login automático exitoso")
                            return True
                        else:
                            print("❌ Login automático falló, requiere intervención manual")
                    
                    print("⚠️  Procediendo con login manual...")
                    print("⚠️  IMPORTANTE: Inicia sesión MANUALMENTE en la ventana del navegador")
                    print("⚠️  NO uses credenciales automatizadas")
                    print("⚠️  Asegúrate de completar cualquier verificación de seguridad")
                    input("\n✋ Presiona Enter SOLO después de iniciar sesión completamente...")
                    await self.wait_random(5, 8)
                    return True
            
            return False
            
        except Exception as e:
            print(f"⚠️  Error en verificación de autenticación: {e}")
            return False
    
    async def auto_login(self, page):
        """Intento de login automático (USAR CON PRECAUCIÓN)"""
        try:
            print("🔄 Navegando a página de login...")
            await page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded")
            await self.wait_random(2, 4)
            
            # Buscar campos de email y password
            email_field = await page.query_selector('#username')
            password_field = await page.query_selector('#password')
            login_button = await page.query_selector('button[type="submit"]')
            
            if not all([email_field, password_field, login_button]):
                print("❌ No se encontraron los campos de login")
                return False
            
            # Rellenar formulario con delay humano
            print("✍️  Rellenando email...")
            await email_field.type(LINKEDIN_CONFIG.email, delay=random.randint(50, 150))
            await self.wait_random(1, 2)
            
            print("✍️  Rellenando password...")
            await password_field.type(LINKEDIN_CONFIG.password, delay=random.randint(50, 150))
            await self.wait_random(1, 2)
            
            print("🔘 Haciendo click en login...")
            await login_button.click()
            await self.wait_random(5, 8)
            
            # Verificar si el login fue exitoso - CORREGIDO
            current_url = page.url
            print(f"🔍 URL actual después del login: {current_url}")
            
            # Verificar múltiples indicadores de login exitoso
            login_success_indicators = [
                "feed" in current_url.lower(),
                "jobs" in current_url.lower(), 
                "mynetwork" in current_url.lower(),
                current_url == "https://www.linkedin.com/"
            ]
            
            # También verificar elementos de la página
            feed_element = await page.query_selector('[data-test-id="main-feed"], .feed-container, .scaffold-layout')
            profile_element = await page.query_selector('button[data-test-id="nav-user-btn"], .global-nav__me')
            
            if any(login_success_indicators) or feed_element or profile_element:
                print("✅ Login automático exitoso")
                
                # Guardar estado de la sesión si está configurado
                if SCRAPING_CONFIG.storage_state_path:
                    try:
                        await page.context.storage_state(path=SCRAPING_CONFIG.storage_state_path)
                        print(f"💾 Estado de sesión guardado en {SCRAPING_CONFIG.storage_state_path}")
                    except Exception as e:
                        print(f"⚠️  No se pudo guardar el estado de sesión: {e}")
                
                return True
            else:
                print("❌ Login automático falló - posible verificación requerida")
                return False
                
        except Exception as e:
            print(f"❌ Error en login automático: {e}")
            return False
    
    async def safe_job_search(self, page, search_term, max_jobs=5):
        """Búsqueda MUY conservadora de empleos usando configuración - CORREGIDA"""
        try:
            # Primero navegar directamente a la sección de jobs
            print("🔍 Navegando a la sección de empleos...")
            await page.goto("https://www.linkedin.com/jobs/", wait_until="domcontentloaded")
            await self.wait_random(3, 5)
            
            # Verificar que estamos en la página de jobs
            current_url = page.url
            print(f"🔍 URL actual: {current_url}")
            
            # Buscar caja de búsqueda de empleos
            search_box_selectors = [
                'input[aria-label*="Buscar empleos"]',
                'input[placeholder*="Buscar empleos"]',
                '.jobs-search-box__text-input',
                'input[data-test-id="job-search-bar-keywords"]',
                '#jobs-search-box-keyword-id-ember'
            ]
            
            search_box = None
            for selector in search_box_selectors:
                try:
                    search_box = await page.query_selector(selector)
                    if search_box:
                        print(f"✅ Encontrada caja de búsqueda con selector: {selector}")
                        break
                except:
                    continue
            
            if not search_box:
                print("❌ No se encontró la caja de búsqueda de empleos")
                # Intentar con URL de búsqueda directa
                print("🔄 Intentando con URL de búsqueda directa...")
                search_url = f"https://www.linkedin.com/jobs/search/?keywords={search_term.replace(' ', '%20')}&location=Argentina"
                await page.goto(search_url, wait_until="domcontentloaded")
                await self.wait_random(5, 8)
            else:
                # Realizar búsqueda usando la caja de búsqueda
                print(f"🔍 Buscando: {search_term}")
                await search_box.clear()
                await search_box.type(search_term, delay=random.randint(50, 150))
                await self.wait_random(2, 3)
                
                # Buscar botón de búsqueda
                search_button_selectors = [
                    'button[aria-label*="Buscar empleos"]',
                    '.jobs-search-box__submit-button',
                    'button[data-test-id="job-search-bar-submit"]'
                ]
                
                for selector in search_button_selectors:
                    try:
                        search_button = await page.query_selector(selector)
                        if search_button:
                            await search_button.click()
                            break
                    except:
                        continue
                else:
                    # Si no encuentra botón, usar Enter
                    await search_box.press('Enter')
                
                await self.wait_random(5, 8)
            
            # Verificar que la página de resultados cargó
            title = await page.title()
            print(f"📄 Título de página después de búsqueda: {title}")
            
            # Buscar elementos de empleo con selectores más amplios
            job_selectors = [
                '.job-search-card',
                '.jobs-search-results__list-item',
                '.base-search-card',
                '[data-entity-urn*="job"]',
                '.jobs-search__results-list li',
                '.job-card-container',
                '.scaffold-layout__list-container li'
            ]
            
            jobs_found = []
            print("🔍 Buscando elementos de empleo...")
            
            for selector in job_selectors:
                try:
                    elements = await page.query_selector_all(selector)
                    if elements:
                        print(f"✅ Encontrados {len(elements)} elementos con selector: {selector}")
                        jobs_found.extend(elements[:max_jobs])
                        break
                except Exception as e:
                    print(f"⚠️  Error con selector {selector}: {e}")
                    continue
            
            if not jobs_found:
                print("⚠️  No se encontraron elementos de empleo")
                print("🔍 Intentando selectores adicionales...")
                
                # Selectores más generales como último recurso
                generic_selectors = [
                    'li[data-occludable-job-id]',
                    'div[data-job-id]',
                    'article',
                    '.artdeco-list__item'
                ]
                
                for selector in generic_selectors:
                    try:
                        elements = await page.query_selector_all(selector)
                        if elements:
                            print(f"✅ Encontrados {len(elements)} elementos genéricos con: {selector}")
                            jobs_found.extend(elements[:max_jobs])
                            break
                    except:
                        continue
            
            if not jobs_found:
                print("❌ No se pudieron encontrar empleos")
                # Debug: Guardar screenshot y HTML
                try:
                    await page.screenshot(path='debug_jobs_page.png')
                    print("📸 Screenshot guardada como debug_jobs_page.png")
                    
                    page_content = await page.content()
                    with open('debug_jobs_page.html', 'w', encoding='utf-8') as f:
                        f.write(page_content)
                    print("📝 HTML guardado como debug_jobs_page.html")
                except:
                    pass
                
                return False
            
            print(f"📊 Procesando {len(jobs_found)} elementos de empleo")
            
            # Extraer datos de forma muy conservadora
            for i, job_element in enumerate(jobs_found[:max_jobs]):
                print(f"\n📋 Procesando empleo {i+1}/{min(len(jobs_found), max_jobs)}")
                
                job_data = await self.extract_job_data_safe(job_element, i+1)
                if job_data:
                    self.jobs_data.append(job_data)
                    print(f"✅ Extraído: {job_data.get('titulo_puesto', 'N/A')}")
                else:
                    print("⚠️  No se pudo extraer datos del empleo")
                
                # Espera usando configuración (pero más larga para pruebas)
                await self.wait_random(8, 15)
            
            return True
            
        except Exception as e:
            print(f"❌ Error en búsqueda de empleos: {e}")
            return False
    
    async def extract_job_data_safe(self, job_element, index):
        """Extracción de datos MUY segura y robusta - MEJORADA"""
        try:
            job_data = {
                "indice": index,
                "fecha_extraccion": self.fecha_extraccion,
                "titulo_puesto": "No encontrado",
                "empresa": "No encontrado", 
                "ubicacion": "No encontrado",
                "url_empleo": "No encontrado",
                "descripcion_breve": "No encontrado"
            }
            
            # Múltiples selectores para título - AMPLIADOS
            title_selectors = [
                '.base-search-card__title a',
                '.job-search-card__title a',
                'h3 a',
                'h4 a',
                '[data-tracking-control-name="public_jobs_jserp-result_search-card"] h3 a',
                '.job-card-list__title a',
                '.jobs-search-results__list-item h3 a',
                'a[data-tracking-control-name*="job"]',
                '.scaffold-layout__list-detail h3 a'
            ]
            
            for selector in title_selectors:
                try:
                    title_element = await job_element.query_selector(selector)
                    if title_element:
                        title_text = await title_element.inner_text()
                        if title_text and title_text.strip():
                            job_data["titulo_puesto"] = title_text.strip()
                            
                            # Obtener URL
                            href = await title_element.get_attribute("href")
                            if href:
                                if href.startswith("http"):
                                    job_data["url_empleo"] = href
                                else:
                                    job_data["url_empleo"] = f"https://www.linkedin.com{href}"
                            break
                except:
                    continue
            
            # Si no encontramos título con links, buscar texto directo
            if job_data["titulo_puesto"] == "No encontrado":
                title_text_selectors = [
                    'h3',
                    'h4',
                    '.job-title',
                    '[data-test-id*="title"]'
                ]
                
                for selector in title_text_selectors:
                    try:
                        title_element = await job_element.query_selector(selector)
                        if title_element:
                            title_text = await title_element.inner_text()
                            if title_text and title_text.strip():
                                job_data["titulo_puesto"] = title_text.strip()
                                break
                    except:
                        continue
            
            # Múltiples selectores para empresa - AMPLIADOS
            company_selectors = [
                '.base-search-card__subtitle a',
                '.job-search-card__subtitle-link',
                'h4 a',
                '.base-search-card__subtitle',
                '.job-card-container__company-name',
                '.jobs-search-results__list-item h4',
                '[data-test-id*="company"]'
            ]
            
            for selector in company_selectors:
                try:
                    company_element = await job_element.query_selector(selector)
                    if company_element:
                        company_text = await company_element.inner_text()
                        if company_text and company_text.strip():
                            job_data["empresa"] = company_text.strip()
                            break
                except:
                    continue
            
            # Múltiples selectores para ubicación - AMPLIADOS
            location_selectors = [
                '.job-search-card__location',
                '.base-search-card__metadata',
                '.job-search-card__subtitle + div',
                '.job-card-container__metadata',
                '[data-test-id*="location"]'
            ]
            
            for selector in location_selectors:
                try:
                    location_element = await job_element.query_selector(selector)
                    if location_element:
                        location_text = await location_element.inner_text()
                        if location_text and location_text.strip():
                            # Limpiar texto de ubicación
                            clean_location = re.sub(r'\s+', ' ', location_text.strip())
                            job_data["ubicacion"] = clean_location
                            break
                except:
                    continue
            
            # Intentar extraer descripción breve si está disponible
            description_selectors = [
                '.job-search-card__snippet',
                '.base-search-card__snippet',
                '.job-card-container__snippet'
            ]
            
            for selector in description_selectors:
                try:
                    desc_element = await job_element.query_selector(selector)
                    if desc_element:
                        desc_text = await desc_element.inner_text()
                        if desc_text and desc_text.strip():
                            job_data["descripcion_breve"] = desc_text.strip()[:200]  # Limitar longitud
                            break
                except:
                    continue
            
            return job_data
            
        except Exception as e:
            print(f"⚠️  Error extrayendo empleo {index}: {e}")
            return None
    
    def save_test_results(self, filename="linkedin_test_results.csv"):
        """Guardar resultados de prueba"""
        if not self.jobs_data:
            print("⚠️  No hay datos para guardar")
            return
        
        try:
            with open(filename, "w", newline="", encoding="utf-8") as f:
                if self.jobs_data:
                    fieldnames = list(self.jobs_data[0].keys())
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(self.jobs_data)
            
            print(f"✅ Resultados de prueba guardados en {filename}")
            print(f"📊 Total de empleos extraídos: {len(self.jobs_data)}")
            
        except Exception as e:
            print(f"❌ Error guardando resultados: {e}")

# Función de prueba principal
async def test_scraper():
    """Función de prueba MUY conservadora - MEJORADA"""
    print("🧪 INICIANDO PRUEBA DE SCRAPER LINKEDIN")
    print("=" * 50)
    print("⚠️  ADVERTENCIAS IMPORTANTES:")
    print("   - Esta es una prueba muy limitada (máximo 5 empleos)")
    print("   - Usa esperas largas entre acciones")
    print("   - Requiere intervención manual para login")
    print("   - Detente si detectas cualquier problema")
    print("   - LinkedIn puede bloquear tu cuenta")
    print("=" * 50)
    
    response = input("\n¿Continuar con la prueba? (si/no): ").lower()
    if response not in ['si', 's', 'yes', 'y']:
        print("🛑 Prueba cancelada por el usuario")
        return
    
    scraper = LinkedInJobsScraperTest()
    
    async with async_playwright() as p:
        browser, page = await scraper.setup_browser(p)
        
        try:
            # Paso 1: Verificar acceso básico
            print("\n🔍 PASO 1: Verificando acceso a LinkedIn...")
            if not await scraper.check_linkedin_access(page):
                print("❌ No se pudo acceder a LinkedIn")
                return
            
            # Paso 2: Manejar autenticación
            print("\n🔐 PASO 2: Verificando autenticación...")
            await scraper.handle_auth_check(page)
            
            # Paso 3: Prueba de búsqueda muy conservadora
            print("\n🔍 PASO 3: Realizando búsqueda de prueba...")
            search_term = "Python Developer"  # Término básico
            success = await scraper.safe_job_search(page, search_term, max_jobs=3)  # Solo 3 empleos
            
            if success:
                print("✅ Prueba completada exitosamente")
            else:
                print("⚠️  Prueba completada con problemas")
            
            # Paso 4: Guardar resultados
            print("\n💾 PASO 4: Guardando resultados...")
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"linkedin_test_{timestamp}.csv"
            scraper.save_test_results(filename)
            
        except Exception as e:
            print(f"❌ Error durante la prueba: {e}")
        
        finally:
            print("\n🔄 Cerrando navegador...")
            await scraper.wait_random(3, 5)
            await browser.close()
    
    print("\n✅ Prueba finalizada")
    
    if scraper.jobs_data:
        print("\n📊 RESUMEN DE RESULTADOS:")
        for i, job in enumerate(scraper.jobs_data, 1):
            print(f"   {i}. {job.get('titulo_puesto', 'N/A')} - {job.get('empresa', 'N/A')}")

if __name__ == "__main__":
    asyncio.run(test_scraper())