"""
Configuration validation utilities to eliminate duplication across config classes.

This module provides centralized validation functions and decorators that can be
shared across all configuration classes, reducing code duplication and ensuring
consistent validation behavior.
"""

from typing import Any, Callable, List, Optional, Set

from pydantic import field_validator


class ConfigValidationError(ValueError):
    """Raised when configuration validation fails"""


class APIKeyValidator:
    """Centralized API key validation utilities"""

    # Common placeholder patterns that indicate unconfigured keys
    PLACEHOLDER_PATTERNS = {
        "your_api_key_here",
        "your-api-key-here",
        "your_rapid_api_key_here",
        "your-rapid-api-key-here",
        "placeholder_key_here",
        "change_me",
        "insert_key_here",
        "test_key",
        "demo_key",
    }

    @staticmethod
    def validate_api_key_format(api_key: Optional[str], field_name: str = "API key") -> Optional[str]:
        """
        Validate API key format (type checking only).
        
        Args:
            api_key: The API key to validate
            field_name: Name of the field for error messages
            
        Returns:
            The validated API key
            
        Raises:
            ConfigValidationError: If API key format is invalid
        """
        if api_key is not None and not isinstance(api_key, str):
            raise ConfigValidationError(f"{field_name} must be a string")
        return api_key

    @staticmethod
    def is_api_key_configured(api_key: Optional[str],
                             additional_placeholders: Optional[Set[str]] = None) -> bool:
        """
        Check if API key is properly configured (not a placeholder).
        
        Args:
            api_key: The API key to check
            additional_placeholders: Additional placeholder patterns to check
            
        Returns:
            True if API key appears to be configured, False otherwise
        """
        if not api_key or not isinstance(api_key, str):
            return False

        # Check if key is empty or whitespace only
        if not api_key.strip():
            return False

        # Combine default and additional placeholders
        placeholders = APIKeyValidator.PLACEHOLDER_PATTERNS.copy()
        if additional_placeholders:
            placeholders.update(additional_placeholders)

        # Check against known placeholder patterns (case-insensitive)
        api_key_lower = api_key.lower().strip()
        return api_key_lower not in {p.lower() for p in placeholders}

    @classmethod
    def create_api_key_validator(cls,
                                field_name: str = "API key",
                                additional_placeholders: Optional[Set[str]] = None) -> Callable:
        """
        Create a Pydantic field validator for API keys.
        
        Args:
            field_name: Name of the field for error messages
            additional_placeholders: Additional placeholder patterns to check
            
        Returns:
            A Pydantic field validator function
        """
        def validator(v):
            return cls.validate_api_key_format(v, field_name)
        return validator


class StringValidator:
    """Centralized string validation utilities"""

    @staticmethod
    def validate_non_empty_string(value: Any, field_name: str) -> str:
        """
        Validate that a value is a non-empty string.
        
        Args:
            value: The value to validate
            field_name: Name of the field for error messages
            
        Returns:
            The validated string
            
        Raises:
            ConfigValidationError: If value is not a non-empty string
        """
        if not value or not isinstance(value, str):
            raise ConfigValidationError(f"{field_name} must be a non-empty string")
        return value

    @staticmethod
    def validate_string_choices(value: str,
                               choices: List[str],
                               field_name: str,
                               case_sensitive: bool = True) -> str:
        """
        Validate that a string value is one of the allowed choices.
        
        Args:
            value: The value to validate
            choices: List of allowed choices
            field_name: Name of the field for error messages
            case_sensitive: Whether comparison should be case-sensitive
            
        Returns:
            The validated string
            
        Raises:
            ConfigValidationError: If value is not in choices
        """
        if not case_sensitive:
            value_check = value.lower()
            choices_check = [c.lower() for c in choices]
        else:
            value_check = value
            choices_check = choices

        if value_check not in choices_check:
            choices_str = ", ".join(choices)
            raise ConfigValidationError(f"{field_name} must be one of: {choices_str}")

        return value

    @staticmethod
    def validate_no_special_chars(value: str,
                                 field_name: str,
                                 forbidden_chars: Set[str] = None) -> str:
        """
        Validate that a string doesn't contain forbidden characters.
        
        Args:
            value: The value to validate
            field_name: Name of the field for error messages
            forbidden_chars: Set of forbidden characters (default: {':'})
            
        Returns:
            The validated string
            
        Raises:
            ConfigValidationError: If value contains forbidden characters
        """
        if forbidden_chars is None:
            forbidden_chars = {":"}

        found_chars = forbidden_chars.intersection(set(value))
        if found_chars:
            chars_str = "', '".join(found_chars)
            raise ConfigValidationError(f"{field_name} cannot contain: '{chars_str}'")

        return value


