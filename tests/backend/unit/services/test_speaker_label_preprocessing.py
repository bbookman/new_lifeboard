"""
Test speaker label preprocessing functionality
"""

import pytest
from unittest.mock import Mock
from services.speaker_labeling_service import SpeakerLabelingService
from core.database import DatabaseService
from config.models import AppConfig


class TestSpeakerLabelPreprocessing:
    """Test the speaker label preprocessing feature"""

    @pytest.fixture
    def speaker_service(self):
        """Create a SpeakerLabelingService instance for testing"""
        mock_db = Mock(spec=DatabaseService)
        mock_config = Mock(spec=AppConfig)
        return SpeakerLabelingService(database=mock_db, config=mock_config)

    def test_preprocess_replaces_you_with_bruce(self, speaker_service):
        """Test that 'You' speaker labels are replaced with 'Bruce'"""
        input_content = "- You (10/17/25 10:19 AM): Been thinking about work and upcoming projects."
        expected_output = "- Bruce (10/17/25 10:19 AM): Been thinking about work and upcoming projects."

        result = speaker_service._preprocess_speaker_labels(input_content)

        assert result == expected_output

    def test_preprocess_multiple_you_labels(self, speaker_service):
        """Test that multiple 'You' labels are all replaced"""
        input_content = """- You (10/17/25 10:19 AM): First message.
- Unknown (10/17/25 10:20 AM): Response.
- You (10/17/25 10:21 AM): Second message."""

        expected_output = """- Bruce (10/17/25 10:19 AM): First message.
- Unknown (10/17/25 10:20 AM): Response.
- Bruce (10/17/25 10:21 AM): Second message."""

        result = speaker_service._preprocess_speaker_labels(input_content)

        assert result == expected_output

    def test_preprocess_preserves_lowercase_you(self, speaker_service):
        """Test that lowercase 'you' in conversation text is NOT replaced"""
        input_content = "- You (10/17/25 10:19 AM): How are you doing today?"
        expected_output = "- Bruce (10/17/25 10:19 AM): How are you doing today?"

        result = speaker_service._preprocess_speaker_labels(input_content)

        assert result == expected_output
        # Verify "you" in the text remains unchanged
        assert "you doing" in result

    def test_preprocess_only_replaces_speaker_label_position(self, speaker_service):
        """Test that only 'You' in speaker label position is replaced"""
        input_content = "- You (10/17/25 10:19 AM): You should check this out."
        # Only the first 'You' (speaker label) should be replaced, not "You should"
        expected_output = "- Bruce (10/17/25 10:19 AM): You should check this out."

        result = speaker_service._preprocess_speaker_labels(input_content)

        assert result == expected_output

    def test_preprocess_preserves_other_speakers(self, speaker_service):
        """Test that other speaker names are not affected"""
        input_content = """- You (10/17/25 10:19 AM): Hello.
- Alice (10/17/25 10:20 AM): Hi there.
- Unknown (10/17/25 10:21 AM): Hey."""

        expected_output = """- Bruce (10/17/25 10:19 AM): Hello.
- Alice (10/17/25 10:20 AM): Hi there.
- Unknown (10/17/25 10:21 AM): Hey."""

        result = speaker_service._preprocess_speaker_labels(input_content)

        assert result == expected_output

    def test_preprocess_empty_content(self, speaker_service):
        """Test that empty content is handled gracefully"""
        result = speaker_service._preprocess_speaker_labels("")

        assert result == ""

    def test_preprocess_no_speaker_labels(self, speaker_service):
        """Test content without speaker labels is unchanged"""
        input_content = "Just some regular text without any speaker labels."
        expected_output = input_content

        result = speaker_service._preprocess_speaker_labels(input_content)

        assert result == expected_output

    def test_preprocess_case_sensitive(self, speaker_service):
        """Test that replacement is case-sensitive (only 'You', not 'YOU' or 'you')"""
        input_content = """- You (10/17/25 10:19 AM): Normal case.
- you (10/17/25 10:20 AM): Lowercase should not be replaced.
- YOU (10/17/25 10:21 AM): Uppercase should not be replaced."""

        # Only 'You' with capital Y should be replaced
        result = speaker_service._preprocess_speaker_labels(input_content)

        assert "- Bruce (10/17/25 10:19 AM): Normal case." in result
        assert "- you (10/17/25 10:20 AM):" in result  # Unchanged
        assert "- YOU (10/17/25 10:21 AM):" in result  # Unchanged
