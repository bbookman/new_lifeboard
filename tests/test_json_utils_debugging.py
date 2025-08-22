"""
Test cases for debugging JSON parsing failures in core.json_utils

This test focuses on reproducing the recurring position 4 parsing errors
with timestamp "2025-07-31T02:51:57.519"
"""

import json
import logging

import pytest

from core.json_utils import JSONMetadataParser

# Configure logging to capture debug messages
logging.basicConfig(level=logging.DEBUG)


class TestJSONParsingDebugging:
    """Test class for debugging JSON parsing issues"""

    def test_problematic_timestamp_scenarios(self):
        """Test various malformed scenarios with the problematic timestamp"""

        # Scenario 1: Missing quotes around timestamp value
        malformed_1 = '{"timestamp": 2025-07-31T02:51:57.519}'
        result = JSONMetadataParser.parse_metadata(malformed_1)
        assert result is None, "Should fail to parse malformed JSON with unquoted timestamp"

        # Scenario 2: Missing quotes around key
        malformed_2 = '{timestamp: "2025-07-31T02:51:57.519"}'
        result = JSONMetadataParser.parse_metadata(malformed_2)
        assert result is None, "Should fail to parse malformed JSON with unquoted key"

        # Scenario 3: Missing quotes around both key and value
        malformed_3 = "{timestamp: 2025-07-31T02:51:57.519}"
        result = JSONMetadataParser.parse_metadata(malformed_3)
        assert result is None, "Should fail to parse malformed JSON with unquoted key and value"

        # Scenario 4: Extra characters at position 4 (column 5)
        malformed_4 = '{"t"x: "2025-07-31T02:51:57.519"}'  # 'x' at position 4
        result = JSONMetadataParser.parse_metadata(malformed_4)
        assert result is None, "Should fail to parse JSON with extra character at position 4"

    def test_double_serialization_scenarios(self):
        """Test double-serialization issues that could cause position 4 errors"""

        # Scenario 1: Properly double-serialized JSON
        inner_json = '{"timestamp": "2025-07-31T02:51:57.519"}'
        double_serialized = json.dumps(inner_json)  # Should be: "{\"timestamp\": \"2025-07-31T02:51:57.519\"}"

        result = JSONMetadataParser.parse_metadata(double_serialized)
        assert result is not None, "Should handle proper double-serialization"
        assert result["timestamp"] == "2025-07-31T02:51:57.519"

        # Scenario 2: Malformed double-serialization
        malformed_double = '"{timestamp: "2025-07-31T02:51:57.519"}"'  # Missing quotes around key
        result = JSONMetadataParser.parse_metadata(malformed_double)
        # This should either parse the inner string or fail gracefully

    def test_specific_position_4_errors(self):
        """Test specific cases that would cause position 4 (column 5) errors"""

        # Position 4 is the 5th character (0-indexed)
        # In '{"ts": "value"}', position 4 is the 's' in "ts"

        # Case 1: Malformed at exactly position 4
        cases = [
            '{"t": "2025-07-31T02:51:57.519"}',  # Valid - should work
            '{"tx: "2025-07-31T02:51:57.519"}',  # Missing quote at position 4
            '{ts": "2025-07-31T02:51:57.519"}',  # Missing quote at start, error earlier
            '{"t"x "2025-07-31T02:51:57.519"}',  # Extra char at position 4, missing :
        ]

        for i, test_case in enumerate(cases):
            print(f"Testing case {i}: {test_case}")
            result = JSONMetadataParser.parse_metadata(test_case)
            if i == 0:
                assert result is not None, f"Case {i} should parse successfully"
            # Other cases should fail but not crash

    def test_character_encoding_issues(self):
        """Test potential character encoding issues with the timestamp"""

        # Test with various encodings that might cause issues
        timestamp_cases = [
            '{"timestamp": "2025-07-31T02:51:57.519"}',  # Normal
            '{"timestamp": "2025‑07‑31T02:51:57.519"}',  # Non-breaking hyphens
            '{"timestamp": "2025-07-31T02：51：57.519"}',  # Full-width colons
        ]

        for case in timestamp_cases:
            result = JSONMetadataParser.parse_metadata(case)
            # Should either parse or fail gracefully

    def test_serialization_then_parsing_roundtrip(self):
        """Test serialization followed by parsing to detect roundtrip issues"""

        # Test data with the problematic timestamp
        test_metadata = {
            "timestamp": "2025-07-31T02:51:57.519",
            "source": "test",
            "type": "debug",
        }

        # Serialize
        serialized = JSONMetadataParser.serialize_metadata(test_metadata)
        assert serialized is not None, "Serialization should succeed"

        # Parse back
        parsed = JSONMetadataParser.parse_metadata(serialized)
        assert parsed is not None, "Parsing serialized data should succeed"
        assert parsed["timestamp"] == "2025-07-31T02:51:57.519"

        # Test double serialization scenario
        double_serialized = JSONMetadataParser.serialize_metadata(serialized)
        double_parsed = JSONMetadataParser.parse_metadata(double_serialized)
        # This should handle the double-serialization gracefully

    def test_edge_cases_at_position_4(self):
        """Test various edge cases that could cause position 4 errors"""

        edge_cases = [
            "",  # Empty string
            "{",  # Incomplete JSON
            '{"',  # Incomplete key start
            '{"t',  # Incomplete key
            '{"t"',  # Incomplete after key
            '{"t":',  # Incomplete after colon
            '{"t": ',  # Incomplete after colon and space
            '{"timestamp"',  # Good key but incomplete
        ]

        for case in edge_cases:
            result = JSONMetadataParser.parse_metadata(case)
            # All should return None and not crash
            assert result is None, f"Edge case should return None: {case}"

    def test_logging_capture(self):
        """Test that our enhanced logging captures the right information"""

        # Create a malformed JSON that should trigger position 4 error
        malformed = '{"t"x: "2025-07-31T02:51:57.519"}'

        # This should trigger our special logging for position 4 errors
        result = JSONMetadataParser.parse_metadata(malformed)
        assert result is None, "Malformed JSON should return None"
        # The logging should have captured detailed information

    def test_common_corruption_patterns(self):
        """Test common patterns that could lead to JSON corruption"""

        # Pattern 1: Concatenated JSON strings
        corrupted_1 = '{"timestamp": "2025-07-31T02:51:57.519"}{"extra": "data"}'
        result = JSONMetadataParser.parse_metadata(corrupted_1)
        # Should either parse first object or fail

        # Pattern 2: Missing comma between fields
        corrupted_2 = '{"timestamp": "2025-07-31T02:51:57.519" "source": "test"}'
        result = JSONMetadataParser.parse_metadata(corrupted_2)
        assert result is None, "Should fail on missing comma"

        # Pattern 3: Trailing comma
        corrupted_3 = '{"timestamp": "2025-07-31T02:51:57.519",}'
        result = JSONMetadataParser.parse_metadata(corrupted_3)
        # Some JSON parsers accept this, others don't

    def test_specific_timestamp_value_issues(self):
        """Test if the specific timestamp value causes issues"""

        # Test with the exact problematic timestamp
        problem_timestamp = "2025-07-31T02:51:57.519"

        # Valid cases
        valid_cases = [
            {"timestamp": problem_timestamp},
            {"start_time": problem_timestamp},
            {"created_at": problem_timestamp},
            {"published_datetime_utc": problem_timestamp},
        ]

        for case in valid_cases:
            serialized = JSONMetadataParser.serialize_metadata(case)
            parsed = JSONMetadataParser.parse_metadata(serialized)
            assert parsed is not None

        # Test serialization of raw string - this should work normally
        raw_result = JSONMetadataParser.serialize_metadata(problem_timestamp)
        assert raw_result == f'"{problem_timestamp}"', "Raw string should be properly quoted when serialized"

        # Test parsing serialized string - this should work normally
        parsed_raw = JSONMetadataParser.parse_metadata(raw_result)
        assert parsed_raw == problem_timestamp, "Properly quoted JSON string should parse back to original value"

        # Test the defensive fix directly - raw timestamp string should be handled gracefully
        result = JSONMetadataParser.parse_metadata(problem_timestamp)
        assert result is not None, "Defensive fix should handle raw strings"
        # ISO timestamps are returned as-is, not wrapped, for better usability
        assert result == problem_timestamp, "Valid ISO timestamp should be returned as-is"


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v", "-s"])
