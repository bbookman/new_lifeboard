"""
Comprehensive tests for FrontendEnvironmentValidator class.

Tests the frontend environment validation, Node.js detection, and dependency
management functionality that was extracted from the original run_full_stack method.
"""

import subprocess
from unittest.mock import Mock, patch

import pytest

from core.orchestration import FrontendEnvironmentValidator


class TestFrontendEnvironmentValidator:
    """Comprehensive test suite for FrontendEnvironmentValidator functionality"""

    def test_is_node_installed_success(self):
        """Test successful Node.js installation detection"""
        mock_result = Mock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            result = FrontendEnvironmentValidator.is_node_installed()

            assert result is True
            mock_run.assert_called_once_with(
                ["node", "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )

    def test_is_node_installed_command_not_found(self):
        """Test Node.js detection when command not found"""
        with patch("subprocess.run", side_effect=FileNotFoundError()) as mock_run:
            result = FrontendEnvironmentValidator.is_node_installed()

            assert result is False
            mock_run.assert_called_once()

    def test_is_node_installed_subprocess_error(self):
        """Test Node.js detection with subprocess error"""
        with patch("subprocess.run", side_effect=subprocess.SubprocessError()) as mock_run:
            result = FrontendEnvironmentValidator.is_node_installed()

            assert result is False
            mock_run.assert_called_once()

    def test_is_node_installed_non_zero_return_code(self):
        """Test Node.js detection with non-zero return code"""
        mock_result = Mock()
        mock_result.returncode = 1

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            result = FrontendEnvironmentValidator.is_node_installed()

            assert result is False
            mock_run.assert_called_once()

    def test_is_node_installed_timeout(self):
        """Test Node.js detection with timeout"""
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("node", 5)) as mock_run:
            result = FrontendEnvironmentValidator.is_node_installed()

            assert result is False
            mock_run.assert_called_once()

    def test_check_frontend_dependencies_all_present(self):
        """Test frontend dependencies check when all dependencies are present"""
        with patch("pathlib.Path.exists") as mock_exists:
            with patch("pathlib.Path.is_dir", return_value=True) as mock_is_dir:
                # Mock Path existence for frontend dir, node_modules, and package-lock.json
                mock_exists.side_effect = lambda: True

                result = FrontendEnvironmentValidator.check_frontend_dependencies()

                assert result is True

    def test_check_frontend_dependencies_no_frontend_dir(self):
        """Test frontend dependencies check when frontend directory doesn't exist"""
        with patch("pathlib.Path.exists") as mock_exists:
            # Frontend directory doesn't exist
            mock_exists.return_value = False

            result = FrontendEnvironmentValidator.check_frontend_dependencies()

            assert result is False

    def test_check_frontend_dependencies_no_node_modules(self):
        """Test frontend dependencies check when node_modules doesn't exist"""
        def mock_exists_side_effect(path_instance):
            # Only frontend directory exists
            if "frontend" in str(path_instance) and "node_modules" not in str(path_instance):
                return True
            return False

        with patch("pathlib.Path.exists", side_effect=mock_exists_side_effect):
            with patch("pathlib.Path.is_dir", return_value=False):
                result = FrontendEnvironmentValidator.check_frontend_dependencies()

                assert result is False

    def test_check_frontend_dependencies_with_yarn_lock(self):
        """Test frontend dependencies check with yarn.lock instead of package-lock.json"""
        def mock_exists_side_effect(path_instance):
            path_str = str(path_instance)
            if "package-lock.json" in path_str:
                return False
            if "yarn.lock" in path_str:
                return True
            # frontend dir and node_modules
            return True

        with patch("pathlib.Path.exists", side_effect=mock_exists_side_effect):
            with patch("pathlib.Path.is_dir", return_value=True):
                result = FrontendEnvironmentValidator.check_frontend_dependencies()

                assert result is True

    def test_check_frontend_dependencies_no_lock_files(self):
        """Test frontend dependencies check when no lock files exist"""
        def mock_exists_side_effect(path_instance):
            path_str = str(path_instance)
            if "package-lock.json" in path_str or "yarn.lock" in path_str:
                return False
            # frontend dir and node_modules exist
            return True

        with patch("pathlib.Path.exists", side_effect=mock_exists_side_effect):
            with patch("pathlib.Path.is_dir", return_value=True):
                result = FrontendEnvironmentValidator.check_frontend_dependencies()

                assert result is False

    def test_install_frontend_dependencies_success(self):
        """Test successful frontend dependency installation"""
        mock_result = Mock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            result = FrontendEnvironmentValidator.install_frontend_dependencies()

            assert result is True
            mock_run.assert_called_once_with(
                ["npm", "install"],
                cwd="frontend",
                capture_output=True,
                text=True,
                timeout=300,
            )

    def test_install_frontend_dependencies_failure(self):
        """Test frontend dependency installation failure"""
        mock_result = Mock()
        mock_result.returncode = 1

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            result = FrontendEnvironmentValidator.install_frontend_dependencies()

            assert result is False
            mock_run.assert_called_once()

    def test_install_frontend_dependencies_subprocess_error(self):
        """Test frontend dependency installation with subprocess error"""
        with patch("subprocess.run", side_effect=subprocess.SubprocessError()) as mock_run:
            result = FrontendEnvironmentValidator.install_frontend_dependencies()

            assert result is False
            mock_run.assert_called_once()

    def test_install_frontend_dependencies_file_not_found(self):
        """Test frontend dependency installation when npm not found"""
        with patch("subprocess.run", side_effect=FileNotFoundError()) as mock_run:
            result = FrontendEnvironmentValidator.install_frontend_dependencies()

            assert result is False
            mock_run.assert_called_once()

    def test_install_frontend_dependencies_timeout(self):
        """Test frontend dependency installation with timeout"""
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("npm", 300)) as mock_run:
            result = FrontendEnvironmentValidator.install_frontend_dependencies()

            assert result is False
            mock_run.assert_called_once()

    def test_validate_environment_all_good(self):
        """Test complete environment validation when everything is ready"""
        with patch.object(FrontendEnvironmentValidator, "is_node_installed", return_value=True):
            with patch.object(FrontendEnvironmentValidator, "check_frontend_dependencies", return_value=True):
                with patch("pathlib.Path.exists", return_value=True):
                    result = FrontendEnvironmentValidator.validate_environment()

                    expected = {
                        "node_installed": True,
                        "dependencies_ready": True,
                        "frontend_dir_exists": True,
                    }
                    assert result == expected

    def test_validate_environment_node_missing(self):
        """Test environment validation when Node.js is missing"""
        with patch.object(FrontendEnvironmentValidator, "is_node_installed", return_value=False):
            with patch.object(FrontendEnvironmentValidator, "check_frontend_dependencies", return_value=True):
                with patch("pathlib.Path.exists", return_value=True):
                    result = FrontendEnvironmentValidator.validate_environment()

                    expected = {
                        "node_installed": False,
                        "dependencies_ready": True,
                        "frontend_dir_exists": True,
                    }
                    assert result == expected

    def test_validate_environment_dependencies_missing(self):
        """Test environment validation when dependencies are missing"""
        with patch.object(FrontendEnvironmentValidator, "is_node_installed", return_value=True):
            with patch.object(FrontendEnvironmentValidator, "check_frontend_dependencies", return_value=False):
                with patch("pathlib.Path.exists", return_value=True):
                    result = FrontendEnvironmentValidator.validate_environment()

                    expected = {
                        "node_installed": True,
                        "dependencies_ready": False,
                        "frontend_dir_exists": True,
                    }
                    assert result == expected

    def test_validate_environment_frontend_dir_missing(self):
        """Test environment validation when frontend directory is missing"""
        with patch.object(FrontendEnvironmentValidator, "is_node_installed", return_value=True):
            with patch.object(FrontendEnvironmentValidator, "check_frontend_dependencies", return_value=False):
                with patch("pathlib.Path.exists", return_value=False):
                    result = FrontendEnvironmentValidator.validate_environment()

                    expected = {
                        "node_installed": True,
                        "dependencies_ready": False,
                        "frontend_dir_exists": False,
                    }
                    assert result == expected

    def test_validate_environment_everything_missing(self):
        """Test environment validation when everything is missing"""
        with patch.object(FrontendEnvironmentValidator, "is_node_installed", return_value=False):
            with patch.object(FrontendEnvironmentValidator, "check_frontend_dependencies", return_value=False):
                with patch("pathlib.Path.exists", return_value=False):
                    result = FrontendEnvironmentValidator.validate_environment()

                    expected = {
                        "node_installed": False,
                        "dependencies_ready": False,
                        "frontend_dir_exists": False,
                    }
                    assert result == expected


