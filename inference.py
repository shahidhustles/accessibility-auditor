#!/usr/bin/env python3
"""
Baseline inference script for Accessibility Auditor OpenEnv environment.
Uses OpenAI API to run accessibility testing tasks across 3 difficulty levels.
"""

import os
import sys
from typing import List, Dict, Any
import json
from openai import OpenAI

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from accessibility_auditor.client import AccessibilityEnv
from accessibility_auditor.models import AccessibilityAction


# Environment variables (required by hackathon guidelines)
API_BASE_URL = os.getenv("API_BASE_URL", "https://api.openai.com/v1")
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4")
HF_TOKEN = os.getenv("HF_TOKEN", os.getenv("OPENAI_API_KEY", ""))

# Validate required environment variables
if not HF_TOKEN:
    print("ERROR: HF_TOKEN or OPENAI_API_KEY environment variable not set")
    sys.exit(1)


SYSTEM_PROMPT = """You are an expert web accessibility auditor using the WCAG 2.1 guidelines.
Your task is to systematically test a web page for accessibility violations.

Available test actions:
- run_axe: Full axe-core WCAG scan (comprehensive, recommended first step)
- run_axe_wcag_a: WCAG Level A violations only
- run_axe_wcag_aa: WCAG Level AA violations only
- test_image_alt: Check images have alt text
- test_form_labels: Check form inputs have labels
- test_color_contrast: Check color contrast ratios
- test_keyboard_nav: Check keyboard navigation
- test_aria_labels: Check ARIA attributes
- test_heading_structure: Check heading hierarchy
- test_landmark_roles: Check landmark roles
- test_focus_indicators: Check focus indicators
- test_skip_links: Check skip navigation links
- test_language_attrs: Check language attributes
- test_table_headers: Check table headers
- test_video_captions: Check video captions
- complete_audit: Finish the audit

Strategy:
1. Start with run_axe to get a comprehensive overview
2. Run specific tests for critical areas (images, forms, contrast)
3. Complete the audit when satisfied

Respond with ONLY the test_type to execute (e.g., "run_axe" or "test_image_alt").
Do not include explanations or additional text."""


def run_episode(client: AccessibilityEnv, llm_client: OpenAI, max_steps: int = 20) -> Dict[str, Any]:
    """Run a single episode with the LLM agent."""
    
    # Reset environment - returns (observation, reward, done, info)
    observation, reward, done, info = client.reset()
    state = client.state()
    
    total_reward = 0.0
    step_count = 0
    action_history: List[str] = []
    
    print(f"\n{'='*60}")
    print(f"Episode started - Difficulty: {state.task_difficulty}")
    print(f"Target URL: {state.target_url}")
    print(f"Known violations: {len(state.known_violations)}")
    print(f"{'='*60}\n")
    
    while not done and step_count < max_steps:
        step_count += 1
        
        # Build prompt for LLM
        user_prompt = f"""Step {step_count}/{max_steps}

Current state:
- URL: {observation.page_metadata.url}
- Page title: {observation.page_metadata.title}
- Violations found so far: {len(observation.violations_found)}
- Tests completed: {', '.join(state.tests_completed) if state.tests_completed else 'none'}
- Coverage: {observation.coverage_metrics.get('overall', 0.0):.1%}

Recent actions: {', '.join(action_history[-3:]) if action_history else 'none'}

Last action error: {observation.last_action_error if observation.last_action_error else 'none'}

What test should we run next?"""
        
        # Get LLM response
        try:
            response = llm_client.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,
                max_tokens=50
            )
            
            test_type = response.choices[0].message.content.strip()
            
            # Clean up response (remove quotes, extra whitespace)
            test_type = test_type.strip('"\'`').strip()
            
            # Validate test_type
            valid_actions = [
                "run_axe", "run_axe_wcag_a", "run_axe_wcag_aa",
                "test_image_alt", "test_form_labels", "test_color_contrast",
                "test_keyboard_nav", "test_aria_labels", "test_heading_structure",
                "test_landmark_roles", "test_focus_indicators", "test_skip_links",
                "test_language_attrs", "test_table_headers", "test_video_captions",
                "complete_audit"
            ]
            
            if test_type not in valid_actions:
                print(f"⚠️  Invalid action '{test_type}', using 'run_axe'")
                test_type = "run_axe"
            
        except Exception as e:
            print(f"⚠️  LLM error: {e}, using fallback action")
            test_type = "run_axe" if step_count == 1 else "complete_audit"
        
        # Execute action - returns (observation, reward, done, info)
        action = AccessibilityAction(test_type=test_type)
        observation, reward, done, info = client.step(action)
        state = client.state()
        
        total_reward += reward
        action_history.append(test_type)
        
        # Print step summary
        print(f"Step {step_count}: {test_type}")
        print(f"  Violations found: {len(observation.violations_found)}")
        print(f"  Reward: {reward:+.2f} (total: {total_reward:+.2f})")
        print(f"  Coverage: {observation.coverage_metrics.get('overall', 0.0):.1%}")
        
        if done:
            print(f"  Episode completed!\n")
            break
    
    return {
        "total_reward": total_reward,
        "steps_taken": step_count,
        "violations_found": len(observation.violations_found),
        "coverage": observation.coverage_metrics.get('overall', 0.0),
        "actions": action_history
    }


