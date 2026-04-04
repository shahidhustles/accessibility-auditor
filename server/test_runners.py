"""
Accessibility Test Runners for WCAG Compliance Checks.

This module provides 12 test runner functions that evaluate web pages
for accessibility compliance using Playwright's page object.
"""

from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from playwright.sync_api import Page, ElementHandle
import math


@dataclass
class TestResult:
    """Result of an accessibility test."""
    test_name: str
    passed: bool
    violations: List[Dict[str, Any]]
    details: Optional[str] = None


# Helper Functions

def get_computed_style(element: ElementHandle, property: str) -> str:
    """Get computed CSS property value for an element."""
    try:
        return element.evaluate(
            f"(el) => window.getComputedStyle(el).getPropertyValue('{property}')"
        )
    except Exception:
        return ""


def parse_color_to_rgb(color_str: str) -> Optional[tuple]:
    """Parse CSS color string to RGB tuple."""
    if not color_str:
        return None
    
    try:
        # Handle rgb(r, g, b) format
        if color_str.startswith("rgb("):
            values = color_str[4:-1].split(",")
            return tuple(int(v.strip()) for v in values[:3])
        
        # Handle rgba(r, g, b, a) format
        if color_str.startswith("rgba("):
            values = color_str[5:-1].split(",")
            return tuple(int(v.strip()) for v in values[:3])
        
        return None
    except (ValueError, IndexError):
        return None


def calculate_luminance(rgb: tuple) -> float:
    """Calculate relative luminance of an RGB color."""
    r, g, b = rgb
    
    # Convert to 0-1 range
    r, g, b = r / 255.0, g / 255.0, b / 255.0
    
    # Apply gamma correction
    def gamma(channel):
        if channel <= 0.03928:
            return channel / 12.92
        return ((channel + 0.055) / 1.055) ** 2.4
    
    r, g, b = gamma(r), gamma(g), gamma(b)
    
    # Calculate luminance
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def check_contrast_ratio(fg_color: str, bg_color: str) -> Optional[float]:
    """
    Calculate contrast ratio between foreground and background colors.
    Returns None if colors cannot be parsed.
    """
    fg_rgb = parse_color_to_rgb(fg_color)
    bg_rgb = parse_color_to_rgb(bg_color)
    
    if not fg_rgb or not bg_rgb:
        return None
    
    fg_lum = calculate_luminance(fg_rgb)
    bg_lum = calculate_luminance(bg_rgb)
    
    # Ensure lighter color is in numerator
    lighter = max(fg_lum, bg_lum)
    darker = min(fg_lum, bg_lum)
    
    ratio = (lighter + 0.05) / (darker + 0.05)
    return ratio


def is_focusable(element: ElementHandle) -> bool:
    """Check if an element can receive keyboard focus."""
    try:
        result = element.evaluate("""
            (el) => {
                // Check if element is focusable
                const tabindex = el.getAttribute('tabindex');
                if (tabindex && parseInt(tabindex) < 0) return false;
                
                const focusableTags = ['A', 'BUTTON', 'INPUT', 'SELECT', 'TEXTAREA'];
                if (focusableTags.includes(el.tagName)) return true;
                
                if (tabindex !== null) return true;
                
                return false;
            }
        """)
        return result
    except Exception:
        return False


# Test Runner Functions

def test_image_alt_text(page: Page) -> TestResult:
    """Test that all images have alt text."""
    violations = []
    
    try:
        images = page.locator("img").all()
        
        for idx, img in enumerate(images):
            try:
                alt = img.get_attribute("alt")
                if alt is None:
                    html = img.evaluate("(el) => el.outerHTML")
                    violations.append({
                        "violation_id": "image-alt",
                        "impact": "critical",
                        "description": "Image missing alt attribute",
                        "element_html": html[:200],
                        "failure_summary": "Alt attribute not present on image element"
                    })
            except Exception as e:
                violations.append({
                    "violation_id": "image-alt-error",
                    "impact": "serious",
                    "description": f"Error checking image: {str(e)}",
                    "element_html": f"Image index {idx}",
                    "failure_summary": str(e)
                })
    except Exception as e:
        violations.append({
            "violation_id": "test-error",
            "impact": "serious",
            "description": f"Error running image alt test: {str(e)}",
            "element_html": "",
            "failure_summary": str(e)
        })
    
    return TestResult(
        test_name="image_alt_text",
        passed=len(violations) == 0,
        violations=violations,
        details=f"Checked {len(page.locator('img').all()) if violations != [{'violation_id': 'test-error', 'impact': 'serious', 'description': f'Error running image alt test: {str(e)}', 'element_html': '', 'failure_summary': str(e)}] else 0} images"
    )