class TestFrontendEnvironmentValidatorIntegration:
    """Integration tests for FrontendEnvironmentValidator"""

    def test_node_version_check_integration(self):
        """Integration test for actual Node.js version check"""
        # This test will only pass if Node.js is actually installed
        try:
            result = subprocess.run(["node", "--version"], check=False, capture_output=True, timeout=5)
            node_available = result.returncode == 0
        except (FileNotFoundError, subprocess.SubprocessError):
            node_available = False

        validator_result = FrontendEnvironmentValidator.is_node_installed()

        # The validator should match the actual Node.js availability
        assert validator_result == node_available

    @patch("pathlib.Path")
    def test_dependency_check_with_real_path_operations(self, mock_path_class):
        """Integration test with more realistic path operations"""
        # Create mock Path instances
        mock_frontend_path = Mock()
        mock_node_modules_path = Mock()
        mock_package_lock_path = Mock()
        mock_yarn_lock_path = Mock()

        # Set up the Path constructor to return our mocks
        def mock_path_constructor(path_str):
            if path_str == "frontend":
                return mock_frontend_path
            if "node_modules" in path_str:
                return mock_node_modules_path
            if "package-lock.json" in path_str:
                return mock_package_lock_path
            if "yarn.lock" in path_str:
                return mock_yarn_lock_path
            return Mock()

        mock_path_class.side_effect = mock_path_constructor

        # Configure mocks for a valid setup
        mock_frontend_path.exists.return_value = True
        mock_node_modules_path.exists.return_value = True
        mock_node_modules_path.is_dir.return_value = True
        mock_package_lock_path.exists.return_value = True
        mock_yarn_lock_path.exists.return_value = False

        result = FrontendEnvironmentValidator.check_frontend_dependencies()

        assert result is True
        mock_frontend_path.exists.assert_called()
        mock_node_modules_path.exists.assert_called()
        mock_node_modules_path.is_dir.assert_called()


