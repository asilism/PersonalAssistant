#!/usr/bin/env python3
"""
Calculator Agent MCP Server
Provides mathematical calculation tools
"""

import math
from fastmcp import FastMCP

# Create FastMCP server
mcp = FastMCP("calculator-agent")


@mcp.tool()
def add(numbers: list[float]) -> dict:
    """Add two or more numbers

    Args:
        numbers: Numbers to add

    Returns:
        Result of the addition operation
    """
    if not numbers:
        return {
            "success": False,
            "error": "At least one number required"
        }

    result = sum(numbers)
    return {
        "success": True,
        "operation": "addition",
        "numbers": numbers,
        "result": result
    }


@mcp.tool()
def subtract(numbers: list[float]) -> dict:
    """Subtract numbers (first - second - third...)

    Args:
        numbers: Numbers to subtract

    Returns:
        Result of the subtraction operation
    """
    if not numbers:
        return {
            "success": False,
            "error": "At least one number required"
        }

    result = numbers[0]
    for num in numbers[1:]:
        result -= num

    return {
        "success": True,
        "operation": "subtraction",
        "numbers": numbers,
        "result": result
    }


@mcp.tool()
def multiply(numbers: list[float]) -> dict:
    """Multiply two or more numbers

    Args:
        numbers: Numbers to multiply

    Returns:
        Result of the multiplication operation
    """
    if not numbers:
        return {
            "success": False,
            "error": "At least one number required"
        }

    result = 1
    for num in numbers:
        result *= num

    return {
        "success": True,
        "operation": "multiplication",
        "numbers": numbers,
        "result": result
    }


@mcp.tool()
def divide(numbers: list[float]) -> dict:
    """Divide numbers (first / second / third...)

    Args:
        numbers: Numbers to divide

    Returns:
        Result of the division operation
    """
    if not numbers:
        return {
            "success": False,
            "error": "At least one number required"
        }

    if any(num == 0 for num in numbers[1:]):
        return {
            "success": False,
            "error": "Division by zero"
        }

    result = numbers[0]
    for num in numbers[1:]:
        result /= num

    return {
        "success": True,
        "operation": "division",
        "numbers": numbers,
        "result": result
    }


@mcp.tool()
def power(base: float, exponent: float) -> dict:
    """Raise a number to a power

    Args:
        base: Base number
        exponent: Exponent

    Returns:
        Result of the power operation
    """
    result = math.pow(base, exponent)
    return {
        "success": True,
        "operation": "power",
        "base": base,
        "exponent": exponent,
        "result": result
    }