def test_form_labels(page: Page) -> TestResult:
    """Verify all form inputs have associated labels."""
    violations = []
    
    try:
        # Check inputs, selects, and textareas
        form_elements = page.locator("input:not([type='hidden']), select, textarea").all()
        
        for elem in form_elements:
            try:
                # Check for explicit label association
                elem_id = elem.get_attribute("id")
                aria_label = elem.get_attribute("aria-label")
                aria_labelledby = elem.get_attribute("aria-labelledby")
                
                has_label = False
                
                # Check for aria-label
                if aria_label:
                    has_label = True
                
                # Check for aria-labelledby
                if aria_labelledby:
                    has_label = True
                
                # Check for associated label element
                if elem_id:
                    labels = page.locator(f"label[for='{elem_id}']").all()
                    if labels:
                        has_label = True
                
                # Check if wrapped in label
                parent_is_label = elem.evaluate("""
                    (el) => {
                        let parent = el.parentElement;
                        while (parent) {
                            if (parent.tagName === 'LABEL') return true;
                            parent = parent.parentElement;
                        }
                        return false;
                    }
                """)
                
                if parent_is_label:
                    has_label = True
                
                if not has_label:
                    html = elem.evaluate("(el) => el.outerHTML")
                    violations.append({
                        "violation_id": "form-label",
                        "impact": "critical",
                        "description": "Form element missing accessible label",
                        "element_html": html[:200],
                        "failure_summary": "No label, aria-label, or aria-labelledby found"
                    })
            except Exception:
                pass
    except Exception as e:
        violations.append({
            "violation_id": "test-error",
            "impact": "serious",
            "description": f"Error running form labels test: {str(e)}",
            "element_html": "",
            "failure_summary": str(e)
        })
    
    return TestResult(
        test_name="form_labels",
        passed=len(violations) == 0,
        violations=violations
    )


def test_color_contrast(page: Page) -> TestResult:
    """Check color contrast ratios for text elements."""
    violations = []
    
    try:
        # Check text elements for contrast
        text_elements = page.locator("p, span, div, a, button, h1, h2, h3, h4, h5, h6, li, td, th").all()
        
        checked = 0
        for elem in text_elements[:50]:  # Limit to first 50 for performance
            try:
                # Get text content
                text = elem.inner_text().strip()
                if not text or len(text) < 3:
                    continue
                
                # Get computed styles
                color = get_computed_style(elem, "color")
                bg_color = get_computed_style(elem, "background-color")
                font_size = get_computed_style(elem, "font-size")
                
                # Parse font size
                try:
                    font_size_px = float(font_size.replace("px", ""))
                except (ValueError, AttributeError):
                    font_size_px = 16
                
                # Calculate contrast ratio
                ratio = check_contrast_ratio(color, bg_color)
                
                if ratio:
                    checked += 1
                    # WCAG AA requires 4.5:1 for normal text, 3:1 for large text (18pt+)
                    required_ratio = 3.0 if font_size_px >= 24 else 4.5
                    
                    if ratio < required_ratio:
                        html = elem.evaluate("(el) => el.outerHTML")
                        violations.append({
                            "violation_id": "color-contrast",
                            "impact": "serious",
                            "description": f"Insufficient color contrast ratio: {ratio:.2f}:1 (required: {required_ratio}:1)",
                            "element_html": html[:200],
                            "failure_summary": f"Contrast ratio {ratio:.2f}:1 is below WCAG AA threshold"
                        })
            except Exception:
                pass
        
    except Exception as e:
        violations.append({
            "violation_id": "test-error",
            "impact": "serious",
            "description": f"Error running color contrast test: {str(e)}",
            "element_html": "",
            "failure_summary": str(e)
        })
    
    return TestResult(
        test_name="color_contrast",
        passed=len(violations) == 0,
        violations=violations,
        details=f"Checked {checked} text elements"
    )


