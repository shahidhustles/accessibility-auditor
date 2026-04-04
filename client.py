# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""Accessibility Auditor Environment Client."""

from io import BytesIO
from typing import Any, Dict, Optional, Tuple

from openenv.core import EnvClient

from .models import (
    AccessibilityAction,
    AccessibilityObservation,
    AccessibilityState,
    PageMetadata,
    ViolationDetail,
)


class AccessibilityEnv(
    EnvClient[AccessibilityAction, AccessibilityObservation, AccessibilityState]
):
    """
    Client for the Accessibility Auditor Environment.

    This client maintains a persistent WebSocket connection to the environment server,
    enabling efficient multi-step interactions with lower latency.
    Each client instance has its own dedicated environment session on the server.

    Example:
        >>> # Connect to a running server
        >>> with AccessibilityEnv(base_url="http://localhost:8000") as client:
        ...     result = client.reset()
        ...     print(f"Current URL: {result.observation.page_metadata.url}")
        ...
        ...     # Run an axe-core accessibility scan
        ...     action = AccessibilityAction(test_type="run_axe")
        ...     result = client.step(action)
        ...     print(f"Found {len(result.observation.violations_found)} violations")

    Example with Docker:
        >>> # Automatically start container and connect
        >>> client = AccessibilityEnv.from_docker_image("accessibility_auditor-env:latest")
        >>> try:
        ...     result = client.reset()
        ...     action = AccessibilityAction(
        ...         test_type="check_alt_text",
        ...         selector="img"
        ...     )
        ...     result = client.step(action)
        ... finally:
        ...     client.close()
    """

    def _step_payload(self, action: AccessibilityAction) -> Dict[str, Any]:
        """
        Convert AccessibilityAction to JSON payload for the server.

        Args:
            action: AccessibilityAction instance with test_type and optional parameters

        Returns:
            Dictionary representation suitable for JSON encoding
        """
        return action.model_dump()

    def _parse_result(
        self, result: Dict[str, Any]
    ) -> Tuple[AccessibilityObservation, float, bool, Dict[str, Any]]:
        """
        Parse step result into (observation, reward, done, info).

        Args:
            result: JSON response data from server step endpoint

        Returns:
            Tuple of (observation, reward, done, info) where:
                - observation: AccessibilityObservation with test results
                - reward: Float reward value
                - done: Boolean indicating if episode is complete
                - info: Additional metadata dictionary

        Raises:
            ValueError: If result is malformed or missing required fields
        """
        try:
            obs_data = result.get("observation")
            if obs_data is None:
                raise ValueError("Missing 'observation' field in server response")

            # Parse nested models
            page_metadata = PageMetadata(**obs_data.get("page_metadata", {}))

            violations = [
                ViolationDetail(**v) for v in obs_data.get("violations_found", [])
            ]

            # Handle optional screenshot bytes
            screenshot = obs_data.get("screenshot")
            if screenshot is not None and isinstance(screenshot, str):
                # If screenshot is base64 encoded, decode it
                import base64

                screenshot = base64.b64decode(screenshot)

            observation = AccessibilityObservation(
                page_metadata=page_metadata,
                screenshot=screenshot,
                dom_summary=obs_data.get("dom_summary", ""),
                violations_found=violations,
                coverage_metrics=obs_data.get("coverage_metrics", {}),
                last_action_error=obs_data.get("last_action_error"),
            )

            reward = result.get("reward", 0.0)
            done = result.get("done", False)
            info = result.get("info", {})

            return observation, reward, done, info

        except (KeyError, TypeError, ValueError) as e:
            raise ValueError(f"Failed to parse server result: {e}") from e

    def _parse_state(self, state: Dict[str, Any]) -> AccessibilityState:
        """
        Parse state dict into AccessibilityState object.

        Args:
            state: JSON response from state endpoint

        Returns:
            AccessibilityState object with episode configuration and progress

        Raises:
            ValueError: If state is malformed or missing required fields
        """
        try:
            # Parse nested violation models
            known_violations = [
                ViolationDetail(**v) for v in state.get("known_violations", [])
            ]

            return AccessibilityState(
                target_url=state.get("target_url", ""),
                task_difficulty=state.get("task_difficulty", "easy"),
                known_violations=known_violations,
                tests_completed=state.get("tests_completed", []),
                episode_step=state.get("episode_step", 0),
            )

        except (KeyError, TypeError, ValueError) as e:
            raise ValueError(f"Failed to parse state: {e}") from e

    def get_screenshot_as_image(self) -> Optional["Image.Image"]:
        """
        Get the last observation's screenshot as a PIL Image.

        Returns:
            PIL Image object if screenshot is available, None otherwise

        Raises:
            ImportError: If PIL is not installed
        """
        try:
            from PIL import Image
        except ImportError:
            raise ImportError(
                "PIL is required for image processing. Install with: pip install pillow"
            )

        if not hasattr(self, "_last_observation"):
            return None

        obs = getattr(self, "_last_observation", None)
        if obs is None or obs.screenshot is None:
            return None

        return Image.open(BytesIO(obs.screenshot))

    def get_violations_summary(self) -> str:
        """
        Get a formatted summary of violations from the last observation.

        Returns:
            Human-readable string summarizing violations by impact level
        """
        if not hasattr(self, "_last_observation"):
            return "No observations yet"

        obs = getattr(self, "_last_observation", None)
        if obs is None or not obs.violations_found:
            return "No violations found"

        # Group by impact
        by_impact = {"critical": [], "serious": [], "moderate": [], "minor": []}
        for violation in obs.violations_found:
            by_impact.setdefault(violation.impact, []).append(violation)

        lines = [f"Total violations: {len(obs.violations_found)}"]
        for impact in ["critical", "serious", "moderate", "minor"]:
            count = len(by_impact.get(impact, []))
            if count > 0:
                lines.append(f"  {impact.upper()}: {count}")

        return "\n".join(lines)
