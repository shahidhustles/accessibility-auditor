"""
Accessibility Testing Task Graders

Grading functions for evaluating agent performance on accessibility testing tasks.
Each grader returns a score from 0.0 (total failure) to 1.0 (perfect performance).
"""

from typing import List, Tuple


def get_impact_weight(impact: str) -> float:
    """
    Return numeric weight for violation impact level.
    
    Args:
        impact: Impact level string (critical, serious, moderate, minor)
        
    Returns:
        float: Weight value for the impact level
    """
    return {
        "critical": 4.0,
        "serious": 3.0,
        "moderate": 2.0,
        "minor": 1.0
    }.get(impact.lower(), 1.0)


def match_violations(found: List[dict], known: List[dict]) -> Tuple[int, int, int]:
    """
    Match found violations to known violations to identify true positives,
    false positives, and false negatives.
    
    Args:
        found: List of violations found by the agent
        known: List of ground truth violations
        
    Returns:
        Tuple of (true_positives, false_positives, false_negatives)
    """
    if not found and not known:
        return 0, 0, 0
    
    if not found:
        return 0, 0, len(known)
    
    if not known:
        return 0, len(found), 0
    
    # Track which known violations have been matched
    matched_known = set()
    true_positives = 0
    
    # Match by violation_id
    for found_v in found:
        found_id = found_v.get('violation_id', '')
        
        for idx, known_v in enumerate(known):
            if idx in matched_known:
                continue
                
            known_id = known_v.get('violation_id', '')
            
            # Match by violation_id
            if found_id and known_id and found_id == known_id:
                true_positives += 1
                matched_known.add(idx)
                break
            
            # Fallback: match by similar properties if violation_id not available
            if not found_id or not known_id:
                found_html = found_v.get('element_html', '').strip()
                known_html = known_v.get('element_html', '').strip()
                found_type = found_v.get('type', '')
                known_type = known_v.get('type', '')
                
                # Match if both type and element HTML are similar
                if (found_type and known_type and found_type == known_type and
                    found_html and known_html and found_html == known_html):
                    true_positives += 1
                    matched_known.add(idx)
                    break
    
    false_positives = len(found) - true_positives
    false_negatives = len(known) - true_positives
    
    return true_positives, false_positives, false_negatives


def grade_easy_task(found_violations: List[dict], known_violations: List[dict]) -> float:
    """
    Grade Easy task: Focus on recall of Level A (critical/serious) violations.
    
    Scoring:
    - Calculate recall for critical and serious violations only
    - Return 1.0 if recall ≥ 0.8
    - Scale linearly below 0.8 threshold
    
    Args:
        found_violations: Violations found by the agent
        known_violations: Ground truth violations
        
    Returns:
        float: Score from 0.0 to 1.0
        
    Example:
        8 critical/serious found out of 10 total → recall=0.8 → score=1.0
    """
    if not known_violations:
        return 1.0 if not found_violations else 0.0
    
    # Filter for Level A violations (critical and serious)
    known_critical_serious = [
        v for v in known_violations
        if v.get('impact', '').lower() in ['critical', 'serious']
    ]
    
    if not known_critical_serious:
        # If no critical/serious violations exist, check if agent found any
        return 1.0 if not found_violations else 0.0
    
    found_critical_serious = [
        v for v in found_violations
        if v.get('impact', '').lower() in ['critical', 'serious']
    ]
    
    # Match violations to calculate true positives
    tp, _, _ = match_violations(found_critical_serious, known_critical_serious)
    
    # Calculate recall
    recall = tp / len(known_critical_serious)
    
    # Score: 1.0 if recall ≥ 0.8, else scale linearly
    threshold = 0.8
    if recall >= threshold:
        return 1.0
    else:
        # Scale from 0.0 to 1.0 based on recall
        return recall / threshold


