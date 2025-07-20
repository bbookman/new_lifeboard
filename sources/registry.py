import os
import importlib
import inspect
from typing import Dict, Type, List, Optional, Any
import logging
from config.models import SourceConfig
from .base import SourceBase, FileSource, APISource, LimitlessSource, DatabaseSource


logger = logging.getLogger(__name__)


class SourceRegistry:
    """Registry for managing data source types and instances"""
    
    def __init__(self):
        self.source_types: Dict[str, Type[SourceBase]] = {}
        self.active_sources: Dict[str, SourceBase] = {}
        self._register_built_in_sources()
        self._auto_discover_sources()
    
    def _register_built_in_sources(self):
        """Register built-in source types"""
        self.source_types['file'] = FileSource
        self.source_types['api'] = APISource
        self.source_types['limitless'] = LimitlessSource
        self.source_types['database'] = DatabaseSource
        
        logger.info(f"Registered {len(self.source_types)} built-in source types")
    
    def _auto_discover_sources(self):
        """Auto-discover source adapters from the adapters directory"""
        try:
            adapters_dir = os.path.join(os.path.dirname(__file__), 'adapters')
            if not os.path.exists(adapters_dir):
                return
            
            for filename in os.listdir(adapters_dir):
                if filename.endswith('.py') and not filename.startswith('_'):
                    module_name = filename[:-3]  # Remove .py extension
                    try:
                        module = importlib.import_module(f'sources.adapters.{module_name}')
                        self._register_sources_from_module(module)
                    except Exception as e:
                        logger.warning(f"Failed to load adapter module {module_name}: {e}")
                        
        except Exception as e:
            logger.error(f"Error during source auto-discovery: {e}")
    
    def _register_sources_from_module(self, module):
        """Register source classes from a module"""
        for name, obj in inspect.getmembers(module, inspect.isclass):
            if issubclass(obj, SourceBase) and obj != SourceBase:
                source_type = obj().get_source_type() if hasattr(obj, 'get_source_type') else name.lower()
                self.source_types[source_type] = obj
                logger.info(f"Registered source type: {source_type}")
    
    def register_source_type(self, source_type: str, source_class: Type[SourceBase]):
        """Manually register a source type"""
        if not issubclass(source_class, SourceBase):
            raise ValueError(f"Source class must inherit from SourceBase")
        
        self.source_types[source_type] = source_class
        logger.info(f"Registered custom source type: {source_type}")
    
    def create_source(self, source_config: SourceConfig) -> SourceBase:
        """Create a source instance from configuration"""
        source_type = source_config.source_type
        
        if source_type not in self.source_types:
            raise ValueError(f"Unknown source type: {source_type}")
        
        source_class = self.source_types[source_type]
        
        try:
            source = source_class(source_config.namespace, source_config.config)
            return source
        except Exception as e:
            logger.error(f"Failed to create source {source_config.namespace}: {e}")
            raise
    
    def add_source(self, source_config: SourceConfig) -> SourceBase:
        """Add and activate a source"""
        if source_config.namespace in self.active_sources:
            logger.warning(f"Replacing existing source: {source_config.namespace}")
        
        source = self.create_source(source_config)
        self.active_sources[source_config.namespace] = source
        
        logger.info(f"Added source: {source_config.namespace} ({source_config.source_type})")
        return source
    
    def remove_source(self, namespace: str) -> bool:
        """Remove an active source"""
        if namespace in self.active_sources:
            del self.active_sources[namespace]
            logger.info(f"Removed source: {namespace}")
            return True
        return False
    
    def get_source(self, namespace: str) -> Optional[SourceBase]:
        """Get an active source by namespace"""
        return self.active_sources.get(namespace)
    
    def get_active_sources(self) -> List[SourceBase]:
        """Get all active source instances"""
        return list(self.active_sources.values())
    
    def get_namespaces(self) -> List[str]:
        """Get all active namespaces"""
        return list(self.active_sources.keys())
    
    def get_source_types(self) -> List[str]:
        """Get all available source types"""
        return list(self.source_types.keys())
    
    def get_source_type_info(self, source_type: str) -> Dict[str, Any]:
        """Get information about a source type"""
        if source_type not in self.source_types:
            return {}
        
        source_class = self.source_types[source_type]
        return {
            'type': source_type,
            'class': source_class.__name__,
            'module': source_class.__module__,
            'docstring': source_class.__doc__ or '',
            'base_classes': [base.__name__ for base in source_class.__bases__]
        }
    
    async def validate_source_config(self, source_config: SourceConfig) -> List[str]:
        """Validate a source configuration"""
        errors = []
        
        # Check if source type exists
        if source_config.source_type not in self.source_types:
            errors.append(f"Unknown source type: {source_config.source_type}")
            return errors
        
        # Create temporary source instance to validate config
        try:
            source = self.create_source(source_config)
            config_errors = await source.validate_config()
            errors.extend(config_errors)
        except Exception as e:
            errors.append(f"Failed to create source: {str(e)}")
        
        return errors
    
    async def test_source_connection(self, source_config: SourceConfig) -> bool:
        """Test if a source configuration works"""
        try:
            source = self.create_source(source_config)
            return await source.test_connection()
        except Exception as e:
            logger.error(f"Connection test failed for {source_config.namespace}: {e}")
            return False
    
    def load_sources_from_configs(self, source_configs: List[SourceConfig]):
        """Load multiple sources from configurations"""
        loaded_count = 0
        failed_count = 0
        
        for config in source_configs:
            if not config.enabled:
                logger.info(f"Skipping disabled source: {config.namespace}")
                continue
            
            try:
                self.add_source(config)
                loaded_count += 1
            except Exception as e:
                logger.error(f"Failed to load source {config.namespace}: {e}")
                failed_count += 1
        
        logger.info(f"Loaded {loaded_count} sources, {failed_count} failed")
        return loaded_count, failed_count
    
    async def sync_all_sources(self, since: Optional[Any] = None) -> Dict[str, Any]:
        """Sync all active sources and return results"""
        from datetime import datetime
        import time
        
        results = {}
        total_items = 0
        total_errors = 0
        
        start_time = time.time()
        
        for namespace, source in self.active_sources.items():
            logger.info(f"Syncing source: {namespace}")
            source_start = time.time()
            
            try:
                items_count = 0
                errors = []
                
                async for item in source.fetch_data(since):
                    items_count += 1
                    # In a real implementation, you'd store these items
                    # For now, we just count them
                
                sync_duration = time.time() - source_start
                
                results[namespace] = {
                    'success': True,
                    'items_fetched': items_count,
                    'sync_duration_seconds': sync_duration,
                    'errors': errors
                }
                
                total_items += items_count
                logger.info(f"Synced {namespace}: {items_count} items in {sync_duration:.2f}s")
                
            except Exception as e:
                sync_duration = time.time() - source_start
                error_msg = str(e)
                
                results[namespace] = {
                    'success': False,
                    'items_fetched': 0,
                    'sync_duration_seconds': sync_duration,
                    'errors': [error_msg]
                }
                
                total_errors += 1
                logger.error(f"Failed to sync {namespace}: {error_msg}")
        
        total_duration = time.time() - start_time
        
        return {
            'sync_time': datetime.now(),
            'total_duration_seconds': total_duration,
            'total_sources': len(self.active_sources),
            'total_items': total_items,
            'total_errors': total_errors,
            'source_results': results
        }
    
    def get_registry_stats(self) -> Dict[str, Any]:
        """Get statistics about the registry"""
        return {
            'available_source_types': len(self.source_types),
            'active_sources': len(self.active_sources),
            'source_types': list(self.source_types.keys()),
            'active_namespaces': list(self.active_sources.keys())
        }
    
    def cleanup(self):
        """Clean up all sources"""
        for namespace, source in self.active_sources.items():
            try:
                if hasattr(source, 'cleanup'):
                    source.cleanup()
            except Exception as e:
                logger.error(f"Error cleaning up source {namespace}: {e}")
        
        self.active_sources.clear()
        logger.info("Source registry cleaned up")


