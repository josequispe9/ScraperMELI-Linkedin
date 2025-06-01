from playwright.async_api import async_playwright, Browser, BrowserContext, Page
import asyncio
from contextlib import asynccontextmanager
from typing import Optional, List
from .config import BROWSER_CONFIG, SCRAPING_CONFIG
from .logger import get_logger, LogConfig
import json
import random  
from pathlib import Path

config = LogConfig(json_format=False)
logger = get_logger("scraper", config)

class BrowserManager:
    def __init__(self):
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.contexts: List[BrowserContext] = []
        
    async def start(self):
        """Inicializar Playwright y navegador Chromium"""
        if not self.playwright:
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(
                headless=BROWSER_CONFIG.headless,
                slow_mo=BROWSER_CONFIG.slow_mo,
                args=[
                    '--no-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-blink-features=AutomationControlled',
                    '--disable-web-security',
                    '--disable-features=VizDisplayCompositor'
                ]
            )
            logger.info("Browser iniciado correctamente", extra={"event": "browser_start"})
    
    async def create_context(self, storage_state: Optional[str] = None) -> BrowserContext:
        """Crear un nuevo contexto de navegador con configuración y sesión opcional"""
        if not self.browser:
            await self.start()
            
        context_options = {
            'viewport': {
                'width': BROWSER_CONFIG.viewport_width, 
                'height': BROWSER_CONFIG.viewport_height
            },
            'user_agent': BROWSER_CONFIG.get_random_user_agent(),
            'ignore_https_errors': True,
            'java_script_enabled': True,
        }
        
        # Cargar estado de sesión si existe
        if storage_state and Path(storage_state).exists():
            context_options['storage_state'] = storage_state
            logger.info(f"Cargando sesión desde: {storage_state}", extra={"event": "load_session"})
            
        context = await self.browser.new_context(**context_options)
        self.contexts.append(context)
        
        # Configurar modo stealth para evitar detección como bot
        await self._setup_stealth_mode(context)
        
        return context
    
    async def _setup_stealth_mode(self, context: BrowserContext):
        """Configurar modo stealth para evitar detección de automatización"""
        page = await context.new_page()
        await page.add_init_script(
            """
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
            });

            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3],
            });

            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en'],
            });

            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => 
                parameters.name === 'notifications' 
                ? Promise.resolve({ state: Notification.permission }) 
                : originalQuery(parameters);
            """
        )
        await page.close()
        logger.debug("Modo stealth configurado para el contexto", extra={"event": "stealth_mode"})
        
    async def save_session(self, context: BrowserContext, path: str):
        """Guardar estado de sesión para reutilización posterior"""
        try:
            storage_state = await context.storage_state()
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            with open(path, 'w') as f:
                json.dump(storage_state, f)
            logger.info(f"Sesión guardada en: {path}", extra={"event": "save_session"})
        except Exception as e:
            logger.error(f"Error guardando sesión: {e}", extra={"event": "save_session_error", "error": str(e)})
    
    async def close(self):
        """Cerrar todos los contextos y el navegador"""
        for context in self.contexts:
            await context.close()
        self.contexts.clear()
        
        if self.browser:
            await self.browser.close()
            self.browser = None
            
        if self.playwright:
            await self.playwright.stop()
            self.playwright = None
            
        logger.info("Browser cerrado correctamente", extra={"event": "browser_close"})

# Context manager para manejo sencillo y seguro del navegador
@asynccontextmanager
async def managed_browser():
    manager = BrowserManager()
    try:
        await manager.start()
        yield manager
    finally:
        await manager.close()

class PagePool:
    def __init__(self, context: BrowserContext, size: int = 3):
        self.context = context
        self.size = size
        self.pages: List[Page] = []
        self.available_pages = asyncio.Queue()
        
    async def initialize(self):
        """Inicializar el pool de páginas para paralelización"""
        for _ in range(self.size):
            page = await self.context.new_page()
            page.set_default_timeout(BROWSER_CONFIG.timeout)
            self.pages.append(page)
            await self.available_pages.put(page)
        logger.info(f"Pool de {self.size} páginas inicializado", extra={"event": "page_pool_init"})
    
    async def get_page(self) -> Page:
        """Obtener página disponible del pool"""
        page = await self.available_pages.get()
        logger.debug("Página obtenida del pool", extra={"event": "page_pool_get"})
        return page
    
    async def return_page(self, page: Page):
        """Devolver página al pool"""
        await self.available_pages.put(page)
        logger.debug("Página devuelta al pool", extra={"event": "page_pool_return"})
    
    async def close_all(self):
        """Cerrar todas las páginas"""
        for page in self.pages:
            await page.close()
        logger.info("Todas las páginas del pool han sido cerradas", extra={"event": "page_pool_close"})
