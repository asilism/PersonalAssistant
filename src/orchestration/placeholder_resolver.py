"""
Placeholder Resolver - Resolves placeholders in step inputs using previous step outputs
"""

import re
from typing import Any, Dict, List, Optional
from .types import Step, StepResult


class PlaceholderResolver:
    """Resolves placeholders like {{step_id}} or {{step_id.field}} in step inputs"""

    PLACEHOLDER_PATTERN = re.compile(r'\{\{([^}]+)\}\}')

    def __init__(self):
        self._step_outputs: Dict[str, Any] = {}

    def register_step_result(self, step_id: str, output: Any) -> None:
        """
        Register a step's output for later placeholder resolution

        Args:
            step_id: The step ID
            output: The step's output (can be dict, list, or primitive)
        """
        self._step_outputs[step_id] = output
        print(f"[PlaceholderResolver] Registered output for step '{step_id}': {output}")

    def resolve_step_input(self, step: Step) -> Step:
        """
        Resolve all placeholders in a step's input

        Args:
            step: The step to resolve placeholders for

        Returns:
            A new Step with placeholders resolved
        """
        resolved_input = self._resolve_dict(step.input)

        # Create a new step with resolved input
        return Step(
            step_id=step.step_id,
            tool_name=step.tool_name,
            input=resolved_input,
            description=step.description,
            dependencies=step.dependencies
        )

    def _resolve_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively resolve placeholders in a dictionary"""
        resolved = {}
        for key, value in data.items():
            resolved[key] = self._resolve_value(value)
        return resolved

    def _resolve_value(self, value: Any) -> Any:
        """Resolve placeholders in a single value"""
        if isinstance(value, str):
            return self._resolve_string(value)
        elif isinstance(value, dict):
            return self._resolve_dict(value)
        elif isinstance(value, list):
            return [self._resolve_value(item) for item in value]
        else:
            return value

    def _resolve_string(self, text: str) -> Any:
        """
        Resolve placeholders in a string

        Supports:
        - {{step_id}} - replaces with entire output
        - {{step_id.field}} - replaces with specific field from output
        - {{step_id.field.nested}} - supports nested field access
        """
        # Find all placeholders in the string
        matches = list(self.PLACEHOLDER_PATTERN.finditer(text))

        if not matches:
            return text

        # If the entire string is a single placeholder, return the value directly
        if len(matches) == 1 and matches[0].group(0) == text:
            placeholder = matches[0].group(1)
            value = self._get_placeholder_value(placeholder)
            if value is not None:
                print(f"[PlaceholderResolver] Resolved '{text}' -> {value}")
                return value
            else:
                print(f"[PlaceholderResolver] WARNING: Could not resolve placeholder '{text}'")
                return text

        # If there are multiple placeholders or mixed text, do string replacement
        resolved_text = text
        for match in reversed(matches):  # Process in reverse to maintain positions
            placeholder = match.group(1)
            value = self._get_placeholder_value(placeholder)
            if value is not None:
                # Convert value to string for insertion
                str_value = str(value) if not isinstance(value, str) else value
                resolved_text = resolved_text[:match.start()] + str_value + resolved_text[match.end():]
                print(f"[PlaceholderResolver] Replaced '{match.group(0)}' with '{str_value}'")
            else:
                print(f"[PlaceholderResolver] WARNING: Could not resolve placeholder '{match.group(0)}'")

        return resolved_text

    def _get_placeholder_value(self, placeholder: str) -> Optional[Any]:
        """
        Get the value for a placeholder

        Args:
            placeholder: The placeholder content (without {{ }})
                        Examples: "step_1", "step_1.id", "step_1.events.0.id"

        Returns:
            The resolved value or None if not found
        """
        parts = placeholder.split('.')
        step_id = parts[0]

        # Check if step output exists
        if step_id not in self._step_outputs:
            print(f"[PlaceholderResolver] Step '{step_id}' not found in outputs")
            return None

        value = self._step_outputs[step_id]

        # Navigate through nested fields
        for part in parts[1:]:
            if isinstance(value, dict):
                if part in value:
                    value = value[part]
                else:
                    print(f"[PlaceholderResolver] Field '{part}' not found in {value}")
                    return None
            elif isinstance(value, list):
                # Support array indexing like events.0
                try:
                    index = int(part)
                    if 0 <= index < len(value):
                        value = value[index]
                    else:
                        print(f"[PlaceholderResolver] Index {index} out of range for list of length {len(value)}")
                        return None
                except ValueError:
                    print(f"[PlaceholderResolver] Invalid list index: '{part}'")
                    return None
            else:
                print(f"[PlaceholderResolver] Cannot access field '{part}' on {type(value)}")
                return None

        return value

    def clear(self) -> None:
        """Clear all registered step outputs"""
        self._step_outputs.clear()
        print("[PlaceholderResolver] Cleared all step outputs")
