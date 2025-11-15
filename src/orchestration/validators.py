"""
Validators for input parameters
"""

import re
from typing import Tuple


def validate_email(email: str) -> Tuple[bool, str]:
    """
    Validate email address format

    Args:
        email: Email address to validate

    Returns:
        Tuple of (is_valid, error_message)
        - (True, "") if valid
        - (False, error_message) if invalid
    """
    if not email:
        return False, "Email address is required"

    # Check for template variables like {{USER_EMAIL}}, {{...}}
    template_pattern = r'\{\{.*?\}\}'
    if re.search(template_pattern, email):
        return False, f"Email address contains unresolved template variable: {email}"

    # Check for empty or whitespace-only
    if not email.strip():
        return False, "Email address cannot be empty"

    # RFC 5322 simplified email regex
    # This pattern matches most common email formats
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'

    if not re.match(email_pattern, email.strip()):
        return False, f"Invalid email address format: {email}"

    # Block common placeholder/fake domains
    blocked_domains = [
        'example.com', 'example.org', 'example.net',
        'test.com', 'test.org', 'test.net',
        'sample.com', 'sample.org', 'sample.net',
        'placeholder.com', 'dummy.com', 'fake.com'
    ]
    email_domain = email.strip().split('@')[-1].lower()
    if email_domain in blocked_domains:
        return False, f"Email validation failed: '{email_domain}' is a placeholder domain"

    return True, ""


def extract_missing_params(error_message: str) -> dict:
    """
    Extract missing parameters from error message

    Args:
        error_message: Error message from validation

    Returns:
        Dictionary with missing parameter information
    """
    # Check if it's an email validation error
    if "email" in error_message.lower():
        if "template variable" in error_message.lower():
            return {
                "param_name": "to",
                "param_type": "email",
                "reason": "unresolved_template",
                "question": "이메일을 보내려면 받는 사람의 이메일 주소가 필요합니다. 누구에게 보낼까요?"
            }
        elif "placeholder domain" in error_message.lower():
            return {
                "param_name": "to",
                "param_type": "email",
                "reason": "placeholder_domain",
                "question": "정확한 이메일 주소를 알 수 없습니다. 받는 사람의 이메일 주소를 입력해주세요."
            }
        elif "required" in error_message.lower():
            return {
                "param_name": "to",
                "param_type": "email",
                "reason": "missing",
                "question": "이메일을 보내려면 받는 사람의 이메일 주소가 필요합니다. 누구에게 보낼까요?"
            }
        elif "invalid" in error_message.lower():
            return {
                "param_name": "to",
                "param_type": "email",
                "reason": "invalid_format",
                "question": f"유효하지 않은 이메일 주소입니다. 올바른 이메일 주소를 입력해주세요."
            }

    return {
        "param_name": "unknown",
        "param_type": "unknown",
        "reason": "validation_failed",
        "question": "입력값이 유효하지 않습니다. 다시 시도해주세요."
    }
