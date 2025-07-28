"""
Ollama Management Service

Handles automatic startup and model management for Ollama.
"""

import asyncio
import subprocess
import time
import logging
import httpx
from typing import Optional, Dict, Any, List
import platform
import os

logger = logging.getLogger(__name__)


class OllamaManager:
    """Manages Ollama service lifecycle and model availability"""
    
    def __init__(self, config):
        self.config = config
        self.base_url = config.base_url
        self.model = config.model
        self.timeout = config.timeout
        self._ollama_process: Optional[subprocess.Popen] = None
        self._startup_attempts = 0
        self.max_startup_attempts = 3
        self.startup_timeout = 30  # seconds to wait for Ollama to start
        
    async def ensure_ollama_available(self) -> Dict[str, Any]:
        """
        Ensure Ollama is running and the specified model is available
        
        Returns:
            Dict with status information about the setup process
        """
        result = {
            "ollama_running": False,
            "model_available": False,
            "actions_taken": [],
            "errors": [],
            "success": False
        }
        
        try:
            # Step 1: Check if Ollama is already running
            if await self._check_ollama_running():
                result["ollama_running"] = True
                result["actions_taken"].append("Ollama already running")
                logger.info("Ollama is already running")
            else:
                # Step 2: Try to start Ollama
                if await self._start_ollama():
                    result["ollama_running"] = True
                    result["actions_taken"].append("Started Ollama service")
                    logger.info("Successfully started Ollama")
                else:
                    error_msg = "Failed to start Ollama service"
                    result["errors"].append(error_msg)
                    logger.error(error_msg)
                    return result
            
            # Step 3: Check if the model is available
            if await self._check_model_available():
                result["model_available"] = True
                result["actions_taken"].append(f"Model {self.model} already available")
                logger.info(f"Model {self.model} is already available")
            else:
                # Step 4: Try to pull the model
                if await self._pull_model():
                    result["model_available"] = True
                    result["actions_taken"].append(f"Pulled model {self.model}")
                    logger.info(f"Successfully pulled model {self.model}")
                else:
                    error_msg = f"Failed to pull model {self.model}"
                    result["errors"].append(error_msg)
                    logger.error(error_msg)
                    return result
            
            result["success"] = result["ollama_running"] and result["model_available"]
            
        except Exception as e:
            error_msg = f"Unexpected error in Ollama setup: {str(e)}"
            result["errors"].append(error_msg)
            logger.error(error_msg)
        
        return result
    
    async def _check_ollama_running(self) -> bool:
        """Check if Ollama is running by making a health check request"""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                return response.status_code == 200
        except Exception:
            return False
    
    async def _start_ollama(self) -> bool:
        """Start Ollama service"""
        if self._startup_attempts >= self.max_startup_attempts:
            logger.error(f"Maximum startup attempts ({self.max_startup_attempts}) reached")
            return False
        
        self._startup_attempts += 1
        logger.info(f"Attempting to start Ollama (attempt {self._startup_attempts}/{self.max_startup_attempts})")
        
        try:
            # Check if ollama command is available
            if not self._check_ollama_installed():
                logger.error("Ollama is not installed or not in PATH")
                return False
            
            # Start Ollama service in the background
            if platform.system() == "Windows":
                # Windows: start ollama serve
                self._ollama_process = subprocess.Popen(
                    ["ollama", "serve"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    creationflags=subprocess.CREATE_NEW_CONSOLE
                )
            else:
                # Unix-like systems: start ollama serve
                self._ollama_process = subprocess.Popen(
                    ["ollama", "serve"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    start_new_session=True
                )
            
            # Wait for Ollama to start
            logger.info("Waiting for Ollama to start...")
            start_time = time.time()
            
            while time.time() - start_time < self.startup_timeout:
                if await self._check_ollama_running():
                    logger.info("Ollama started successfully")
                    return True
                await asyncio.sleep(1)
            
            logger.error(f"Ollama failed to start within {self.startup_timeout} seconds")
            await self._cleanup_process()
            return False
            
        except FileNotFoundError:
            logger.error("Ollama command not found. Please install Ollama first.")
            return False
        except Exception as e:
            logger.error(f"Error starting Ollama: {str(e)}")
            await self._cleanup_process()
            return False
    
    def _check_ollama_installed(self) -> bool:
        """Check if Ollama is installed and available in PATH"""
        try:
            result = subprocess.run(
                ["ollama", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False
    
    async def _check_model_available(self) -> bool:
        """Check if the specified model is available locally"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                if response.status_code == 200:
                    data = response.json()
                    models = [model.get("name", "") for model in data.get("models", [])]
                    # Check if our model is in the list (handle tag variations)
                    for model_name in models:
                        if self.model in model_name or model_name.startswith(self.model.split(':')[0]):
                            return True
                return False
        except Exception as e:
            logger.error(f"Error checking model availability: {str(e)}")
            return False
    
    async def _pull_model(self) -> bool:
        """Pull the specified model"""
        try:
            logger.info(f"Pulling model {self.model}...")
            
            async with httpx.AsyncClient(timeout=300.0) as client:  # 5 minute timeout for model pull
                response = await client.post(
                    f"{self.base_url}/api/pull",
                    json={"name": self.model},
                    headers={"Content-Type": "application/json"}
                )
                
                if response.status_code == 200:
                    logger.info(f"Model {self.model} pulled successfully")
                    return True
                else:
                    logger.error(f"Failed to pull model {self.model}: HTTP {response.status_code}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error pulling model {self.model}: {str(e)}")
            return False
    
    async def _cleanup_process(self):
        """Clean up the Ollama process if it was started by us"""
        if self._ollama_process:
            try:
                self._ollama_process.terminate()
                self._ollama_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._ollama_process.kill()
            except Exception as e:
                logger.error(f"Error cleaning up Ollama process: {str(e)}")
            finally:
                self._ollama_process = None
    
    async def get_available_models(self) -> List[str]:
        """Get list of available models"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                if response.status_code == 200:
                    data = response.json()
                    return [model.get("name", "") for model in data.get("models", [])]
                return []
        except Exception as e:
            logger.error(f"Error getting available models: {str(e)}")
            return []
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform a comprehensive health check"""
        return {
            "ollama_running": await self._check_ollama_running(),
            "model_available": await self._check_model_available(),
            "available_models": await self.get_available_models(),
            "configured_model": self.model,
            "base_url": self.base_url
        }
    
    async def shutdown(self):
        """Shutdown the Ollama service if it was started by us"""
        await self._cleanup_process()