def grade_medium_task(found_violations: List[dict], known_violations: List[dict]) -> float:
    """
    Grade Medium task: Balanced precision and recall with weighted F1 score.
    
    Scoring:
    - Calculate precision: TP / (TP + FP)
    - Calculate recall: TP / (TP + FN)
    - Weighted score: 0.6 * recall + 0.4 * precision
    - Return 1.0 if weighted score ≥ 0.7
    - Scale linearly below 0.7 threshold
    
    Args:
        found_violations: Violations found by the agent
        known_violations: Ground truth violations
        
    Returns:
        float: Score from 0.0 to 1.0
        
    Example:
        recall=0.75, precision=0.85 → weighted=0.79 → score=1.0
    """
    if not known_violations:
        return 1.0 if not found_violations else 0.0
    
    if not found_violations:
        return 0.0
    
    # Match violations
    tp, fp, fn = match_violations(found_violations, known_violations)
    
    # Calculate precision and recall
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    
    # Weighted score: favor recall slightly
    weighted_score = 0.6 * recall + 0.4 * precision
    
    # Score: 1.0 if weighted score ≥ 0.7, else scale linearly
    threshold = 0.7
    if weighted_score >= threshold:
        return 1.0
    else:
        return weighted_score / threshold


def grade_hard_task(found_violations: List[dict], known_violations: List[dict]) -> float:
    """
    Grade Hard task: Comprehensive evaluation with multiple metrics.
    
    Scoring components:
    - Recall (40%): Basic violation detection
    - Coverage (30%): Unique violation types found
    - Severity-weighted recall (20%): Impact-adjusted detection
    - False positive penalty (10%): Accuracy incentive
    
    Comprehensive score = 0.4*recall + 0.3*coverage + 0.2*severity + 0.1*fp_penalty
    Return 1.0 if comprehensive score ≥ 0.6, else scale linearly
    
    Args:
        found_violations: Violations found by the agent
        known_violations: Ground truth violations
        
    Returns:
        float: Score from 0.0 to 1.0
    """
    if not known_violations:
        return 1.0 if not found_violations else 0.0
    
    if not found_violations:
        return 0.0
    
    # Match violations
    tp, fp, fn = match_violations(found_violations, known_violations)
    
    # 1. Calculate basic recall
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    
    # 2. Calculate coverage (unique violation types)
    known_types = set(v.get('type', '') for v in known_violations if v.get('type'))
    found_types = set(v.get('type', '') for v in found_violations if v.get('type'))
    
    if known_types:
        matched_types = known_types.intersection(found_types)
        coverage = len(matched_types) / len(known_types)
    else:
        coverage = 0.0
    
    # 3. Calculate severity-weighted recall
    # Weight violations by impact level
    total_weighted = sum(get_impact_weight(v.get('impact', 'minor')) for v in known_violations)
    
    # Find matched violations to calculate weighted found
    matched_known = set()
    for found_v in found_violations:
        found_id = found_v.get('violation_id', '')
        
        for idx, known_v in enumerate(known_violations):
            if idx in matched_known:
                continue
                
            known_id = known_v.get('violation_id', '')
            
            if found_id and known_id and found_id == known_id:
                matched_known.add(idx)
                break
            
            # Fallback matching
            if not found_id or not known_id:
                found_html = found_v.get('element_html', '').strip()
                known_html = known_v.get('element_html', '').strip()
                found_type = found_v.get('type', '')
                known_type = known_v.get('type', '')
                
                if (found_type and known_type and found_type == known_type and
                    found_html and known_html and found_html == known_html):
                    matched_known.add(idx)
                    break
    
    weighted_found = sum(
        get_impact_weight(known_violations[idx].get('impact', 'minor'))
        for idx in matched_known
    )
    
    severity_weighted_recall = weighted_found / total_weighted if total_weighted > 0 else 0.0
    
    # 4. Calculate false positive penalty
    total_found = len(found_violations)
    fp_penalty = 1 - (fp / max(1, total_found))
    
    # Comprehensive score
    comprehensive_score = (
        0.4 * recall +
        0.3 * coverage +
        0.2 * severity_weighted_recall +
        0.1 * fp_penalty
    )
    
    # Score: 1.0 if comprehensive score ≥ 0.6, else scale linearly
    threshold = 0.6
    if comprehensive_score >= threshold:
        return 1.0
    else:
        return comprehensive_score / threshold