class NumericValidator:
    """Centralized numeric validation utilities"""

    @staticmethod
    def validate_positive_int(value: int, field_name: str) -> int:
        """
        Validate that a value is a positive integer.
        
        Args:
            value: The value to validate
            field_name: Name of the field for error messages
            
        Returns:
            The validated integer
            
        Raises:
            ConfigValidationError: If value is not positive
        """
        if value <= 0:
            raise ConfigValidationError(f"{field_name} must be positive")
        return value

    @staticmethod
    def validate_positive_float(value: float, field_name: str) -> float:
        """
        Validate that a value is a positive float.
        
        Args:
            value: The value to validate
            field_name: Name of the field for error messages
            
        Returns:
            The validated float
            
        Raises:
            ConfigValidationError: If value is not positive
        """
        if value <= 0.0:
            raise ConfigValidationError(f"{field_name} must be positive")
        return value

    @staticmethod
    def validate_range(value: float,
                      min_val: Optional[float] = None,
                      max_val: Optional[float] = None,
                      field_name: str = "Value") -> float:
        """
        Validate that a value is within a specified range.
        
        Args:
            value: The value to validate
            min_val: Minimum allowed value (inclusive)
            max_val: Maximum allowed value (inclusive)
            field_name: Name of the field for error messages
            
        Returns:
            The validated value
            
        Raises:
            ConfigValidationError: If value is out of range
        """
        if min_val is not None and value < min_val:
            raise ConfigValidationError(f"{field_name} must be >= {min_val}")
        if max_val is not None and value > max_val:
            raise ConfigValidationError(f"{field_name} must be <= {max_val}")
        return value


class PathValidator:
    """Centralized path validation utilities"""

    @staticmethod
    def validate_path_string(path: Any, field_name: str) -> str:
        """
        Validate that a value is a valid path string.
        
        Args:
            path: The path to validate
            field_name: Name of the field for error messages
            
        Returns:
            The validated path
            
        Raises:
            ConfigValidationError: If path is not valid
        """
        if not path or not isinstance(path, str):
            raise ConfigValidationError(f"{field_name} must be a non-empty string")
        return path


# Factory functions for creating common validator combinations
def create_api_key_field_validator(field_name: str = "API key",
                                  additional_placeholders: Optional[Set[str]] = None):
    """Create a field validator for API keys with Pydantic"""
    validator_func = APIKeyValidator.create_api_key_validator(field_name, additional_placeholders)

    @field_validator(mode="before")
    @classmethod
    def validate(cls, v):
        return validator_func(v)

    return validate


def create_choice_field_validator(choices: List[str],
                                 field_name: str,
                                 case_sensitive: bool = True):
    """Create a field validator for string choices with Pydantic"""

    @field_validator(mode="before")
    @classmethod
    def validate(cls, v):
        return StringValidator.validate_string_choices(v, choices, field_name, case_sensitive)

    return validate


def create_positive_int_validator(field_name: str):
    """Create a field validator for positive integers with Pydantic"""

    @field_validator(mode="before")
    @classmethod
    def validate(cls, v):
        return NumericValidator.validate_positive_int(v, field_name)

    return validate


# Configuration mixin that provides common validation methods
class BaseConfigMixin:
    """
    Mixin providing common configuration validation methods.
    
    Can be inherited by configuration classes to provide standardized
    validation behavior.
    """

    def is_api_key_configured(self,
                             api_key: Optional[str] = None,
                             additional_placeholders: Optional[Set[str]] = None) -> bool:
        """
        Check if API key is properly configured.
        
        Args:
            api_key: API key to check (defaults to self.api_key)
            additional_placeholders: Additional placeholder patterns
            
        Returns:
            True if API key appears to be configured
        """
        if api_key is None and hasattr(self, "api_key"):
            api_key = self.api_key

        return APIKeyValidator.is_api_key_configured(api_key, additional_placeholders)
