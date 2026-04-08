---
title: Accessibility Auditor Environment Server
emoji: ♿
colorFrom: purple
colorTo: indigo
sdk: docker
pinned: false
app_port: 8000
base_path: /web
tags:
  - openenv
  - accessibility
  - wcag
---

# Accessibility Auditor OpenEnv Environment

A comprehensive web accessibility testing environment for training and evaluating AI agents on WCAG 2.1 compliance auditing.

[![OpenEnv](https://img.shields.io/badge/OpenEnv-Compatible-green)](https://github.com/meta-pytorch/openenv)
[![License](https://img.shields.io/badge/License-BSD-blue.svg)](LICENSE)

## Overview

The Accessibility Auditor environment simulates real-world web accessibility testing using Playwright for browser automation and axe-core for WCAG violation detection. Agents learn to systematically audit websites across three difficulty levels, discovering accessibility issues that affect users with disabilities.

### Key Features

- **Real-world task**: Web accessibility testing following WCAG 2.1 guidelines
- **3 difficulty levels**: Easy, Medium, and Hard test scenarios
- **12 specialized tests**: Image alt text, form labels, color contrast, keyboard navigation, ARIA, and more
- **Rich observations**: Page metadata, screenshots, DOM summaries, and violation details
- **6-signal reward function**: Encourages thorough, accurate, and efficient auditing
- **Concurrent sessions**: Supports multiple parallel evaluation sessions

## Environment Description

### Action Space

**AccessibilityAction** with the following fields:

| Field | Type | Description |
|-------|------|-------------|
| `test_type` | str | Type of test to execute (required) |
| `selector` | str | CSS selector for targeted tests (optional) |
| `parameters` | dict | Additional test parameters (optional) |

**Available test_type values:**

| Test Type | Description | WCAG Criteria |
|-----------|-------------|---------------|
| `run_axe` | Full axe-core WCAG scan | All levels |
| `run_axe_wcag_a` | WCAG Level A violations only | Level A |
| `run_axe_wcag_aa` | WCAG Level AA violations only | Level AA |
| `test_image_alt` | Check images have alt attributes | 1.1.1 |
| `test_form_labels` | Verify form inputs have labels | 3.3.2 |
| `test_color_contrast` | Check color contrast ratios | 1.4.3 |
| `test_keyboard_nav` | Test keyboard navigation | 2.1.1 |
| `test_aria_labels` | Validate ARIA attributes | 4.1.2 |
| `test_heading_structure` | Check heading hierarchy | 1.3.1 |
| `test_landmark_roles` | Verify landmark roles | 1.3.1 |
| `test_focus_indicators` | Check visible focus styles | 2.4.7 |
| `test_skip_links` | Check skip navigation links | 2.4.1 |
| `test_language_attrs` | Validate language attributes | 3.1.1 |
| `test_table_headers` | Check table headers | 1.3.1 |
| `test_video_captions` | Verify video captions/subtitles | 1.2.2 |
| `complete_audit` | Finish the audit episode | - |

### Observation Space

**AccessibilityObservation** containing:

| Field | Type | Description |
|-------|------|-------------|
| `page_metadata` | PageMetadata | URL, title, viewport size, timestamp |
| `screenshot` | bytes | PNG screenshot (optional) |
| `dom_summary` | str | Simplified DOM structure (5000 chars) |
| `violations_found` | List[ViolationDetail] | Detected accessibility violations |
| `coverage_metrics` | dict | Test coverage percentages |
| `last_action_error` | str | Error from previous action (if any) |

### Reward Function

The environment uses a **6-signal reward function** to provide rich learning signals:

1. **Violation discovery** (+0.5 per critical/serious violation found)
2. **Coverage bonus** (+0.2 per new test type completed)
3. **False positive penalty** (-0.3 per false positive)
4. **Severity weighting** (critical=4x, serious=3x, moderate=2x, minor=1x)
5. **Efficiency bonus** (rewards early discovery)
6. **Episode completion** (+1.0 for ≥70% coverage, +0.5 for ≥50%)

**Typical reward range**: -5.0 to +10.0 per episode

## Tasks & Grading

### Easy Task
- **Success criteria**: ≥80% recall on critical/serious violations
- **Grading**: Returns 1.0 if recall ≥ 0.8, else scales linearly

### Medium Task
- **Success criteria**: ≥70% weighted score (60% recall + 40% precision)
- **Grading**: Returns 1.0 if weighted score ≥ 0.7, else scales linearly

### Hard Task
- **Success criteria**: ≥60% comprehensive score
- **Metrics**: 40% recall, 30% coverage, 20% severity-weighted, 10% FP penalty

## Setup Instructions

### Local Development

```bash
# Clone and install
git clone <your-repo-url>
cd accessibility_auditor
uv sync

# Install Playwright browsers
playwright install chromium --with-deps

# Run server
uv run uvicorn server.app:app --host 0.0.0.0 --port 8000
```

### Docker Setup

```bash
# Build and run
docker build -t accessibility-auditor -f server/Dockerfile .
docker run -p 8000:8000 accessibility-auditor
```

## Usage

```python
from client import AccessibilityEnv
from models import AccessibilityAction

with AccessibilityEnv(base_url="http://localhost:8000") as env:
    result = env.reset()
    action = AccessibilityAction(test_type="run_axe")
    result = env.step(action)
    print(f"Found {len(result.observation.violations_found)} violations")
```

### Running Baseline Inference

```bash
export HF_TOKEN="your-openai-api-key"  # or OPENAI_API_KEY
export API_BASE_URL="https://api.openai.com/v1"
export MODEL_NAME="gpt-3.5-turbo"
export SERVER_URL="http://localhost:8000"
python inference.py
```

> **Note:** The inference script reads `HF_TOKEN` environment variable (as per hackathon requirements) which should contain your OpenAI API key.

## Baseline Scores

| Task | Baseline Score |
|------|----------------|
| Easy | 0.94 |
| Medium | 0.53 |
| Hard | 1.00 |
| **Overall** | **0.82** |

*Baseline: GPT-3.5-turbo with systematic auditing strategy (run comprehensive axe scan, then targeted tests)*

## Deployment

### Hugging Face Spaces

```bash
openenv push --repo-id YOUR_USERNAME/accessibility-auditor
```

### Validation

```bash
./scripts/validate-submission.sh https://YOUR_USERNAME-accessibility-auditor.hf.space
```

## Project Structure

```
accessibility_auditor/
├── server/
│   ├── app.py                              # FastAPI server
│   ├── accessibility_auditor_environment.py # Environment logic
│   ├── browser_manager.py                  # Playwright lifecycle
│   ├── axe_runner.py                       # axe-core wrapper
│   ├── test_runners.py                     # 12 test functions
│   └── Dockerfile                          # Container definition
├── graders/
│   └── accessibility_grader.py             # Task graders
├── fixtures/sites/{easy,medium,hard}/      # HTML test pages
├── models.py                               # Pydantic models
├── client.py                               # OpenEnv client
├── inference.py                            # Baseline script
└── README.md                               # This file
```

## Technical Details

- **Browser**: Chromium headless (1280x720 viewport)
- **Max steps**: 20 per episode
- **Concurrency**: Supported
- **Dependencies**: playwright, axe-playwright-python, openenv-core, fastapi

## License

BSD 3-Clause License

## Acknowledgments

- Built for [Meta x PyTorch OpenEnv Hackathon](https://github.com/meta-pytorch/openenv)
- Uses [axe-core](https://github.com/dequelabs/axe-core) by Deque Systems
- Uses [Playwright](https://playwright.dev/) by Microsoft

---

**Team**: Richie Rich  
**Members**: Om Agarwal, Piyush Pagar (Lead), Shahid Patel  
**Hackathon**: Meta x PyTorch OpenEnv - Round 1  
**Deadline**: April 8, 2026
