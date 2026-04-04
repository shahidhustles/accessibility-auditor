"""Wrapper for axe-core accessibility testing via axe-playwright-python."""

from typing import Dict, Any, List, Optional
from playwright.sync_api import Page
from axe_playwright_python.sync_playwright import Axe


class AxeRunner:
    """Wrapper for axe-core accessibility testing via axe-playwright-python."""
    
    def __init__(self):
        """Initialize the AxeRunner with an Axe instance."""
        self.axe = Axe()
    
    def run_full_scan(self, page: Page) -> Dict[str, Any]:
        """
        Run complete axe-core scan on the page.
        
        Args:
            page: Playwright Page object
            
        Returns:
            Dict with violations_count, violations, passes, incomplete, inapplicable
        """
        try:
            results = self.axe.run(page)
            return self._parse_results(results)
        except Exception as e:
            raise RuntimeError(f"Axe scan failed: {str(e)}")
    
    def run_wcag_a_scan(self, page: Page) -> Dict[str, Any]:
        """
        Run scan for WCAG Level A violations only.
        
        Args:
            page: Playwright Page object
            
        Returns:
            Dict with filtered WCAG Level A violations
        """
        try:
            results = self.axe.run(page)
            parsed = self._parse_results(results)
            
            # Filter violations by WCAG Level A tags
            wcag_a_violations = [
                v for v in parsed["violations"]
                if any(tag in v.get("tags", []) for tag in ["wcag2a", "wcag21a", "wcag22a"])
            ]
            
            return {
                "violations_count": len(wcag_a_violations),
                "violations": wcag_a_violations,
                "passes": parsed["passes"],
                "incomplete": parsed["incomplete"],
                "inapplicable": parsed["inapplicable"]
            }
        except Exception as e:
            raise RuntimeError(f"WCAG A scan failed: {str(e)}")
    
    def run_wcag_aa_scan(self, page: Page) -> Dict[str, Any]:
        """
        Run scan for WCAG Level AA violations.
        
        Args:
            page: Playwright Page object
            
        Returns:
            Dict with filtered WCAG Level AA violations
        """
        try:
            results = self.axe.run(page)
            parsed = self._parse_results(results)
            
            # Filter violations by WCAG Level AA tags
            wcag_aa_violations = [
                v for v in parsed["violations"]
                if any(tag in v.get("tags", []) for tag in ["wcag2aa", "wcag21aa", "wcag22aa"])
            ]
            
            return {
                "violations_count": len(wcag_aa_violations),
                "violations": wcag_aa_violations,
                "passes": parsed["passes"],
                "incomplete": parsed["incomplete"],
                "inapplicable": parsed["inapplicable"]
            }
        except Exception as e:
            raise RuntimeError(f"WCAG AA scan failed: {str(e)}")
    
    def _parse_results(self, results) -> Dict[str, Any]:
        """
        Parse AxeResults into structured format.
        
        Args:
            results: AxeResults object from axe.run()
            
        Returns:
            Dict with violations_count, violations, passes, incomplete, inapplicable
        """
        response = results.response
        
        return {
            "violations_count": results.violations_count,
            "violations": response.get("violations", []),
            "passes": len(response.get("passes", [])),
            "incomplete": len(response.get("incomplete", [])),
            "inapplicable": len(response.get("inapplicable", []))
        }
    
    def format_violation(self, violation: dict) -> Dict[str, Any]:
        """
        Format single axe violation to match ViolationDetail model.
        
        Args:
            violation: Single violation dict from axe-core results
            
        Returns:
            Formatted violation dict
        """
        nodes = violation.get("nodes", [])
        first_node = nodes[0] if nodes else {}
        
        return {
            "violation_id": violation.get("id", "unknown"),
            "impact": violation.get("impact", "unknown"),
            "description": violation.get("description", ""),
            "help_url": violation.get("helpUrl", ""),
            "element_html": (first_node.get("html", "")[:200] if first_node else ""),
            "failure_summary": (first_node.get("failureSummary", "")[:200] if first_node else "")
        }
    
    def filter_by_impact(
        self, 
        violations: List[Dict[str, Any]], 
        min_impact: str
    ) -> List[Dict[str, Any]]:
        """
        Filter violations by minimum impact level.
        
        Args:
            violations: List of violation dicts
            min_impact: Minimum impact level (minor/moderate/serious/critical)
            
        Returns:
            Filtered list of violations
        """
        impact_levels = {
            "minor": 0,
            "moderate": 1,
            "serious": 2,
            "critical": 3
        }
        
        min_level = impact_levels.get(min_impact.lower(), 0)
        
        return [
            v for v in violations
            if impact_levels.get(v.get("impact", "").lower(), 0) >= min_level
        ]
    
    def group_by_wcag_level(
        self, 
        violations: List[Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Group violations by WCAG level (A, AA, AAA).
        
        Args:
            violations: List of violation dicts
            
        Returns:
            Dict with keys 'A', 'AA', 'AAA' containing grouped violations
        """
        grouped = {
            "A": [],
            "AA": [],
            "AAA": []
        }
        
        for violation in violations:
            tags = violation.get("tags", [])
            
            # Check WCAG levels (A < AA < AAA, so assign to highest level)
            if any("wcag2aaa" in tag or "wcag21aaa" in tag or "wcag22aaa" in tag for tag in tags):
                grouped["AAA"].append(violation)
            elif any("wcag2aa" in tag or "wcag21aa" in tag or "wcag22aa" in tag for tag in tags):
                grouped["AA"].append(violation)
            elif any("wcag2a" in tag or "wcag21a" in tag or "wcag22a" in tag for tag in tags):
                grouped["A"].append(violation)
        
        return grouped
    
    def get_unique_violation_types(
        self, 
        violations: List[Dict[str, Any]]
    ) -> List[str]:
        """
        Get unique violation IDs from a list of violations.
        
        Args:
            violations: List of violation dicts
            
        Returns:
            List of unique violation IDs
        """
        return list(set(v.get("id", "") for v in violations if v.get("id")))
