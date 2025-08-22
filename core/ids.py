import uuid
from typing import Tuple


class NamespacedIDManager:
    """Manages namespaced IDs for data items across different sources"""

    @staticmethod
    def create_id(namespace: str, source_id: str = None) -> str:
        """Create namespaced ID: namespace:source_id"""
        if source_id is None:
            source_id = str(uuid.uuid4())
        return f"{namespace}:{source_id}"

    @staticmethod
    def parse_id(namespaced_id: str) -> Tuple[str, str]:
        """Parse namespaced ID into (namespace, source_id)"""
        parts = namespaced_id.split(":", 1)
        if len(parts) != 2:
            raise ValueError(f"Invalid namespaced ID: {namespaced_id}")
        return parts[0], parts[1]

    @staticmethod
    def get_namespace(namespaced_id: str) -> str:
        """Extract namespace from namespaced ID"""
        namespace, _ = NamespacedIDManager.parse_id(namespaced_id)
        return namespace

    @staticmethod
    def get_source_id(namespaced_id: str) -> str:
        """Extract source_id from namespaced ID"""
        _, source_id = NamespacedIDManager.parse_id(namespaced_id)
        return source_id

    @staticmethod
    def is_valid_id(namespaced_id: str) -> bool:
        """Check if a string is a valid namespaced ID"""
        try:
            NamespacedIDManager.parse_id(namespaced_id)
            return True
        except ValueError:
            return False

    @staticmethod
    def filter_by_namespace(ids: list[str], namespace: str) -> list[str]:
        """Filter list of namespaced IDs by namespace"""
        return [id for id in ids if NamespacedIDManager.get_namespace(id) == namespace]

    @staticmethod
    def group_by_namespace(ids: list[str]) -> dict[str, list[str]]:
        """Group namespaced IDs by their namespace"""
        groups = {}
        for id in ids:
            try:
                namespace = NamespacedIDManager.get_namespace(id)
                if namespace not in groups:
                    groups[namespace] = []
                groups[namespace].append(id)
            except ValueError:
                # Skip invalid IDs
                continue
        return groups

    @staticmethod
    def validate_namespace(namespace: str) -> bool:
        """Validate namespace format (no colons, not empty)"""
        return isinstance(namespace, str) and len(namespace) > 0 and ":" not in namespace

    @staticmethod
    def normalize_namespace(namespace: str) -> str:
        """Normalize namespace to lowercase and replace invalid characters"""
        if not isinstance(namespace, str):
            raise ValueError("Namespace must be a string")

        # Convert to lowercase and replace invalid characters
        normalized = namespace.lower().strip()
        normalized = normalized.replace(":", "_").replace(" ", "_")

        if not normalized:
            raise ValueError("Namespace cannot be empty after normalization")

        return normalized
