#!/usr/bin/env python3
"""
Test email validation logic
"""

import sys
sys.path.insert(0, 'src')

from orchestration.validators import validate_email, extract_missing_params


def test_validate_email():
    """Test email validation function"""
    print("=" * 80)
    print("Testing Email Validation")
    print("=" * 80)

    test_cases = [
        # (email, expected_valid, description)
        ("user@gmail.com", True, "Valid email"),
        ("test.user+tag@company.co.kr", True, "Valid email with special chars"),
        ("user@example.com", False, "Placeholder domain - example.com"),
        ("asilism@example.com", False, "Placeholder domain - example.com"),
        ("test@test.com", False, "Placeholder domain - test.com"),
        ("user@sample.org", False, "Placeholder domain - sample.org"),
        ("fake@dummy.com", False, "Placeholder domain - dummy.com"),
        ("{{USER_EMAIL}}", False, "Template variable"),
        ("{{RECIPIENT}}", False, "Another template variable"),
        ("", False, "Empty string"),
        ("   ", False, "Whitespace only"),
        ("invalid-email", False, "Missing @ and domain"),
        ("invalid@", False, "Missing domain"),
        ("@example.com", False, "Missing local part"),
        ("user @example.com", False, "Space in email"),
        ("user@example", False, "Missing TLD"),
    ]

    passed = 0
    failed = 0

    for email, expected_valid, description in test_cases:
        is_valid, error_msg = validate_email(email)

        status = "✓ PASS" if is_valid == expected_valid else "✗ FAIL"
        if is_valid == expected_valid:
            passed += 1
        else:
            failed += 1

        print(f"\n{status}: {description}")
        print(f"  Input: '{email}'")
        print(f"  Expected: {'Valid' if expected_valid else 'Invalid'}")
        print(f"  Got: {'Valid' if is_valid else 'Invalid'}")
        if not is_valid:
            print(f"  Error: {error_msg}")

    print("\n" + "=" * 80)
    print(f"Results: {passed} passed, {failed} failed out of {len(test_cases)} tests")
    print("=" * 80)

    return failed == 0


def test_extract_missing_params():
    """Test extract_missing_params function"""
    print("\n" + "=" * 80)
    print("Testing Extract Missing Params")
    print("=" * 80)

    test_cases = [
        "Email validation failed: Email address contains unresolved template variable: {{USER_EMAIL}}",
        "Email validation failed: Email address is required",
        "Email validation failed: Invalid email address format: invalid-email",
        "Email validation failed: 'example.com' is a placeholder domain",
    ]

    for error_msg in test_cases:
        print(f"\nError: {error_msg}")
        result = extract_missing_params(error_msg)
        print(f"  Param name: {result.get('param_name')}")
        print(f"  Param type: {result.get('param_type')}")
        print(f"  Reason: {result.get('reason')}")
        print(f"  Question: {result.get('question')}")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    print("\nEmail Validation Test Suite\n")

    success = test_validate_email()
    test_extract_missing_params()

    if success:
        print("\n✓ All tests passed!")
        sys.exit(0)
    else:
        print("\n✗ Some tests failed!")
        sys.exit(1)