def test_keyboard_navigation(page: Page) -> TestResult:
    """Check that focusable elements are keyboard accessible."""
    violations = []
    
    try:
        # Find all interactive elements
        interactive_selectors = [
            "a[href]", "button", "input:not([type='hidden'])", 
            "select", "textarea", "[tabindex]", "[role='button']", "[role='link']"
        ]
        
        for selector in interactive_selectors:
            elements = page.locator(selector).all()
            
            for elem in elements:
                try:
                    # Check if element has negative tabindex
                    tabindex = elem.get_attribute("tabindex")
                    if tabindex and int(tabindex) < 0:
                        continue
                    
                    # Check if element is visible
                    is_visible = elem.is_visible()
                    if not is_visible:
                        continue
                    
                    # Check if element is disabled
                    is_disabled = elem.is_disabled() if selector in ["button", "input", "select", "textarea"] else False
                    if is_disabled:
                        continue
                    
                    # Check if focusable
                    if not is_focusable(elem):
                        html = elem.evaluate("(el) => el.outerHTML")
                        violations.append({
                            "violation_id": "keyboard-navigation",
                            "impact": "serious",
                            "description": "Interactive element not keyboard accessible",
                            "element_html": html[:200],
                            "failure_summary": "Element cannot receive keyboard focus"
                        })
                except Exception:
                    pass
    except Exception as e:
        violations.append({
            "violation_id": "test-error",
            "impact": "serious",
            "description": f"Error running keyboard navigation test: {str(e)}",
            "element_html": "",
            "failure_summary": str(e)
        })
    
    return TestResult(
        test_name="keyboard_navigation",
        passed=len(violations) == 0,
        violations=violations
    )


def test_aria_labels(page: Page) -> TestResult:
    """Validate ARIA attributes on interactive elements."""
    violations = []
    
    try:
        # Find elements with ARIA attributes
        aria_elements = page.locator("[role], [aria-label], [aria-labelledby], [aria-describedby]").all()
        
        for elem in aria_elements:
            try:
                role = elem.get_attribute("role")
                aria_label = elem.get_attribute("aria-label")
                aria_labelledby = elem.get_attribute("aria-labelledby")
                
                # Check if role is valid
                valid_roles = [
                    "button", "link", "navigation", "main", "banner", "contentinfo",
                    "complementary", "search", "form", "region", "article", "section",
                    "alert", "dialog", "menu", "menuitem", "tab", "tabpanel", "list",
                    "listitem", "checkbox", "radio", "textbox", "img", "heading"
                ]
                
                if role and role not in valid_roles:
                    html = elem.evaluate("(el) => el.outerHTML")
                    violations.append({
                        "violation_id": "aria-invalid-role",
                        "impact": "serious",
                        "description": f"Invalid ARIA role: {role}",
                        "element_html": html[:200],
                        "failure_summary": f"Role '{role}' is not a valid ARIA role"
                    })
                
                # Check if aria-labelledby references exist
                if aria_labelledby:
                    label_ids = aria_labelledby.split()
                    for label_id in label_ids:
                        referenced = page.locator(f"#{label_id}").count()
                        if referenced == 0:
                            html = elem.evaluate("(el) => el.outerHTML")
                            violations.append({
                                "violation_id": "aria-labelledby-missing",
                                "impact": "serious",
                                "description": f"aria-labelledby references non-existent ID: {label_id}",
                                "element_html": html[:200],
                                "failure_summary": f"Referenced element #{label_id} does not exist"
                            })
                
                # Check if interactive elements with roles have labels
                if role in ["button", "link"] and not aria_label and not aria_labelledby:
                    text_content = elem.inner_text().strip()
                    if not text_content:
                        html = elem.evaluate("(el) => el.outerHTML")
                        violations.append({
                            "violation_id": "aria-missing-label",
                            "impact": "serious",
                            "description": f"Element with role '{role}' has no accessible name",
                            "element_html": html[:200],
                            "failure_summary": "No aria-label, aria-labelledby, or text content"
                        })
            except Exception:
                pass
    except Exception as e:
        violations.append({
            "violation_id": "test-error",
            "impact": "serious",
            "description": f"Error running ARIA labels test: {str(e)}",
            "element_html": "",
            "failure_summary": str(e)
        })
    
    return TestResult(
        test_name="aria_labels",
        passed=len(violations) == 0,
        violations=violations
    )