def run_task(task_name: str, difficulty: str, num_episodes: int = 3) -> float:
    """Run multiple episodes for a task and return average score."""
    
    print(f"\n{'#'*60}")
    print(f"# Running Task: {task_name} ({difficulty} difficulty)")
    print(f"# Episodes: {num_episodes}")
    print(f"{'#'*60}")
    
    # Initialize client
    base_url = os.getenv("SERVER_URL", "http://localhost:8000")
    
    llm_client = OpenAI(
        api_key=HF_TOKEN,
        base_url=API_BASE_URL
    )
    
    episode_results = []
    
    for episode_num in range(num_episodes):
        print(f"\n--- Episode {episode_num + 1}/{num_episodes} ---")
        
        try:
            with AccessibilityEnv(base_url=base_url).sync() as client:
                result = run_episode(client, llm_client)
                episode_results.append(result)
                
        except Exception as e:
            print(f"❌ Episode {episode_num + 1} failed: {e}")
            episode_results.append({
                "total_reward": 0.0,
                "steps_taken": 0,
                "violations_found": 0,
                "coverage": 0.0,
                "actions": []
            })
    
    # Calculate average score
    avg_reward = sum(r["total_reward"] for r in episode_results) / len(episode_results)
    avg_coverage = sum(r["coverage"] for r in episode_results) / len(episode_results)
    avg_violations = sum(r["violations_found"] for r in episode_results) / len(episode_results)
    
    print(f"\n{'='*60}")
    print(f"Task '{task_name}' Results:")
    print(f"  Average reward: {avg_reward:.2f}")
    print(f"  Average coverage: {avg_coverage:.1%}")
    print(f"  Average violations found: {avg_violations:.1f}")
    print(f"{'='*60}\n")
    
    # Normalize reward to 0.0-1.0 score
    # Assuming typical reward range of -5 to +10
    normalized_score = max(0.0, min(1.0, (avg_reward + 5.0) / 15.0))
    
    return normalized_score


def main():
    """Main inference script entry point."""
    
    print("="*60)
    print("Accessibility Auditor - Baseline Inference")
    print("="*60)
    print(f"Model: {MODEL_NAME}")
    print(f"API Base: {API_BASE_URL}")
    print("="*60)
    
    # Run 3 tasks as per hackathon requirements
    tasks = [
        ("easy_task", "easy", 3),
        ("medium_task", "medium", 3),
        ("hard_task", "hard", 3)
    ]
    
    results = {}
    
    for task_name, difficulty, num_episodes in tasks:
        try:
            score = run_task(task_name, difficulty, num_episodes)
            results[task_name] = score
        except Exception as e:
            print(f"❌ Task '{task_name}' failed: {e}")
            results[task_name] = 0.0
    
    # Print final results
    print("\n" + "="*60)
    print("FINAL BASELINE SCORES")
    print("="*60)
    for task_name, score in results.items():
        print(f"{task_name:20s}: {score:.4f}")
    print("="*60)
    
    # Save results to file
    results_file = "baseline_results.json"
    with open(results_file, "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"\nResults saved to: {results_file}")
    
    # Calculate overall score
    overall_score = sum(results.values()) / len(results)
    print(f"Overall average score: {overall_score:.4f}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
