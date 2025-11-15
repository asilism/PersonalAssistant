#!/usr/bin/env python3
"""
Test script for PlaceholderResolver with expression evaluation
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from orchestration.placeholder_resolver import PlaceholderResolver
from orchestration.types import Step


def test_expression_evaluation():
    """Test that expression evaluation works for list concatenation"""
    resolver = PlaceholderResolver()

    # Simulate step_1 output (same structure as in the logs)
    step_1_output = {
        'success': True,
        'event': {
            'id': 'event_2',
            'title': 'Project Review',
            'description': 'Q4 project review',
            'start_time': '2025-10-23T10:00:00Z',
            'end_time': '2024-11-30T23:59:59',
            'attendees': ['user@example.com', 'boss@example.com'],
            'location': 'Virtual',
            'updated_at': '2025-11-15T17:45:12.160958'
        }
    }

    # Register the step output
    resolver.register_step_result('step_1', step_1_output)

    # Test 1: Simple field access
    print("\n=== Test 1: Simple field access ===")
    step = Step(
        step_id='step_2',
        tool_name='update_event',
        input={
            'event_id': '{{step_1.event.id}}'
        },
        description='Test simple access',
        dependencies=['step_1']
    )

    resolved = resolver.resolve_step_input(step)
    print(f"Input: {step.input}")
    print(f"Resolved: {resolved.input}")
    assert resolved.input['event_id'] == 'event_2', f"Expected 'event_2', got {resolved.input['event_id']}"
    print("✓ Simple field access works!")

    # Test 2: Expression with list concatenation (using smart dict)
    print("\n=== Test 2: Expression with list concatenation (smart dict) ===")
    step = Step(
        step_id='step_2',
        tool_name='update_event',
        input={
            'event_id': 'event_2',
            'attendees': "{{step_1.attendees + ['asilism.lee@gmail.com']}}"
        },
        description='Test expression evaluation',
        dependencies=['step_1']
    )

    resolved = resolver.resolve_step_input(step)
    print(f"Input: {step.input}")
    print(f"Resolved: {resolved.input}")
    expected_attendees = ['user@example.com', 'boss@example.com', 'asilism.lee@gmail.com']
    assert resolved.input['attendees'] == expected_attendees, \
        f"Expected {expected_attendees}, got {resolved.input['attendees']}"
    print("✓ Expression with list concatenation works!")

    # Test 3: Expression with explicit nested path
    print("\n=== Test 3: Expression with explicit nested path ===")
    step = Step(
        step_id='step_2',
        tool_name='update_event',
        input={
            'event_id': 'event_2',
            'attendees': "{{step_1.event.attendees + ['asilism.lee@gmail.com']}}"
        },
        description='Test expression with explicit path',
        dependencies=['step_1']
    )

    resolved = resolver.resolve_step_input(step)
    print(f"Input: {step.input}")
    print(f"Resolved: {resolved.input}")
    assert resolved.input['attendees'] == expected_attendees, \
        f"Expected {expected_attendees}, got {resolved.input['attendees']}"
    print("✓ Expression with explicit nested path works!")

    print("\n=== All tests passed! ===")


if __name__ == '__main__':
    test_expression_evaluation()
