"""
Playwright browser lifecycle manager for accessibility testing.

This module manages Playwright browser instances, page navigation, 
screenshots, and DOM extraction for the accessibility auditor environment.
"""

from typing import Optional
from playwright.sync_api import sync_playwright, Browser, Page, Playwright


class BrowserManager:
    """Manages Playwright browser lifecycle for accessibility testing."""
    
    def __init__(self):
        """Initialize browser manager with no active browser."""
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
    
    def start(self):
        """Initialize Playwright and launch browser."""
        if self.playwright is not None:
            return  # Already started
        
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--allow-file-access-from-files",
                "--disable-web-security",
            ],
        )
        self.page = self.browser.new_page(viewport={"width": 1280, "height": 720})
    
    def navigate_to_url(self, url: str) -> bool:
        """
        Navigate to URL and wait for load.
        
        Args:
            url: URL to navigate to (supports http://, https://, file://)
        
        Returns:
            True if navigation successful, False otherwise
        """
        if self.page is None:
            return False
        
        try:
            self.page.goto(url, wait_until="networkidle", timeout=30000)
            return True
        except Exception as e:
            print(f"Navigation error: {e}")
            return False
    
    def get_screenshot(self) -> bytes:
        """
        Capture full-page screenshot as PNG bytes.
        
        Returns:
            Screenshot as PNG bytes
        
        Raises:
            RuntimeError: If no page is loaded
        """
        if self.page is None:
            raise RuntimeError("No page loaded. Call start() and navigate_to_url() first.")
        
        return self.page.screenshot(full_page=True)
    
    def get_dom_summary(self) -> str:
        """
        Extract simplified DOM structure.
        
        Returns:
            HTML content of document.body, limited to first 5000 characters
        
        Raises:
            RuntimeError: If no page is loaded
        """
        if self.page is None:
            raise RuntimeError("No page loaded. Call start() and navigate_to_url() first.")
        
        html = self.page.evaluate("() => document.body.innerHTML")
        return html[:5000] if html else ""
    
    def get_page_metadata(self) -> dict:
        """
        Get page title, URL, viewport.
        
        Returns:
            Dictionary with page metadata
        
        Raises:
            RuntimeError: If no page is loaded
        """
        if self.page is None:
            raise RuntimeError("No page loaded. Call start() and navigate_to_url() first.")
        
        return {
            "url": self.page.url,
            "title": self.page.title(),
            "viewport": self.page.viewport_size
        }
    
    def wait_for_page_ready(self, timeout: int = 30000) -> bool:
        """
        Ensure page is fully loaded.
        
        Args:
            timeout: Maximum wait time in milliseconds
        
        Returns:
            True if page is ready, False otherwise
        """
        if self.page is None:
            return False
        
        try:
            self.page.wait_for_load_state("networkidle", timeout=timeout)
            return True
        except Exception as e:
            print(f"Page ready timeout: {e}")
            return False
    
    def close(self):
        """Clean up browser resources."""
        if self.page:
            try:
                self.page.close()
            except Exception:
                pass
            self.page = None
        
        if self.browser:
            try:
                self.browser.close()
            except Exception:
                pass
            self.browser = None
        
        if self.playwright:
            try:
                self.playwright.stop()
            except Exception:
                pass
            self.playwright = None
    
    def __enter__(self):
        """Context manager entry: start browser."""
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit: clean up browser."""
        self.close()
        return False


def load_fixture_page(browser_manager: BrowserManager, fixture_path: str) -> bool:
    """
    Load HTML from fixtures/sites/ directory.
    
    Args:
        browser_manager: BrowserManager instance
        fixture_path: Relative path to fixture file (e.g., 'test.html')
    
    Returns:
        True if loaded successfully, False otherwise
    """
    import os
    
    # Assume fixtures are in accessibility_auditor/server/fixtures/sites/
    base_dir = os.path.dirname(os.path.abspath(__file__))
    full_path = os.path.join(base_dir, "fixtures", "sites", fixture_path)
    
    if not os.path.exists(full_path):
        print(f"Fixture not found: {full_path}")
        return False
    
    file_url = f"file://{full_path}"
    return browser_manager.navigate_to_url(file_url)