def test_heading_structure(page: Page) -> TestResult:
    """Check heading hierarchy (h1→h2→h3, etc.)."""
    violations = []
    
    try:
        # Get all headings in document order
        headings_data = page.evaluate("""
            () => {
                const headings = Array.from(document.querySelectorAll('h1, h2, h3, h4, h5, h6'));
                return headings.map(h => ({
                    level: parseInt(h.tagName.substring(1)),
                    text: h.textContent.trim().substring(0, 50),
                    html: h.outerHTML.substring(0, 200)
                }));
            }
        """)
        
        if not headings_data:
            return TestResult(
                test_name="heading_structure",
                passed=True,
                violations=[],
                details="No headings found on page"
            )
        
        # Check for h1
        h1_count = sum(1 for h in headings_data if h['level'] == 1)
        if h1_count == 0:
            violations.append({
                "violation_id": "heading-missing-h1",
                "impact": "moderate",
                "description": "Page has no h1 heading",
                "element_html": "",
                "failure_summary": "Every page should have exactly one h1 heading"
            })
        elif h1_count > 1:
            violations.append({
                "violation_id": "heading-multiple-h1",
                "impact": "moderate",
                "description": f"Page has {h1_count} h1 headings",
                "element_html": "",
                "failure_summary": "Page should have only one h1 heading"
            })
        
        # Check hierarchy
        prev_level = 0
        for heading in headings_data:
            level = heading['level']
            
            # Check if heading skips levels
            if level > prev_level + 1:
                violations.append({
                    "violation_id": "heading-skip-level",
                    "impact": "moderate",
                    "description": f"Heading skips from h{prev_level} to h{level}",
                    "element_html": heading['html'],
                    "failure_summary": f"Heading levels should not be skipped (h{prev_level} → h{level})"
                })
            
            prev_level = level
        
    except Exception as e:
        violations.append({
            "violation_id": "test-error",
            "impact": "serious",
            "description": f"Error running heading structure test: {str(e)}",
            "element_html": "",
            "failure_summary": str(e)
        })
    
    return TestResult(
        test_name="heading_structure",
        passed=len(violations) == 0,
        violations=violations
    )


def test_landmark_roles(page: Page) -> TestResult:
    """Verify semantic HTML5 landmarks (nav, main, etc.)."""
    violations = []
    
    try:
        # Check for essential landmarks
        landmarks_check = page.evaluate("""
            () => {
                const main = document.querySelector('main, [role="main"]');
                const nav = document.querySelector('nav, [role="navigation"]');
                const banner = document.querySelector('header, [role="banner"]');
                
                return {
                    hasMain: !!main,
                    hasNav: !!nav,
                    hasBanner: !!banner,
                    mainCount: document.querySelectorAll('main, [role="main"]').length
                };
            }
        """)
        
        if not landmarks_check['hasMain']:
            violations.append({
                "violation_id": "landmark-missing-main",
                "impact": "moderate",
                "description": "Page missing main landmark",
                "element_html": "",
                "failure_summary": "Page should have a <main> element or role='main'"
            })
        
        if landmarks_check['mainCount'] > 1:
            violations.append({
                "violation_id": "landmark-multiple-main",
                "impact": "moderate",
                "description": f"Page has {landmarks_check['mainCount']} main landmarks",
                "element_html": "",
                "failure_summary": "Page should have only one main landmark"
            })
        
        if not landmarks_check['hasNav']:
            violations.append({
                "violation_id": "landmark-missing-nav",
                "impact": "minor",
                "description": "Page missing navigation landmark",
                "element_html": "",
                "failure_summary": "Page should have a <nav> element or role='navigation'"
            })
        
    except Exception as e:
        violations.append({
            "violation_id": "test-error",
            "impact": "serious",
            "description": f"Error running landmark roles test: {str(e)}",
            "element_html": "",
            "failure_summary": str(e)
        })
    
    return TestResult(
        test_name="landmark_roles",
        passed=len(violations) == 0,
        violations=violations
    )


