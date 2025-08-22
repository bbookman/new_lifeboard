"""
Template Processing Service for Prompt Variable Resolution

This service handles parsing and resolving template variables in prompts,
allowing users to insert dynamic data from various sources with different time ranges.

Template Format: {{SOURCE_TIMERANGE}}
Examples: {{LIMITLESS_DAY}}, {{TWITTER_WEEK}}, {{NEWS_MONTH}}
"""

import hashlib
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import pytz

from config.models import AppConfig
from core.base_service import BaseService
from core.database import DatabaseService

logger = logging.getLogger(__name__)


@dataclass
class TemplateVariable:
    """Represents a parsed template variable"""
    original_text: str
    source: str
    time_range: str
    full_match: str


@dataclass
class ResolvedTemplate:
    """Represents a template with resolved variables"""
    original_content: str
    resolved_content: str
    variables_resolved: int
    errors: List[str]


class TemplateProcessor(BaseService):
    """Service for processing template variables in prompts"""

    # Regex pattern for template variables: {{SOURCE_TIMERANGE}}
    TEMPLATE_PATTERN = re.compile(r"\{\{([A-Z_]+)_([A-Z]+)\}\}")

    # Supported sources (extensible via configuration)
    DEFAULT_SOURCES = {
        "limitless": "LIMITLESS",
        "twitter": "TWITTER",
        "news": "NEWS",
    }

    # Supported time ranges
    TIME_RANGES = ["DAY", "WEEK", "MONTH"]

    def __init__(self,
                 database: DatabaseService,
                 config: AppConfig,
                 timezone: str = "America/New_York",
                 cache_enabled: bool = True,
                 cache_ttl_hours: int = 1):
        super().__init__(service_name="TemplateProcessor", config=config)
        self.database = database
        self.timezone = timezone
        self.sources = self.DEFAULT_SOURCES.copy()
        self.cache_enabled = cache_enabled
        self.cache_ttl_hours = cache_ttl_hours

    async def _initialize_service(self) -> bool:
        """Initialize the template processor service"""
        try:
            self.logger.info("TemplateProcessor service initialized successfully")
            return True
        except Exception as e:
            self.logger.error(f"Failed to initialize TemplateProcessor: {e}")
            return False

    def _generate_template_hash(self, content: str, target_date: str) -> str:
        """Generate a hash for template caching"""
        cache_key = f"{content}|{target_date}"
        return hashlib.md5(cache_key.encode()).hexdigest()

    def _get_cached_result(self, template_hash: str) -> Optional[str]:
        """Get cached template result if available and not expired"""
        if not self.cache_enabled:
            return None

        try:
            with self.database.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT resolved_content FROM template_cache 
                    WHERE template_hash = ? AND expires_at > CURRENT_TIMESTAMP
                """, (template_hash,))

                row = cursor.fetchone()
                if row:
                    logger.debug(f"Cache hit for template hash: {template_hash}")
                    return row["resolved_content"]

        except Exception as e:
            logger.warning(f"Error retrieving from template cache: {e}")

        return None

    def _cache_result(self, template_hash: str, content: str, target_date: str,
                     resolved_content: str, variables_resolved: int) -> None:
        """Cache template result"""
        if not self.cache_enabled:
            return

        try:
            # Calculate expiration time
            expires_at = datetime.now(timezone.utc) + timedelta(hours=self.cache_ttl_hours)

            # Generate content hash for additional validation
            content_hash = hashlib.md5(content.encode()).hexdigest()

            with self.database.get_connection() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO template_cache 
                    (id, template_hash, content_hash, target_date, resolved_content, 
                     variables_resolved, created_at, expires_at)
                    VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
                """, (
                    template_hash,  # Use hash as ID for simplicity
                    template_hash,
                    content_hash,
                    target_date,
                    resolved_content,
                    variables_resolved,
                    expires_at.isoformat(),
                ))
                conn.commit()

            logger.debug(f"Cached template result: {template_hash}")

        except Exception as e:
            logger.warning(f"Error caching template result: {e}")

    def _cleanup_expired_cache(self) -> None:
        """Remove expired cache entries"""
        try:
            with self.database.get_connection() as conn:
                cursor = conn.execute("""
                    DELETE FROM template_cache 
                    WHERE expires_at <= CURRENT_TIMESTAMP
                """)

                deleted_count = cursor.rowcount
                if deleted_count > 0:
                    logger.debug(f"Cleaned up {deleted_count} expired cache entries")

                conn.commit()

        except Exception as e:
            logger.warning(f"Error cleaning up template cache: {e}")

    def parse_template_variables(self, content: str) -> List[TemplateVariable]:
        """
        Parse template variables from content text
        
        Args:
            content: The content containing template variables
            
        Returns:
            List of parsed TemplateVariable objects
        """
        variables = []

        for match in self.TEMPLATE_PATTERN.finditer(content):
            full_match = match.group(0)  # {{LIMITLESS_DAY}}
            source = match.group(1)      # LIMITLESS
            time_range = match.group(2)  # DAY

            # Validate time range
            if time_range not in self.TIME_RANGES:
                logger.warning(f"Unknown time range '{time_range}' in template variable '{full_match}'")
                continue

            # Validate source
            source_namespace = self._get_namespace_for_source(source)
            if not source_namespace:
                logger.warning(f"Unknown source '{source}' in template variable '{full_match}'")
                continue

            variables.append(TemplateVariable(
                original_text=full_match,
                source=source,
                time_range=time_range,
                full_match=full_match,
            ))

        return variables

    def resolve_template(self, content: str, target_date: Optional[str] = None) -> ResolvedTemplate:
        """
        Resolve all template variables in content
        
        Args:
            content: The content containing template variables
            target_date: The target date for resolution (defaults to today)
            
        Returns:
            ResolvedTemplate object with resolved content and metadata
        """
        if target_date is None:
            target_date = self._get_current_date()

        # Check cache first
        template_hash = self._generate_template_hash(content, target_date)
        cached_result = self._get_cached_result(template_hash)

        if cached_result:
            # Return cached result
            variables = self.parse_template_variables(content)
            return ResolvedTemplate(
                original_content=content,
                resolved_content=cached_result,
                variables_resolved=len(variables),  # Assume all were resolved from cache
                errors=[],
            )

        # Clean up expired cache entries periodically (10% chance)
        if self.cache_enabled and hash(template_hash) % 10 == 0:
            self._cleanup_expired_cache()

        variables = self.parse_template_variables(content)
        resolved_content = content
        variables_resolved = 0
        errors = []

        for var in variables:
            try:
                resolved_data = self._resolve_variable(var, target_date)
                resolved_content = resolved_content.replace(var.full_match, resolved_data)
                variables_resolved += 1
                logger.debug(f"Resolved template variable: {var.full_match}")

            except Exception as e:
                error_msg = f"Failed to resolve {var.full_match}: {e!s}"
                errors.append(error_msg)
                logger.error(error_msg)

                # Replace with error placeholder
                placeholder = f"[Error resolving {var.full_match}]"
                resolved_content = resolved_content.replace(var.full_match, placeholder)

        # Cache the result if no errors occurred
        if not errors and variables_resolved > 0:
            self._cache_result(template_hash, content, target_date, resolved_content, variables_resolved)

        return ResolvedTemplate(
            original_content=content,
            resolved_content=resolved_content,
            variables_resolved=variables_resolved,
            errors=errors,
        )

    def _resolve_variable(self, variable: TemplateVariable, target_date: str) -> str:
        """
        Resolve a single template variable to its data
        
        Args:
            variable: The TemplateVariable to resolve
            target_date: The target date for data retrieval
            
        Returns:
            Formatted string containing the resolved data
        """
        namespace = self._get_namespace_for_source(variable.source)
        if not namespace:
            raise ValueError(f"Unknown source: {variable.source}")

        date_range = self._calculate_date_range(variable.time_range, target_date)

        if variable.time_range == "DAY":
            data_items = self.database.get_data_items_by_date(
                target_date,
                namespaces=[namespace],
            )
        else:
            start_date, end_date = date_range
            data_items = self.database.get_data_items_by_date_range(
                start_date,
                end_date,
                namespaces=[namespace],
            )

        return self._format_data_items(data_items, variable)

    def _calculate_date_range(self, time_range: str, target_date: str) -> Tuple[str, str]:
        """
        Calculate start and end dates for the given time range
        
        Args:
            time_range: The time range ('DAY', 'WEEK', 'MONTH')
            target_date: The target date as string (YYYY-MM-DD)
            
        Returns:
            Tuple of (start_date, end_date) as strings
        """
        target_dt = datetime.strptime(target_date, "%Y-%m-%d").date()

        if time_range == "DAY":
            return target_date, target_date

        if time_range == "WEEK":
            # Week = today + 6 days prior (7 days total)
            start_date = target_dt - timedelta(days=6)
            return start_date.strftime("%Y-%m-%d"), target_date

        if time_range == "MONTH":
            # Month = from 1st of month to target date
            start_date = target_dt.replace(day=1)
            return start_date.strftime("%Y-%m-%d"), target_date

        raise ValueError(f"Unsupported time range: {time_range}")

    def _format_data_items(self, data_items: List[Dict], variable: TemplateVariable) -> str:
        """
        Format data items into a readable string
        
        Args:
            data_items: List of data items from database
            variable: The template variable being resolved
            
        Returns:
            Formatted string representation of the data
        """
        if not data_items:
            return f"[No data available for {variable.source}_{variable.time_range}]"

        # Basic formatting - can be enhanced with different strategies
        formatted_items = []

        for item in data_items:
            content = item.get("content", "")
            days_date = item.get("days_date", "")

            # Truncate very long content
            if len(content) > 500:
                content = content[:500] + "..."

            if days_date:
                formatted_items.append(f"[{days_date}] {content}")
            else:
                formatted_items.append(content)

        # Join with newlines, but limit total output size
        result = "\n".join(formatted_items)

        # Limit total output size to prevent overwhelming the prompt
        if len(result) > 5000:
            result = result[:5000] + f"\n... ({len(data_items)} total items, truncated)"

        return result

    def _get_namespace_for_source(self, source: str) -> Optional[str]:
        """
        Get the database namespace for a template source
        
        Args:
            source: The template source name (e.g., 'LIMITLESS')
            
        Returns:
            The corresponding database namespace or None
        """
        for namespace, template_name in self.sources.items():
            if template_name == source:
                return namespace
        return None

    def _get_current_date(self) -> str:
        """
        Get the current date in the configured timezone
        
        Returns:
            Current date as YYYY-MM-DD string
        """
        try:
            tz = pytz.timezone(self.timezone)
            now = datetime.now(tz)
            return now.strftime("%Y-%m-%d")
        except Exception as e:
            logger.warning(f"Error getting timezone-aware date: {e}. Using UTC.")
            return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def add_source(self, namespace: str, template_name: str) -> None:
        """
        Add a new data source for template processing
        
        Args:
            namespace: The database namespace
            template_name: The template variable name (e.g., 'NEWSFEED')
        """
        self.sources[namespace] = template_name
        logger.info(f"Added new template source: {template_name} -> {namespace}")

    def get_supported_sources(self) -> Dict[str, str]:
        """Get all supported template sources"""
        return self.sources.copy()

    def validate_template(self, content: str) -> Dict[str, Any]:
        """
        Validate template variables without resolving them
        
        Args:
            content: The content to validate
            
        Returns:
            Dictionary with validation results
        """
        variables = self.parse_template_variables(content)

        valid_variables = []
        invalid_variables = []

        for var in variables:
            if (self._get_namespace_for_source(var.source) and
                var.time_range in self.TIME_RANGES):
                valid_variables.append(var.full_match)
            else:
                invalid_variables.append(var.full_match)

        return {
            "is_valid": len(invalid_variables) == 0,
            "total_variables": len(variables),
            "valid_variables": valid_variables,
            "invalid_variables": invalid_variables,
            "supported_sources": list(self.sources.values()),
            "supported_time_ranges": self.TIME_RANGES,
        }