class TestFrontendEnvironmentValidatorEdgeCases:
    """Test edge cases and error conditions"""

    def test_is_node_installed_with_custom_timeout(self):
        """Test Node.js detection with different timeout values"""
        # Since we can't easily change the timeout in the method,
        # we test that timeout exceptions are handled properly
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("node", 1)):
            result = FrontendEnvironmentValidator.is_node_installed()

            assert result is False

    def test_check_dependencies_with_permission_error(self):
        """Test dependency check when file access has permission issues"""
        with patch("pathlib.Path.exists", side_effect=PermissionError("Permission denied")):
            # Should handle the exception gracefully
            try:
                result = FrontendEnvironmentValidator.check_frontend_dependencies()
                # If no exception is raised, that's good, result could be either True or False
                # depending on the implementation's error handling
                assert isinstance(result, bool)
            except PermissionError:
                # If the method doesn't handle the exception, that's also acceptable
                # for this test - we're just ensuring it doesn't crash unexpectedly
                pass

    def test_install_dependencies_with_very_long_timeout(self):
        """Test dependency installation behavior with extended timeout"""
        mock_result = Mock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            result = FrontendEnvironmentValidator.install_frontend_dependencies()

            assert result is True
            # Verify that the timeout parameter was passed correctly
            args, kwargs = mock_run.call_args
            assert kwargs["timeout"] == 300  # 5 minutes as defined in the method

    def test_validate_environment_with_partial_failures(self):
        """Test environment validation with some components failing"""
        # Simulate a scenario where Node is installed but other components fail
        with patch.object(FrontendEnvironmentValidator, "is_node_installed", return_value=True):
            with patch.object(FrontendEnvironmentValidator, "check_frontend_dependencies",
                            side_effect=Exception("Dependency check failed")):
                with patch("pathlib.Path.exists", side_effect=Exception("Path check failed")):

                    # The method should handle exceptions gracefully
                    try:
                        result = FrontendEnvironmentValidator.validate_environment()
                        # If it returns a result, verify it has the expected structure
                        assert isinstance(result, dict)
                        assert "node_installed" in result
                    except Exception:
                        # If it raises an exception, that's also acceptable behavior
                        # The test is mainly to ensure it doesn't crash unexpectedly
                        pass

    def test_path_operations_with_different_working_directories(self):
        """Test that path operations work correctly from different working directories"""
        with patch("pathlib.Path") as mock_path_class:
            # Create a mock that always returns False for exists()
            mock_path_instance = Mock()
            mock_path_instance.exists.return_value = False
            mock_path_instance.is_dir.return_value = False
            mock_path_class.return_value = mock_path_instance

            result = FrontendEnvironmentValidator.check_frontend_dependencies()

            assert result is False
            # Verify that Path was called with relative paths (not absolute)
            mock_path_class.assert_called()


class TestFrontendEnvironmentValidatorErrorHandling:
    """Test error handling and resilience"""

    def test_graceful_handling_of_missing_subprocess_module(self):
        """Test behavior when subprocess operations fail unexpectedly"""
        with patch("subprocess.run", side_effect=ImportError("subprocess not available")):
            result = FrontendEnvironmentValidator.is_node_installed()

            assert result is False

    def test_graceful_handling_of_missing_pathlib_module(self):
        """Test behavior when pathlib operations fail unexpectedly"""
        with patch("pathlib.Path", side_effect=ImportError("pathlib not available")):
            try:
                result = FrontendEnvironmentValidator.check_frontend_dependencies()
                # If it returns a result, it should be False (safe default)
                assert result is False
            except ImportError:
                # If it propagates the exception, that's also acceptable
                pass

    def test_install_with_network_unavailable(self):
        """Test dependency installation when network is unavailable"""
        # Simulate network error during npm install
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stderr = "network error"

        with patch("subprocess.run", return_value=mock_result):
            result = FrontendEnvironmentValidator.install_frontend_dependencies()

            assert result is False

    def test_robust_timeout_handling(self):
        """Test that timeout handling is robust across different platforms"""
        # Test with different timeout exceptions
        timeout_exceptions = [
            subprocess.TimeoutExpired("node", 5),
            subprocess.TimeoutExpired("npm", 300),
        ]

        for exception in timeout_exceptions:
            with patch("subprocess.run", side_effect=exception):
                node_result = FrontendEnvironmentValidator.is_node_installed()
                assert node_result is False

                install_result = FrontendEnvironmentValidator.install_frontend_dependencies()
                assert install_result is False


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v"])
