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
        
    async def wait_random(self, min_seconds=None, max_seconds=None):
        if min_seconds is None or max_seconds is None:
            min_seconds, max_seconds = SCRAPING_CONFIG.delay_range
        
        wait_time = random.uniform(min_seconds, max_seconds)
        await asyncio.sleep(wait_time)
    
    async def setup_browser(self, playwright):
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
                '--disable-features=VizDisplayCompositor'
            ]
        )
        
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
        
        await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
            });
            
            window.chrome = {
                runtime: {},
            };
            
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5],
            });
            
            Object.defineProperty(navigator, 'languages', {
                get: () => ['es-AR', 'es', 'en'],
            });
        """)
        
        return browser, page
    
    async def check_linkedin_access(self, page):
        try:
            await page.goto("https://www.linkedin.com", wait_until="domcontentloaded", timeout=30000)
            await self.wait_random(3, 5)
            
            title = await page.title()
            
            if "blocked" in title.lower() or "security" in title.lower():
                return False
                
            captcha = await page.query_selector('iframe[title*="captcha"], div[class*="captcha"]')
            if captcha:
                input("Resuelve el CAPTCHA y presiona Enter para continuar...")
            
            return True
            
        except Exception:
            return False
    
    async def handle_auth_check(self, page):
        try:
            await self.wait_random(2, 4)
            
            login_selectors = [
                'form[data-id="sign-in-form"]',
                '.sign-in-form',
                'a[href*="login"]',
                'button[data-tracking-control-name="guest_homepage-basic_nav-header-signin"]'
            ]
            
            for selector in login_selectors:
                login_element = await page.query_selector(selector)
                if login_element:
                    if LINKEDIN_CONFIG.email and LINKEDIN_CONFIG.password:
                        return await self.auto_login(page)
                    else:
                        input("Inicia sesión manualmente y presiona Enter para continuar...")
                        await self.wait_random(3, 5)
                        return True
            
            return True
            
        except Exception:
            return False
    
    async def auto_login(self, page):
        try:
            await page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded")
            await self.wait_random(2, 4)
            
            email_field = await page.query_selector('#username')
            password_field = await page.query_selector('#password')
            login_button = await page.query_selector('button[type="submit"]')
            
            if not all([email_field, password_field, login_button]):
                return False
            
            await email_field.type(LINKEDIN_CONFIG.email, delay=random.randint(50, 150))
            await self.wait_random(1, 2)
            
            await password_field.type(LINKEDIN_CONFIG.password, delay=random.randint(50, 150))
            await self.wait_random(1, 2)
            
            await login_button.click()
            await self.wait_random(5, 8)
            
            current_url = page.url
            
            login_success_indicators = [
                "feed" in current_url.lower(),
                "jobs" in current_url.lower(), 
                "mynetwork" in current_url.lower(),
                current_url == "https://www.linkedin.com/"
            ]
            
            feed_element = await page.query_selector('[data-test-id="main-feed"], .feed-container, .scaffold-layout')
            profile_element = await page.query_selector('button[data-test-id="nav-user-btn"], .global-nav__me')
            
            if any(login_success_indicators) or feed_element or profile_element:
                if SCRAPING_CONFIG.storage_state_path:
                    try:
                        await page.context.storage_state(path=SCRAPING_CONFIG.storage_state_path)
                    except Exception:
                        pass
                return True
            else:
                return False
                
        except Exception:
            return False
    
    async def search_jobs(self, page, search_term, max_jobs=50):
        try:
            await page.goto("https://www.linkedin.com/jobs/", wait_until="domcontentloaded")
            await self.wait_random(3, 5)
            
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
                        break
                except:
                    continue
            
            if not search_box:
                search_url = f"https://www.linkedin.com/jobs/search/?keywords={search_term.replace(' ', '%20')}&location=Argentina"
                await page.goto(search_url, wait_until="domcontentloaded")
                await self.wait_random(5, 8)
            else:
                await search_box.clear()
                await search_box.type(search_term, delay=random.randint(50, 150))
                await self.wait_random(2, 3)
                
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
                    await search_box.press('Enter')
                
                await self.wait_random(5, 8)
            
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
            
            for selector in job_selectors:
                try:
                    elements = await page.query_selector_all(selector)
                    if elements:
                        jobs_found.extend(elements[:max_jobs])
                        break
                except Exception:
                    continue
            
            if not jobs_found:
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
                            jobs_found.extend(elements[:max_jobs])
                            break
                    except:
                        continue
            
            if not jobs_found:
                return False
            
            for i, job_element in enumerate(jobs_found[:max_jobs]):
                job_data = await self.extract_job_data(job_element, i+1)
                if job_data:
                    self.jobs_data.append(job_data)
                
                await self.wait_random()
            
            return True
            
        except Exception:
            return False
    
    async def extract_job_data(self, job_element, index):
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
                            
                            href = await title_element.get_attribute("href")
                            if href:
                                if href.startswith("http"):
                                    job_data["url_empleo"] = href
                                else:
                                    job_data["url_empleo"] = f"https://www.linkedin.com{href}"
                            break
                except:
                    continue
            
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
                            clean_location = re.sub(r'\s+', ' ', location_text.strip())
                            job_data["ubicacion"] = clean_location
                            break
                except:
                    continue
            
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
                            job_data["descripcion_breve"] = desc_text.strip()[:200]
                            break
                except:
                    continue
            
            return job_data
            
        except Exception:
            return None
    
    def save_results(self, filename="linkedin_jobs.csv"):
        if not self.jobs_data:
            return
        
        try:
            with open(filename, "w", newline="", encoding="utf-8") as f:
                if self.jobs_data:
                    fieldnames = list(self.jobs_data[0].keys())
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(self.jobs_data)
            
        except Exception:
            pass

async def scrape_linkedin_jobs(search_term, max_jobs=50):
    scraper = LinkedInJobsScraper()
    
    async with async_playwright() as p:
        browser, page = await scraper.setup_browser(p)
        
        try:
            if not await scraper.check_linkedin_access(page):
                return False
            
            await scraper.handle_auth_check(page)
            
            success = await scraper.search_jobs(page, search_term, max_jobs)
            
            if success:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"linkedin_jobs_{timestamp}.csv"
                scraper.save_results(filename)
                return True
            
            return False
            
        except Exception:
            return False
        
        finally:
            await browser.close()
    
    return scraper.jobs_data