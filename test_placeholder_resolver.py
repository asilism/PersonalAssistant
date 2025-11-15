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


def test_single_braces_and_array_indexing():
    """Test single braces {} and Python array indexing [0] support"""
    resolver = PlaceholderResolver()

    # Simulate step_0 output matching the error log structure
    step_0_output = {
        'success': True,
        'count': 2,
        'events': [
            {
                'id': 'event_1',
                'title': 'Team Meeting',
                'description': 'Weekly team sync',
                'start_time': '2025-10-22T14:00:00Z',
                'end_time': '2025-10-22T15:00:00Z',
                'attendees': ['alice@example.com', 'bob@example.com'],
                'location': 'Conference Room A'
            },
            {
                'id': 'event_2',
                'title': 'Project Review',
                'description': 'Q4 project review',
                'start_time': '2025-10-23T10:00:00Z',
                'end_time': '2024-11-30T23:59:59',
                'attendees': ['user@example.com', 'boss@example.com'],
                'location': 'Virtual'
            }
        ]
    }

    # Register the step output
    resolver.register_step_result('step_0', step_0_output)

    # Test 1: Single braces with Python array indexing (matching the error log)
    print("\n=== Test 1: Single braces with Python array indexing ===")
    step = Step(
        step_id='step_1',
        tool_name='update_event',
        input={
            'event_id': '{step_0.events[0].id}'  # Single braces + [0] indexing
        },
        description='Test single braces with array indexing',
        dependencies=['step_0']
    )

    resolved = resolver.resolve_step_input(step)
    print(f"Input: {step.input}")
    print(f"Resolved: {resolved.input}")
    assert resolved.input['event_id'] == 'event_1', \
        f"Expected 'event_1', got {resolved.input['event_id']}"
    print("✓ Single braces with Python array indexing works!")

    # Test 2: Single braces with nested array indexing for email
    print("\n=== Test 2: Single braces with nested array access ===")
    step = Step(
        step_id='step_2',
        tool_name='send_email',
        input={
            'to': '{step_0.events[0].attendees[0]}'  # Nested array access
        },
        description='Test nested array access',
        dependencies=['step_0']
    )

    resolved = resolver.resolve_step_input(step)
    print(f"Input: {step.input}")
    print(f"Resolved: {resolved.input}")
    assert resolved.input['to'] == 'alice@example.com', \
        f"Expected 'alice@example.com', got {resolved.input['to']}"
    print("✓ Nested array access works!")

    # Test 3: Mixed double braces with dot notation (recommended style)
    print("\n=== Test 3: Double braces with dot notation (recommended) ===")
    step = Step(
        step_id='step_3',
        tool_name='update_event',
        input={
            'event_id': '{{step_0.events.0.id}}',  # Double braces + dot notation
            'title': '{{step_0.events.0.title}}'
        },
        description='Test recommended style',
        dependencies=['step_0']
    )

    resolved = resolver.resolve_step_input(step)
    print(f"Input: {step.input}")
    print(f"Resolved: {resolved.input}")
    assert resolved.input['event_id'] == 'event_1', \
        f"Expected 'event_1', got {resolved.input['event_id']}"
    assert resolved.input['title'] == 'Team Meeting', \
        f"Expected 'Team Meeting', got {resolved.input['title']}"
    print("✓ Recommended style works!")

    # Test 4: Dollar sign syntax ${} with array indexing
    print("\n=== Test 4: Dollar sign syntax with array indexing ===")
    step = Step(
        step_id='step_4',
        tool_name='send_email',
        input={
            'to': '${step_0.events[1].attendees[1]}'  # Dollar syntax + [1] indexing
        },
        description='Test dollar syntax',
        dependencies=['step_0']
    )

    resolved = resolver.resolve_step_input(step)
    print(f"Input: {step.input}")
    print(f"Resolved: {resolved.input}")
    assert resolved.input['to'] == 'boss@example.com', \
        f"Expected 'boss@example.com', got {resolved.input['to']}"
    print("✓ Dollar sign syntax works!")

    print("\n=== All single braces and array indexing tests passed! ===")


if __name__ == '__main__':
    print("="*60)
    print("Running original expression evaluation tests...")
    print("="*60)
    test_expression_evaluation()

    print("\n" + "="*60)
    print("Running new single braces and array indexing tests...")
    print("="*60)
    test_single_braces_and_array_indexing()
