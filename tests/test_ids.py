import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import pytest
from core.ids import NamespacedIDManager

def test_create_id():
    assert NamespacedIDManager.create_id("test", "123") == "test:123"
    assert NamespacedIDManager.create_id("test") is not None

def test_parse_id():
    assert NamespacedIDManager.parse_id("test:123") == ("test", "123")
    with pytest.raises(ValueError):
        NamespacedIDManager.parse_id("test123")

def test_get_namespace():
    assert NamespacedIDManager.get_namespace("test:123") == "test"

def test_get_source_id():
    assert NamespacedIDManager.get_source_id("test:123") == "123"

def test_is_valid_id():
    assert NamespacedIDManager.is_valid_id("test:123") is True
    assert NamespacedIDManager.is_valid_id("test123") is False

def test_filter_by_namespace():
    ids = ["test:123", "other:456", "test:789"]
    assert NamespacedIDManager.filter_by_namespace(ids, "test") == ["test:123", "test:789"]

def test_group_by_namespace():
    ids = ["test:123", "other:456", "test:789"]
    assert NamespacedIDManager.group_by_namespace(ids) == {
        "test": ["test:123", "test:789"],
        "other": ["other:456"]
    }

def test_validate_namespace():
    assert NamespacedIDManager.validate_namespace("test") is True
    assert NamespacedIDManager.validate_namespace("test:123") is False
    assert NamespacedIDManager.validate_namespace("") is False

def test_normalize_namespace():
    assert NamespacedIDManager.normalize_namespace("Test Namespace") == "test_namespace"
    assert NamespacedIDManager.normalize_namespace("test:namespace") == "test_namespace"
