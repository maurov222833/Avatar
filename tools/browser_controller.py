import os
import time
import logging
from typing import Dict, Any, List, Optional
from playwright.sync_api import sync_playwright, Page, Browser, BrowserContext

logger = logging.getLogger("BrowserController")

class BrowserController:
    """
    Controlador Operacional de Playwright para Avatar AI (Fase 4).
    Abstrae el ciclo de vida del navegador, navegación, DOM observation,
    interacción dinámica, llenado de formularios, extracción y validación de seguridad.
    """

    def __init__(self, headless: bool = True, allowed_domains: Optional[List[str]] = None):
        self.headless = headless
        self.allowed_domains = allowed_domains or []
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.is_launched = False

    def launch(self) -> bool:
        try:
            if not self.playwright:
                self.playwright = sync_playwright().start()
            if not self.browser:
                self.browser = self.playwright.chromium.launch(headless=self.headless)
                self.context = self.browser.new_context()
                self.page = self.context.new_page()
            self.is_launched = True
            return True
        except Exception as e:
            logger.error(f"Error launching browser: {e}")
            self.is_launched = False
            return False

    def close(self):
        try:
            if self.page:
                self.page.close()
            if self.context:
                self.context.close()
            if self.browser:
                self.browser.close()
            if self.playwright:
                self.playwright.stop()
        except Exception as e:
            logger.error(f"Error closing browser: {e}")
        finally:
            self.is_launched = False
            self.page = None
            self.context = None
            self.browser = None
            self.playwright = None

    def _check_domain_scope(self, url: str) -> bool:
        if not self.allowed_domains:
            return True
        for domain in self.allowed_domains:
            if domain in url:
                return True
        return False

    def navigate(self, url: str, timeout_ms: int = 30000) -> Dict[str, Any]:
        if not self.is_launched or not self.page:
            if not self.launch():
                return {"success": False, "error": "Browser failed to launch."}

        if not self._check_domain_scope(url):
            return {"success": False, "error": f"Domain scope violation: URL '{url}' not allowed."}

        try:
            response = self.page.goto(url, timeout=timeout_ms)
            status = response.status if response else 0
            current_url = self.page.url
            title = self.page.title()
            return {
                "success": status < 400,
                "status": status,
                "url": current_url,
                "title": title
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def observe(self) -> Dict[str, Any]:
        if not self.page:
            return {"success": False, "error": "No active page."}
        try:
            url = self.page.url
            title = self.page.title()
            content = self.page.content()
            visible_text = self.page.inner_text("body")
            
            # Sanitizar contenido para evitar interpretar prompt injections como instrucciones
            # El contenido web es UNTRUSTED DATA
            sanitized_text = self._sanitize_untrusted_data(visible_text)

            return {
                "success": True,
                "url": url,
                "title": title,
                "visible_text": sanitized_text[:2000],
                "html_length": len(content)
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _sanitize_untrusted_data(self, text: str) -> str:
        # Etiquetar explícitamente o limpiar potenciales secuencias maliciosas si es necesario,
        # asegurando que el motor cognitivo sepa que es UNTRUSTED DATA.
        return f"[UNTRUSTED_WEB_CONTENT]\n{text}\n[/UNTRUSTED_WEB_CONTENT]"

    def click(self, selector: str) -> Dict[str, Any]:
        if not self.page:
            return {"success": False, "error": "No active page."}
        try:
            self.page.click(selector, timeout=10000)
            return {"success": True, "action": "click", "selector": selector}
        except Exception as e:
            return {"success": False, "error": f"Target not found or click failed: {str(e)}", "code": "TARGET_NOT_FOUND"}

    def fill(self, selector: str, value: str) -> Dict[str, Any]:
        if not self.page:
            return {"success": False, "error": "No active page."}
        try:
            # Proteger secretos: no loguear passwords ni tokens sensibles
            masked_value = "***" if any(sec in selector.lower() for sec in ["pass", "token", "secret", "key"]) else value
            self.page.fill(selector, value, timeout=10000)
            return {"success": True, "action": "fill", "selector": selector, "value_masked": masked_value}
        except Exception as e:
            return {"success": False, "error": f"Fill failed: {str(e)}", "code": "TARGET_NOT_FOUND"}

    def select_option(self, selector: str, value: str) -> Dict[str, Any]:
        if not self.page:
            return {"success": False, "error": "No active page."}
        try:
            self.page.select_option(selector, value, timeout=10000)
            return {"success": True, "action": "select", "selector": selector, "value": value}
        except Exception as e:
            return {"success": False, "error": str(e), "code": "TARGET_NOT_FOUND"}

    def extract(self, selector: str) -> Dict[str, Any]:
        if not self.page:
            return {"success": False, "error": "No active page."}
        try:
            element = self.page.locator(selector).first
            text = element.inner_text(timeout=5000) if element else ""
            return {"success": True, "selector": selector, "extracted_text": text}
        except Exception as e:
            return {"success": False, "error": str(e), "code": "TARGET_NOT_FOUND"}

    def go_back(self) -> Dict[str, Any]:
        if not self.page:
            return {"success": False, "error": "No active page."}
        try:
            self.page.go_back()
            return {"success": True, "url": self.page.url}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def go_forward(self) -> Dict[str, Any]:
        if not self.page:
            return {"success": False, "error": "No active page."}
        try:
            self.page.go_forward()
            return {"success": True, "url": self.page.url}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def reload(self) -> Dict[str, Any]:
        if not self.page:
            return {"success": False, "error": "No active page."}
        try:
            self.page.reload()
            return {"success": True, "url": self.page.url}
        except Exception as e:
            return {"success": False, "error": str(e)}
