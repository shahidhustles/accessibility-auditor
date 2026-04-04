# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""
Data models for the Accessibility Auditor Environment.

This environment enables web accessibility testing using Playwright and axe-core.
Agents learn to systematically audit websites for WCAG violations.
"""

from typing import Any, Dict, List, Optional

from openenv.core import Action, Observation, State
from pydantic import Field


class AccessibilityAction(Action):
    """
    Agent action for performing accessibility tests.
    
    Supports different test types like running axe-core scans, checking alt text,
    testing keyboard navigation, and more.
    """

    test_type: str = Field(
        ...,
        description=(
            "Type of accessibility test to run. Examples: 'run_axe', "
            "'check_alt_text', 'test_keyboard_nav', 'check_color_contrast', "
            "'verify_form_labels', 'test_aria_labels', 'check_heading_structure'"
        ),
    )
    selector: Optional[str] = Field(
        default=None,
        description="CSS selector for targeted tests. If None, tests run on entire page.",
    )
    parameters: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional test parameters as key-value pairs.",
    )


class ViolationDetail(Action):
    """
    Details of a single accessibility violation found during testing.
    
    Follows the axe-core violation structure for WCAG compliance reporting.
    """

    violation_id: str = Field(
        ...,
        description=(
            "Unique identifier for the violation type (e.g., 'color-contrast', "
            "'image-alt', 'label', 'button-name')"
        ),
    )
    impact: str = Field(
        ...,
        description="Severity level: 'minor', 'moderate', 'serious', or 'critical'",
    )
    description: str = Field(
        ...,
        description="Human-readable description of the accessibility issue",
    )
    help_url: str = Field(
        ...,
        description="URL to documentation explaining how to fix the violation",
    )
    element_html: str = Field(
        ...,
        description="HTML snippet of the element causing the violation",
    )
    failure_summary: str = Field(
        ...,
        description="Detailed explanation of why the element failed (e.g., 'Expected 4.5:1, found 3.5:1')",
    )


class PageMetadata(Action):
    """
    Metadata about the web page being tested.
    
    Provides context about the testing environment and page state.
    """

    url: str = Field(
        ...,
        description="Full URL of the page being audited",
    )
    title: str = Field(
        ...,
        description="HTML title of the page",
    )
    viewport_size: Dict[str, int] = Field(
        ...,
        description="Browser viewport dimensions with 'width' and 'height' keys",
    )
    timestamp: str = Field(
        ...,
        description="ISO 8601 timestamp of when the page was loaded",
    )


class AccessibilityObservation(Observation):
    """
    Observation returned after each action in the accessibility testing environment.
    
    Contains page metadata, test results, violations found, and optional screenshot data.
    """

    page_metadata: PageMetadata = Field(
        ...,
        description="Metadata about the current page state",
    )
    screenshot: Optional[bytes] = Field(
        default=None,
        description="PNG screenshot of the page as bytes. None if screenshot not captured.",
    )
    dom_summary: str = Field(
        ...,
        description=(
            "Simplified representation of the DOM structure showing key elements, "
            "landmarks, and interactive components"
        ),
    )
    violations_found: List[ViolationDetail] = Field(
        default_factory=list,
        description="List of accessibility violations detected by the last action",
    )
    coverage_metrics: Dict[str, float] = Field(
        default_factory=dict,
        description=(
            "Percentage of different test types completed. Keys are test names, "
            "values are 0.0-1.0 representing coverage."
        ),
    )
    last_action_error: Optional[str] = Field(
        default=None,
        description="Error message if the last action failed, None if successful",
    )


class AccessibilityState(State):
    """
    Persistent state of the accessibility testing environment.
    
    Tracks the target URL, task difficulty, known violations (ground truth),
    and testing progress throughout an episode.
    """

    target_url: str = Field(
        ...,
        description="URL of the website being audited in this episode",
    )
    task_difficulty: str = Field(
        ...,
        description="Difficulty level of the current task: 'easy', 'medium', or 'hard'",
    )
    known_violations: List[ViolationDetail] = Field(
        default_factory=list,
        description=(
            "Ground truth violations that should be found. Used for grading and "
            "reward calculation."
        ),
    )
    tests_completed: List[str] = Field(
        default_factory=list,
        description="List of test types that have been executed in this episode",
    )
    episode_step: int = Field(
        default=0,
        description="Current step number in the episode, incremented with each action",
    )