class SourceFactory:
    """Factory methods for creating common source configurations"""
    
    @staticmethod
    def create_limitless_config(namespace: str, api_key: str, 
                               timezone: str = 'UTC') -> SourceConfig:
        """Create Limitless source configuration"""
        return SourceConfig(
            namespace=namespace,
            source_type='limitless',
            enabled=True,
            config={
                'base_url': 'https://api.limitless.ai/v1',
                'api_key': api_key,
                'timezone': timezone,
                'include_markdown': True,
                'include_headings': True,
                'page_limit': 10
            }
        )
    
    @staticmethod
    def create_file_config(namespace: str, file_path: str, 
                          file_type: str = 'text') -> SourceConfig:
        """Create file source configuration"""
        return SourceConfig(
            namespace=namespace,
            source_type='file',
            enabled=True,
            config={
                'file_path': file_path,
                'file_type': file_type,
                'encoding': 'utf-8'
            }
        )
    
    @staticmethod
    def create_api_config(namespace: str, base_url: str, api_key: str,
                         headers: Dict[str, str] = None) -> SourceConfig:
        """Create generic API source configuration"""
        config = {
            'base_url': base_url,
            'api_key': api_key,
            'timeout': 30
        }
        
        if headers:
            config['headers'] = headers
        
        return SourceConfig(
            namespace=namespace,
            source_type='api',
            enabled=True,
            config=config
        )
    
    @staticmethod
    def from_environment_variables() -> List[SourceConfig]:
        """Create source configurations from environment variables"""
        configs = []
        
        # Look for LIFEBOARD_{NAMESPACE}_SOURCE_ENABLED=true patterns
        for key, value in os.environ.items():
            if key.endswith('_SOURCE_ENABLED') and value.lower() == 'true':
                namespace = key.replace('_SOURCE_ENABLED', '').lower()
                namespace = namespace.replace('lifeboard_', '')
                
                source_type = os.environ.get(f'LIFEBOARD_{namespace.upper()}_SOURCE_TYPE')
                if not source_type:
                    continue
                
                # Build config from environment variables
                config = {}
                prefix = f'LIFEBOARD_{namespace.upper()}_'
                
                for env_key, env_value in os.environ.items():
                    if env_key.startswith(prefix) and not env_key.endswith('_SOURCE_TYPE') and not env_key.endswith('_SOURCE_ENABLED'):
                        config_key = env_key.replace(prefix, '').lower()
                        config[config_key] = env_value
                
                if config:
                    configs.append(SourceConfig(
                        namespace=namespace,
                        source_type=source_type.lower(),
                        enabled=True,
                        config=config
                    ))
        
        return configs