def test_focus_indicators(page: Page) -> TestResult:
    """Check that focus styles are visible on interactive elements."""
    violations = []
    
    try:
        # Check focusable elements for outline styles
        focusable_elements = page.locator(
            "a[href], button, input:not([type='hidden']), select, textarea, [tabindex='0']"
        ).all()
        
        for elem in focusable_elements[:30]:  # Limit for performance
            try:
                if not elem.is_visible():
                    continue
                
                # Check focus styles
                focus_style = elem.evaluate("""
                    (el) => {
                        const style = window.getComputedStyle(el);
                        const outline = style.getPropertyValue('outline');
                        const outlineWidth = style.getPropertyValue('outline-width');
                        const outlineStyle = style.getPropertyValue('outline-style');
                        
                        // Check if outline is effectively disabled
                        const hasOutline = !(
                            outline === 'none' ||
                            outlineWidth === '0px' ||
                            outlineStyle === 'none'
                        );
                        
                        return {
                            hasOutline,
                            outline,
                            outlineWidth,
                            outlineStyle
                        };
                    }
                """)
                
                if not focus_style['hasOutline']:
                    html = elem.evaluate("(el) => el.outerHTML")
                    violations.append({
                        "violation_id": "focus-indicator",
                        "impact": "serious",
                        "description": "Focusable element missing visible focus indicator",
                        "element_html": html[:200],
                        "failure_summary": "Element has outline disabled or set to none"
                    })
            except Exception:
                pass
        
    except Exception as e:
        violations.append({
            "violation_id": "test-error",
            "impact": "serious",
            "description": f"Error running focus indicators test: {str(e)}",
            "element_html": "",
            "failure_summary": str(e)
        })
    
    return TestResult(
        test_name="focus_indicators",
        passed=len(violations) == 0,
        violations=violations
    )


def test_skip_links(page: Page) -> TestResult:
    """Check for skip navigation links."""
    violations = []
    
    try:
        # Check for skip links (usually first link in document)
        skip_link = page.evaluate("""
            () => {
                const links = Array.from(document.querySelectorAll('a[href^="#"]'));
                const skipLink = links.find(link => {
                    const text = link.textContent.toLowerCase();
                    return text.includes('skip') && 
                           (text.includes('content') || text.includes('main') || text.includes('navigation'));
                });
                
                return {
                    hasSkipLink: !!skipLink,
                    skipLinkHtml: skipLink ? skipLink.outerHTML : null
                };
            }
        """)
        
        if not skip_link['hasSkipLink']:
            violations.append({
                "violation_id": "skip-link-missing",
                "impact": "moderate",
                "description": "Page missing skip navigation link",
                "element_html": "",
                "failure_summary": "Page should have a 'skip to content' or 'skip to main' link"
            })
        
    except Exception as e:
        violations.append({
            "violation_id": "test-error",
            "impact": "serious",
            "description": f"Error running skip links test: {str(e)}",
            "element_html": "",
            "failure_summary": str(e)
        })
    
    return TestResult(
        test_name="skip_links",
        passed=len(violations) == 0,
        violations=violations
    )


