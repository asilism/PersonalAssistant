#!/usr/bin/env python3
"""
Test nested array placeholder resolution
This reproduces the email template variable error scenario
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from orchestration.placeholder_resolver import PlaceholderResolver
from orchestration.types import Step


def test_nested_array_placeholder_with_calendar_structure():
    """
    Test that reproduces the exact scenario from the error:
    - step_0 calls list_events and returns {success: True, count: N, events: [...]}
    - step_1 tries to access {{step_0.events.0.attendees.0}}
    """
    resolver = PlaceholderResolver()

    print("\n" + "="*80)
    print("TEST: Nested array placeholder with calendar structure")
    print("="*80)

    # Simulate step_0 output (list_events result)
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
                'attendees': ['alice@company.com', 'bob@company.com'],
                'location': 'Conference Room A'
            },
            {
                'id': 'event_2',
                'title': 'Project Review',
                'description': 'Q4 project review',
                'start_time': '2025-10-23T10:00:00Z',
                'end_time': '2025-10-23T11:30:00Z',
                'attendees': ['user@company.com', 'boss@company.com'],
                'location': 'Virtual'
            }
        ]
    }

    # Register the step output
    print("\n1. Registering step_0 output...")
    resolver.register_step_result('step_0', step_0_output)

    # Test 1: Access first event's first attendee (matching the error scenario)
    print("\n2. Testing: {{step_0.events.0.attendees.0}}")
    print("-" * 80)
    step = Step(
        step_id='step_1',
        tool_name='send_email',
        input={
            'to': '{{step_0.events.0.attendees.0}}',
            'subject': '일정 변경 안내: {{step_0.events.0.title}}',
            'body': '안녕하세요'
        },
        description='Send email to first attendee',
        dependencies=['step_0']
    )

    resolved = resolver.resolve_step_input(step)
    print("-" * 80)
    print(f"\nOriginal input: {step.input}")
    print(f"Resolved input: {resolved.input}")

    assert resolved.input['to'] == 'alice@company.com', \
        f"Expected 'alice@company.com', got {resolved.input['to']}"
    assert resolved.input['subject'] == '일정 변경 안내: Team Meeting', \
        f"Expected '일정 변경 안내: Team Meeting', got {resolved.input['subject']}"
    print("✓ Test 1 PASSED: First attendee resolved correctly")

    # Test 2: Access second event's second attendee
    print("\n3. Testing: {{step_0.events.1.attendees.1}}")
    print("-" * 80)
    step = Step(
        step_id='step_2',
        tool_name='send_email',
        input={
            'to': '{{step_0.events.1.attendees.1}}'
        },
        description='Send email to second attendee of second event',
        dependencies=['step_0']
    )

    resolved = resolver.resolve_step_input(step)
    print("-" * 80)
    print(f"\nOriginal input: {step.input}")
    print(f"Resolved input: {resolved.input}")

    assert resolved.input['to'] == 'boss@company.com', \
        f"Expected 'boss@company.com', got {resolved.input['to']}"
    print("✓ Test 2 PASSED: Second event's second attendee resolved correctly")

    # Test 3: Out of range access (this should fail gracefully)
    print("\n4. Testing: {{step_0.events.5.attendees.0}} (out of range)")
    print("-" * 80)
    step = Step(
        step_id='step_3',
        tool_name='send_email',
        input={
            'to': '{{step_0.events.5.attendees.0}}'
        },
        description='Try to access non-existent event',
        dependencies=['step_0']
    )

    resolved = resolver.resolve_step_input(step)
    print("-" * 80)
    print(f"\nOriginal input: {step.input}")
    print(f"Resolved input: {resolved.input}")

    # When placeholder cannot be resolved, it returns the original text
    assert '{{' in resolved.input['to'], \
        f"Expected unresolved placeholder, got {resolved.input['to']}"
    print("✓ Test 3 PASSED: Out of range access handled gracefully (returned original placeholder)")

    # Test 4: Empty events array
    print("\n5. Testing with empty events array")
    print("-" * 80)
    step_0_empty = {
        'success': True,
        'count': 0,
        'events': []
    }
    resolver.register_step_result('step_0', step_0_empty)

    step = Step(
        step_id='step_4',
        tool_name='send_email',
        input={
            'to': '{{step_0.events.0.attendees.0}}'
        },
        description='Try to access attendee from empty events',
        dependencies=['step_0']
    )

    resolved = resolver.resolve_step_input(step)
    print("-" * 80)
    print(f"\nOriginal input: {step.input}")
    print(f"Resolved input: {resolved.input}")

    # When events is empty, placeholder cannot be resolved
    assert '{{' in resolved.input['to'], \
        f"Expected unresolved placeholder, got {resolved.input['to']}"
    print("✓ Test 4 PASSED: Empty array handled gracefully (returned original placeholder)")

    print("\n" + "="*80)
    print("ALL TESTS PASSED!")
    print("="*80)


if __name__ == '__main__':
    test_nested_array_placeholder_with_calendar_structure()
