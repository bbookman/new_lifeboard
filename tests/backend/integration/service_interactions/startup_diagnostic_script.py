#!/usr/bin/env python3
"""
Comprehensive Server Startup Test with Enhanced Logging
This script starts the server and captures detailed diagnostics to identify startup failures.
"""

import asyncio
import logging
import os
import sys
import time
import subprocess
import requests
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

# Configure comprehensive logging
log_file = project_root / "logs" / "startup_test.log"
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_file)
    ]
)

logger = logging.getLogger(__name__)

class ServerStartupTester:
    """Test server startup and chat service availability"""
    
    def __init__(self):
        self.server_process = None
        self.server_url = "http://127.0.0.1:8000"
        self.startup_timeout = 30
        self.diagnostics_file = project_root / "logs" / "startup_diagnostics.log"
        
    def start_server(self):
        """Start the server in a subprocess"""
        logger.info("=== STARTING SERVER STARTUP TEST ===")
        
        # Change to project directory
        os.chdir(project_root)
        
        # Start server process
        cmd = [sys.executable, "-m", "api.server", "--host", "127.0.0.1", "--port", "8000"]
        logger.info(f"Starting server with command: {' '.join(cmd)}")
        
        try:
            self.server_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1
            )
            logger.info(f"Server process started with PID: {self.server_process.pid}")
            return True
        except Exception as e:
            logger.error(f"Failed to start server process: {e}")
            return False
    
    def wait_for_server_ready(self):
        """Wait for server to be ready and capture startup logs"""
        logger.info("Waiting for server to be ready...")
        
        startup_logs = []
        start_time = time.time()
        
        while time.time() - start_time < self.startup_timeout:
            if self.server_process.poll() is not None:
                logger.error("Server process terminated unexpectedly")
                return False, startup_logs
                
            # Read available output
            try:
                line = self.server_process.stdout.readline()
                if line:
                    line = line.strip()
                    startup_logs.append(line)
                    logger.info(f"SERVER: {line}")
                    
                    # Check for ready indicators
                    if "YIELD POINT REACHED" in line:
                        logger.info("Server reached yield point - should be ready")
                        time.sleep(2)  # Give it a moment to fully initialize
                        return True, startup_logs
                        
                    if "Application initialized successfully" in line:
                        logger.info("Server reports successful initialization")
                        
                else:
                    time.sleep(0.1)
                    
            except Exception as e:
                logger.error(f"Error reading server output: {e}")
                break
        
        logger.error(f"Server startup timeout after {self.startup_timeout} seconds")
        return False, startup_logs
    
    def test_endpoints(self):
        """Test various endpoints to identify the issue"""
        logger.info("=== TESTING ENDPOINTS ===")
        
        test_results = {}
        
        # Test endpoints in order of dependency
        endpoints = [
            ("/health", "Health Check"),
            ("/status", "Status Check"),
            ("/chat", "Chat Page")
        ]
        
        for endpoint, description in endpoints:
            logger.info(f"Testing {description}: {self.server_url}{endpoint}")
            
            try:
                response = requests.get(f"{self.server_url}{endpoint}", timeout=10)
                test_results[endpoint] = {
                    "status_code": response.status_code,
                    "success": response.status_code == 200,
                    "content_length": len(response.content),
                    "error": None
                }
                
                if response.status_code == 200:
                    logger.info(f"✅ {description}: SUCCESS (200)")
                else:
                    logger.error(f"❌ {description}: FAILED ({response.status_code})")
                    logger.error(f"Response: {response.text[:500]}")
                    
            except Exception as e:
                logger.error(f"❌ {description}: EXCEPTION - {e}")
                test_results[endpoint] = {
                    "status_code": None,
                    "success": False,
                    "content_length": 0,
                    "error": str(e)
                }
        
        return test_results
    
    def analyze_diagnostics(self):
        """Analyze the startup diagnostics file"""
        logger.info("=== ANALYZING STARTUP DIAGNOSTICS ===")
        
        if not self.diagnostics_file.exists():
            logger.warning(f"Diagnostics file not found: {self.diagnostics_file}")
            return None
            
        try:
            with open(self.diagnostics_file, 'r') as f:
                diagnostics = f.read()
            
            logger.info("Startup Diagnostics Content:")
            logger.info("-" * 50)
            for line in diagnostics.split('\n'):
                if line.strip():
                    logger.info(f"DIAG: {line}")
            logger.info("-" * 50)
            
            # Analyze key indicators
            analysis = {
                "startup_initiated": "Lifespan startup initiated" in diagnostics,
                "config_created": "Config created: True" in diagnostics,
                "initialize_called": "Calling initialize_application" in diagnostics,
                "post_init_service": "Post-init startup service: available" in diagnostics,
                "chat_service_available": "Chat service: available" in diagnostics,
                "route_config_success": "Route dependencies configured successfully" in diagnostics,
                "initialization_successful": "Application initialization successful" in diagnostics
            }
            
            logger.info("=== DIAGNOSTIC ANALYSIS ===")
            for key, value in analysis.items():
                status = "✅ PASS" if value else "❌ FAIL"
                logger.info(f"{status} {key.replace('_', ' ').title()}")
            
            return analysis
            
        except Exception as e:
            logger.error(f"Failed to analyze diagnostics: {e}")
            return None
    
    def stop_server(self):
        """Stop the server process"""
        if self.server_process:
            logger.info("Stopping server process...")
            try:
                self.server_process.terminate()
                self.server_process.wait(timeout=10)
                logger.info("Server process stopped")
            except subprocess.TimeoutExpired:
                logger.warning("Server didn't stop gracefully, killing...")
                self.server_process.kill()
                self.server_process.wait()
            except Exception as e:
                logger.error(f"Error stopping server: {e}")
    
    def run_test(self):
        """Run the complete startup test"""
        try:
            # Start server
            if not self.start_server():
                return False
            
            # Wait for ready
            ready, startup_logs = self.wait_for_server_ready()
            
            if ready:
                logger.info("✅ Server appears to be ready")
                
                # Test endpoints
                test_results = self.test_endpoints()
                
                # Analyze diagnostics
                analysis = self.analyze_diagnostics()
                
                # Summary
                logger.info("=== TEST SUMMARY ===")
                logger.info(f"Server Ready: {'✅ YES' if ready else '❌ NO'}")
                
                for endpoint, result in test_results.items():
                    status = "✅ PASS" if result["success"] else "❌ FAIL"
                    logger.info(f"{endpoint}: {status}")
                
                if analysis:
                    failed_steps = [k for k, v in analysis.items() if not v]
                    if failed_steps:
                        logger.error(f"Failed startup steps: {', '.join(failed_steps)}")
                    else:
                        logger.info("✅ All startup steps completed successfully")
                
                return len([r for r in test_results.values() if r["success"]]) == len(test_results)
            else:
                logger.error("❌ Server failed to become ready")
                logger.error("Recent startup logs:")
                for log_line in startup_logs[-20:]:  # Show last 20 lines
                    logger.error(f"  {log_line}")
                return False
                
        except Exception as e:
            logger.error(f"Test execution failed: {e}")
            logger.exception("Full test exception:")
            return False
        finally:
            self.stop_server()

def main():
    """Main test execution"""
    tester = ServerStartupTester()
    
    success = tester.run_test()
    
    if success:
        logger.info("🎉 ALL TESTS PASSED - Server startup and chat service working correctly")
        sys.exit(0)
    else:
        logger.error("💥 TESTS FAILED - Issues identified with server startup or chat service")
        sys.exit(1)

if __name__ == "__main__":
    main()