def test_language_attributes(page: Page) -> TestResult:
    """Verify html[lang] attribute is present and valid."""
    violations = []
    
    try:
        lang_info = page.evaluate("""
            () => {
                const html = document.documentElement;
                const lang = html.getAttribute('lang');
                
                return {
                    hasLang: !!lang,
                    langValue: lang,
                    htmlTag: html.outerHTML.substring(0, 100)
                };
            }
        """)
        
        if not lang_info['hasLang']:
            violations.append({
                "violation_id": "language-missing",
                "impact": "serious",
                "description": "HTML element missing lang attribute",
                "element_html": lang_info['htmlTag'],
                "failure_summary": "The <html> element must have a lang attribute"
            })
        elif lang_info['langValue']:
            # Basic validation - check if it's a reasonable language code
            lang_value = lang_info['langValue']
            if len(lang_value) < 2 or len(lang_value) > 10:
                violations.append({
                    "violation_id": "language-invalid",
                    "impact": "serious",
                    "description": f"Invalid lang attribute value: {lang_value}",
                    "element_html": lang_info['htmlTag'],
                    "failure_summary": f"Lang value '{lang_value}' does not appear to be a valid language code"
                })
        
    except Exception as e:
        violations.append({
            "violation_id": "test-error",
            "impact": "serious",
            "description": f"Error running language attributes test: {str(e)}",
            "element_html": "",
            "failure_summary": str(e)
        })
    
    return TestResult(
        test_name="language_attributes",
        passed=len(violations) == 0,
        violations=violations
    )


def test_table_headers(page: Page) -> TestResult:
    """Check that tables have proper headers."""
    violations = []
    
    try:
        tables = page.locator("table").all()
        
        for table in tables:
            try:
                table_info = table.evaluate("""
                    (table) => {
                        const headers = table.querySelectorAll('th');
                        const caption = table.querySelector('caption');
                        const hasHeaders = headers.length > 0;
                        const hasCaption = !!caption;
                        
                        return {
                            hasHeaders,
                            hasCaption,
                            headerCount: headers.length,
                            html: table.outerHTML.substring(0, 200)
                        };
                    }
                """)
                
                if not table_info['hasHeaders']:
                    violations.append({
                        "violation_id": "table-missing-headers",
                        "impact": "serious",
                        "description": "Table missing header cells (<th>)",
                        "element_html": table_info['html'],
                        "failure_summary": "Tables must have <th> elements to identify headers"
                    })
                
                if not table_info['hasCaption']:
                    violations.append({
                        "violation_id": "table-missing-caption",
                        "impact": "moderate",
                        "description": "Table missing caption element",
                        "element_html": table_info['html'],
                        "failure_summary": "Tables should have a <caption> to describe their purpose"
                    })
            except Exception:
                pass
        
    except Exception as e:
        violations.append({
            "violation_id": "test-error",
            "impact": "serious",
            "description": f"Error running table headers test: {str(e)}",
            "element_html": "",
            "failure_summary": str(e)
        })
    
    return TestResult(
        test_name="table_headers",
        passed=len(violations) == 0,
        violations=violations,
        details=f"Checked {len(page.locator('table').all())} tables"
    )


def test_video_captions(page: Page) -> TestResult:
    """Check video elements have captions/tracks."""
    violations = []
    
    try:
        videos = page.locator("video").all()
        
        for video in videos:
            try:
                video_info = video.evaluate("""
                    (video) => {
                        const tracks = video.querySelectorAll('track[kind="captions"], track[kind="subtitles"]');
                        const hasTracks = tracks.length > 0;
                        
                        return {
                            hasTracks,
                            trackCount: tracks.length,
                            html: video.outerHTML.substring(0, 200)
                        };
                    }
                """)
                
                if not video_info['hasTracks']:
                    violations.append({
                        "violation_id": "video-no-captions",
                        "impact": "critical",
                        "description": "Video element missing captions or subtitles",
                        "element_html": video_info['html'],
                        "failure_summary": "Video must have <track> elements with kind='captions' or 'subtitles'"
                    })
            except Exception:
                pass
        
        if not videos:
            return TestResult(
                test_name="video_captions",
                passed=True,
                violations=[],
                details="No video elements found on page"
            )
        
    except Exception as e:
        violations.append({
            "violation_id": "test-error",
            "impact": "serious",
            "description": f"Error running video captions test: {str(e)}",
            "element_html": "",
            "failure_summary": str(e)
        })
    
    return TestResult(
        test_name="video_captions",
        passed=len(violations) == 0,
        violations=violations,
        details=f"Checked {len(page.locator('video').all())} videos"
    )
