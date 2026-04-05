# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""
Accessibility Auditor Environment Implementation.

Web accessibility testing environment using Playwright and axe-core.
Agents learn to systematically audit websites for WCAG violations.
"""

import os
import random
from datetime import datetime
from typing import Dict, List, Any, Optional

from openenv.core.env_server import Environment

try:
    from ..models import (
        AccessibilityAction,
        AccessibilityObservation,
        AccessibilityState,
        ViolationDetail,
        PageMetadata,
    )
    from .browser_manager import BrowserManager
    from .axe_runner import AxeRunner
    from . import test_runners
except ImportError:
    from models import (
        AccessibilityAction,
        AccessibilityObservation,
        AccessibilityState,
        ViolationDetail,
        PageMetadata,
    )
    from browser_manager import BrowserManager
    from axe_runner import AxeRunner
    import test_runners


class AccessibilityEnvironment(Environment):
    """
    Web accessibility testing environment.
    
    Agents learn to audit websites by executing accessibility tests
    and receiving rewards for finding WCAG violations.
    """

    SUPPORTS_CONCURRENT_SESSIONS = True
    MAX_STEPS = 20

    def __init__(self):
        """Initialize the accessibility environment."""
        super().__init__()
        self.browser_manager = BrowserManager()
        self.axe_runner = AxeRunner()
        self._current_state: Optional[AccessibilityState] = None
        self._episode_step = 0
        self._tests_completed: List[str] = []
        self._ground_truth_violations: List[Dict[str, Any]] = []
        self._found_violations: List[Dict[str, Any]] = []

    def reset(self) -> AccessibilityObservation:
        """
        Start new episode with random difficulty and fixture.
        
        Returns:
            AccessibilityObservation with initial page state
        """
        # Clean up previous episode
        try:
            self.browser_manager.close()
        except Exception:
            pass
        
        # Choose random difficulty and fixture
        difficulty = random.choice(["easy", "medium", "hard"])
        fixtures = self._list_fixtures(difficulty)
        
        if not fixtures:
            raise RuntimeError(f"No fixtures found for difficulty: {difficulty}")
        
        fixture_name = random.choice(fixtures)
        
        # Start browser and load fixture
        self.browser_manager.start()
        fixture_path = self._get_fixture_path(difficulty, fixture_name)
        
        success = self.browser_manager.navigate_to_url(fixture_path)
        if not success:
            raise RuntimeError(f"Failed to load fixture: {fixture_path}")
        
        # Wait for page to be ready
        self.browser_manager.wait_for_page_ready()
        
        # Get ground truth violations
        self._ground_truth_violations = self._get_ground_truth_violations()
        
        # Initialize state
        self._episode_step = 0
        self._tests_completed = []
        self._found_violations = []
        
        self._current_state = AccessibilityState(
            target_url=fixture_path,
            task_difficulty=difficulty,
            known_violations=[self._format_violation(v) for v in self._ground_truth_violations],
            tests_completed=[],
            episode_step=0,
        )
        
        # Create initial observation
        return self._create_observation(
            violations_found=[],
            last_action_error=None
        )

    def step(self, action: AccessibilityAction) -> AccessibilityObservation:
        """
        Execute accessibility test action.
        
        Args:
            action: AccessibilityAction with test_type, selector, parameters
            
        Returns:
            AccessibilityObservation with results
        """
        if self._current_state is None:
            raise RuntimeError("Environment not initialized. Call reset() first.")
        
        self._episode_step += 1
        self._current_state.episode_step = self._episode_step
        
        # Parse action - handle both dict and AccessibilityAction
        if isinstance(action, dict):
            test_type = action.get("test_type", "")
            selector = action.get("selector")
            parameters = action.get("parameters", {})
        else:
            test_type = action.test_type
            selector = action.selector
            parameters = action.parameters or {}
        
        # Execute test
        violations_found = []
        error_message = None
        
        try:
            violations_found = self._execute_test(test_type, selector, parameters)
            
            # Track test completion
            if test_type not in self._tests_completed:
                self._tests_completed.append(test_type)
                self._current_state.tests_completed = self._tests_completed.copy()
            
            # Store found violations
            self._found_violations.extend(violations_found)
            
        except Exception as e:
            error_message = str(e)
            violations_found = []
        
        # Calculate reward
        reward = self._calculate_reward(violations_found, test_type)
        
        # Check if done
        done = (
            self._episode_step >= self.MAX_STEPS 
            or test_type == "complete_audit"
        )
        
        # Build info dict for metadata
        info = {
            "test_type": test_type,
            "violations_count": len(violations_found),
            "total_violations_found": len(self._found_violations),
            "ground_truth_count": len(self._ground_truth_violations),
        }
        
        # Create observation with reward, done, and metadata
        observation = self._create_observation(
            violations_found=violations_found,
            last_action_error=error_message,
            reward=reward,
            done=done,
            metadata=info
        )
        
        return observation

    @property
    def state(self) -> dict:
        """
        Return current environment state.
        
        Returns:
            State dict
        """
        if self._current_state is None:
            return {}
        return self._current_state.model_dump()

    def _execute_test(
        self, 
        test_type: str, 
        selector: Optional[str], 
        parameters: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Execute test based on test_type.
        
        Args:
            test_type: Type of test to run
            selector: CSS selector (if applicable)
            parameters: Additional test parameters
            
        Returns:
            List of violation dicts
        """
        if self.browser_manager.page is None:
            raise RuntimeError("No page loaded")
        
        page = self.browser_manager.page
        
        # Axe-core scans
        if test_type == "run_axe":
            results = self.axe_runner.run_full_scan(page)
            return results.get("violations", [])
        
        elif test_type == "run_axe_wcag_a":
            results = self.axe_runner.run_wcag_a_scan(page)
            return results.get("violations", [])
        
        elif test_type == "run_axe_wcag_aa":
            results = self.axe_runner.run_wcag_aa_scan(page)
            return results.get("violations", [])
        
        # Specific test runners
        elif test_type == "test_image_alt":
            result = test_runners.test_image_alt_text(page)
            return result.violations
        
        elif test_type == "test_form_labels":
            result = test_runners.test_form_labels(page)
            return result.violations
        
        elif test_type == "test_color_contrast":
            result = test_runners.test_color_contrast(page)
            return result.violations
        
        elif test_type == "test_keyboard_nav":
            result = test_runners.test_keyboard_navigation(page)
            return result.violations
        
        elif test_type == "test_aria_labels":
            result = test_runners.test_aria_labels(page)
            return result.violations
        
        elif test_type == "test_heading_structure":
            result = test_runners.test_heading_structure(page)
            return result.violations
        
        elif test_type == "test_landmark_roles":
            result = test_runners.test_landmark_roles(page)
            return result.violations
        
        elif test_type == "test_focus_indicators":
            result = test_runners.test_focus_indicators(page)
            return result.violations
        
        elif test_type == "test_skip_links":
            result = test_runners.test_skip_links(page)
            return result.violations
        
        elif test_type == "test_language_attrs":
            result = test_runners.test_language_attributes(page)
            return result.violations
        
        elif test_type == "test_table_headers":
            result = test_runners.test_table_headers(page)
            return result.violations
        
        elif test_type == "test_video_captions":
            result = test_runners.test_video_captions(page)
            return result.violations
        
        elif test_type == "complete_audit":
            # Agent signals audit is complete
            return []
        
        else:
            raise ValueError(f"Unknown test_type: {test_type}")

    def _calculate_reward(
        self, 
        found_violations: List[Dict[str, Any]], 
        test_type: str
    ) -> float:
        """
        Calculate reward using 6-signal reward function.
        
        Signals:
        1. Violation discovery (+0.5 per critical/serious)
        2. Coverage bonus (+0.2 per test type completed)
        3. False positive penalty (-0.3 per FP)
        4. Severity weighting (critical=4x, serious=3x, moderate=2x, minor=1x)
        5. Efficiency bonus (find more in fewer steps)
        6. Episode completion (+1.0 for high coverage)
        
        Args:
            found_violations: Violations found in this step
            test_type: Type of test executed
            
        Returns:
            Reward value (typically -5.0 to +10.0 range)
        """
        reward = 0.0
        
        # Signal 1: Violation discovery
        for violation in found_violations:
            impact = violation.get("impact", "minor").lower()
            
            # Signal 4: Severity weighting
            severity_multiplier = {
                "critical": 4.0,
                "serious": 3.0,
                "moderate": 2.0,
                "minor": 1.0,
            }.get(impact, 1.0)
            
            # Check if this is a true positive (matches ground truth)
            is_true_positive = self._is_true_positive(violation)
            
            if is_true_positive:
                base_reward = 0.5 if impact in ["critical", "serious"] else 0.3
                reward += base_reward * severity_multiplier
            else:
                # Signal 3: False positive penalty
                reward -= 0.3
        
        # Signal 2: Coverage bonus (first time completing this test type)
        if test_type not in self._tests_completed[:-1] if test_type in self._tests_completed else True:
            reward += 0.2
        
        # Signal 5: Efficiency bonus (finding violations early)
        if len(found_violations) > 0 and self._episode_step <= 10:
            efficiency_bonus = 0.1 * (11 - self._episode_step) / 10
            reward += efficiency_bonus
        
        # Signal 6: Episode completion bonus
        if test_type == "complete_audit":
            coverage_ratio = len(self._tests_completed) / 12.0  # 12 test types available
            if coverage_ratio >= 0.7:
                reward += 1.0
            elif coverage_ratio >= 0.5:
                reward += 0.5
        
        return reward

    def _is_true_positive(self, violation: Dict[str, Any]) -> bool:
        """
        Check if violation matches ground truth.
        
        Args:
            violation: Violation to check
            
        Returns:
            True if matches ground truth, False otherwise
        """
        violation_id = violation.get("id") or violation.get("violation_id", "")
        
        # Simple matching: check if violation_id exists in ground truth
        for gt_violation in self._ground_truth_violations:
            gt_id = gt_violation.get("id") or gt_violation.get("violation_id", "")
            if gt_id == violation_id:
                return True
        
        return False

    def _create_observation(
        self,
        violations_found: List[Dict[str, Any]],
        last_action_error: Optional[str],
        reward: float = 0.0,
        done: bool = False,
        metadata: Optional[Dict[str, Any]] = None
    ) -> AccessibilityObservation:
        """
        Build observation from current page state.
        
        Args:
            violations_found: Violations from last action
            last_action_error: Error message if action failed
            reward: Reward value for this step
            done: Whether episode is complete
            metadata: Additional metadata dict
            
        Returns:
            AccessibilityObservation object
        """
        try:
            # Get page metadata
            page_meta = self.browser_manager.get_page_metadata()
            page_metadata = PageMetadata(
                url=page_meta["url"],
                title=page_meta["title"],
                viewport_size=page_meta["viewport"],
                timestamp=datetime.utcnow().isoformat(),
            )
            
            # Get DOM summary
            dom_summary = self.browser_manager.get_dom_summary()
            
            # Format violations
            formatted_violations = [
                self._format_violation(v) for v in violations_found
            ]
            
            # Calculate coverage metrics
            coverage_metrics = self._calculate_coverage()
            
            # Create observation
            observation = AccessibilityObservation(
                page_metadata=page_metadata,
                screenshot=None,  # Screenshot optional for performance
                dom_summary=dom_summary,
                violations_found=formatted_violations,
                coverage_metrics=coverage_metrics,
                last_action_error=last_action_error,
                reward=reward,
                done=done,
                metadata=metadata or {},
            )
            
            return observation
            
        except Exception as e:
            # Fallback minimal observation
            fallback_page_metadata = PageMetadata(
                url=self._current_state.target_url if self._current_state else "",
                title="Error",
                viewport_size={"width": 1280, "height": 720},
                timestamp=datetime.utcnow().isoformat(),
            )
            return AccessibilityObservation(
                page_metadata=fallback_page_metadata,
                screenshot=None,
                dom_summary="",
                violations_found=[],
                coverage_metrics={},
                last_action_error=f"Observation creation failed: {str(e)}",
                reward=reward,
                done=done,
                metadata=metadata or {},
            )

    def _format_violation(self, violation: Dict[str, Any]) -> ViolationDetail:
        """
        Format violation dict to ViolationDetail model.
        
        Args:
            violation: Violation dict from axe or test runner
            
        Returns:
            ViolationDetail object
        """
        # Handle axe-core format
        if "nodes" in violation:
            nodes = violation.get("nodes", [])
            first_node = nodes[0] if nodes else {}
            element_html = first_node.get("html", "")[:200]
            failure_summary = first_node.get("failureSummary", "")[:200]
        else:
            # Handle test_runner format
            element_html = violation.get("element_html", "")[:200]
            failure_summary = violation.get("failure_summary", "")[:200]
        
        return ViolationDetail(
            violation_id=violation.get("id") or violation.get("violation_id", "unknown"),
            impact=violation.get("impact", "unknown"),
            description=violation.get("description", ""),
            help_url=violation.get("helpUrl") or violation.get("help_url", ""),
            element_html=element_html,
            failure_summary=failure_summary,
        )

    def _calculate_coverage(self) -> Dict[str, float]:
        """
        Calculate test coverage metrics.
        
        Returns:
            Dict mapping test names to coverage (0.0-1.0)
        """
        all_tests = [
            "run_axe", "run_axe_wcag_a", "run_axe_wcag_aa",
            "test_image_alt", "test_form_labels", "test_color_contrast",
            "test_keyboard_nav", "test_aria_labels", "test_heading_structure",
            "test_landmark_roles", "test_focus_indicators", "test_skip_links",
            "test_language_attrs", "test_table_headers", "test_video_captions",
        ]
        
        coverage = {}
        for test in all_tests:
            coverage[test] = 1.0 if test in self._tests_completed else 0.0
        
        return coverage

    def _get_fixture_path(self, difficulty: str, fixture_name: str) -> str:
        """
        Build file:// URL for fixture.
        
        Args:
            difficulty: easy, medium, or hard
            fixture_name: HTML filename
            
        Returns:
            file:// URL
        """
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        fixture_path = os.path.join(
            base_dir, "fixtures", "sites", difficulty, fixture_name
        )
        return f"file://{fixture_path}"

    def _list_fixtures(self, difficulty: str) -> List[str]:
        """
        List available fixtures for difficulty level.
        
        Args:
            difficulty: easy, medium, or hard
            
        Returns:
            List of fixture filenames
        """
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        fixtures_dir = os.path.join(base_dir, "fixtures", "sites", difficulty)
        
        if not os.path.exists(fixtures_dir):
            return []
        
        return [
            f for f in os.listdir(fixtures_dir) 
            if f.endswith(".html")
        ]

    def _get_ground_truth_violations(self) -> List[Dict[str, Any]]:
        """
        Run full axe scan to get ground truth violations.
        
        Returns:
            List of ground truth violation dicts
        """
        try:
            if self.browser_manager.page is None:
                return []
            
            results = self.axe_runner.run_full_scan(self.browser_manager.page)
            return results.get("violations", [])
        except Exception as e:
            print(f"Warning: Could not get ground truth violations: {e}")
            return []

    def close(self):
        """Clean up browser resources."""
        try:
            self.browser_manager.close()
        except Exception:
            pass

    def __del__(self):
        """Cleanup on deletion."""
        self.close()
