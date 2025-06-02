"""
Test tools for Enterprise AI tool completion testing - Class-based Architecture.

This module provides a collection of organized tool classes that demonstrate various
tool calling scenarios, data types, and execution patterns for validating
the Enterprise AI tool execution system.

Enhanced with class-based organization for better modularity and maintenance.
"""

import json
import time
import random
import asyncio
from typing import Any, Dict, List, Optional, Union
from datetime import datetime, timedelta

# ═══════════════════════════════════════════════════════════════════════════════
# 🧮 CALCULATION TOOLS CLASS
# ═══════════════════════════════════════════════════════════════════════════════

class CalculationTools:
    """
    Mathematical calculation tools for Enterprise AI testing.
    
    Provides advanced calculation capabilities with step-by-step evaluation,
    error handling, and flexible precision control.
    """
    
    @staticmethod
    def calculate_advanced(
        expression: str,
        precision: Optional[Union[int, str]] = 2,
        include_steps: Optional[Union[bool, str]] = False
    ) -> Dict[str, Any]:
        """
        Advanced calculator with step-by-step evaluation.
        
        Args:
            expression: Mathematical expression to evaluate
            precision: Number of decimal places
            include_steps: Whether to include calculation steps
            
        Returns:
            Calculation result with metadata
        """
        start_time = time.time()
        
        try:
            # Convert string arguments to proper types
            if isinstance(precision, str):
                precision = int(precision) if precision.isdigit() else 2
            if isinstance(include_steps, str):
                include_steps = include_steps.lower() in ('true', '1', 'yes')
            
            # Safe evaluation (basic operators only)
            allowed_chars = set('0123456789+-*/()., ')
            if not all(c in allowed_chars for c in expression):
                raise ValueError("Expression contains invalid characters")
            
            # Evaluate the expression
            result = eval(expression)
            
            # Round to specified precision
            if isinstance(result, (int, float)):
                formatted_result = round(result, precision)
            else:
                formatted_result = result
            
            execution_time = time.time() - start_time
            
            response = {
                "result": formatted_result,
                "expression": expression,
                "precision": precision,
                "execution_time_ms": round(execution_time * 1000, 2),
                "timestamp": datetime.now().isoformat(),
                "tool_class": "CalculationTools"
            }
            
            if include_steps:
                response["steps"] = [
                    f"Input: {expression}",
                    f"Evaluation: {expression} = {result}",
                    f"Rounded to {precision} places: {formatted_result}"
                ]
            
            return response
            
        except Exception as e:
            return {
                "error": str(e),
                "expression": expression,
                "execution_time_ms": round((time.time() - start_time) * 1000, 2),
                "tool_class": "CalculationTools"
            }

    @staticmethod
    def calculate_basic(expression: str) -> Dict[str, Any]:
        """
        Basic calculation without advanced features.
        
        Args:
            expression: Mathematical expression to evaluate
            
        Returns:
            Simple calculation result
        """
        try:
            result = eval(expression)
            return {
                "result": result,
                "expression": expression,
                "success": True,
                "tool_class": "CalculationTools"
            }
        except Exception as e:
            return {
                "error": str(e),
                "expression": expression,
                "success": False,
                "tool_class": "CalculationTools"
            }

# ═══════════════════════════════════════════════════════════════════════════════
# 📊 DATA ANALYSIS TOOLS CLASS
# ═══════════════════════════════════════════════════════════════════════════════

class DataAnalysisTools:
    """
    Statistical analysis and data processing tools.
    
    Provides comprehensive statistical analysis capabilities with support
    for various data formats and advanced metrics.
    """
    
    @staticmethod
    def statistical_analysis(
        numbers: Union[List[float], List[str], str],
        include_advanced: Optional[Union[bool, str]] = True
    ) -> Dict[str, Any]:
        """
        Perform statistical analysis on a list of numbers.
        
        Args:
            numbers: List of numbers to analyze or JSON string
            include_advanced: Include advanced statistics
            
        Returns:
            Statistical analysis results
        """
        try:
            # Handle different input formats
            if isinstance(numbers, str):
                # Try to parse as JSON first
                try:
                    numbers = json.loads(numbers)
                except json.JSONDecodeError:
                    # If not JSON, try to split and convert
                    numbers = [float(x.strip()) for x in numbers.split(',') if x.strip()]
            
            # Convert string list to float list
            if isinstance(numbers, list) and numbers and isinstance(numbers[0], str):
                numbers = [float(x) for x in numbers if str(x).replace('.', '').replace('-', '').isdigit()]
            
            # Convert string argument
            if isinstance(include_advanced, str):
                include_advanced = include_advanced.lower() in ('true', '1', 'yes')
            
            if not numbers:
                return {
                    "error": "Empty or invalid list provided",
                    "numbers_received": str(numbers),
                    "analysis_status": "failed",
                    "tool_class": "DataAnalysisTools"
                }
            
            # Basic statistics
            count = len(numbers)
            total = sum(numbers)
            mean = total / count
            sorted_nums = sorted(numbers)
            
            # Median
            mid = count // 2
            if count % 2 == 0:
                median = (sorted_nums[mid - 1] + sorted_nums[mid]) / 2
            else:
                median = sorted_nums[mid]
            
            # Range
            min_val = min(numbers)
            max_val = max(numbers)
            range_val = max_val - min_val
            
            result = {
                "analysis_status": "completed",
                "count": count,
                "sum": total,
                "mean": round(mean, 4),
                "median": median,
                "min": min_val,
                "max": max_val,
                "range": range_val,
                "sorted_data": sorted_nums[:10],  # Limit output size
                "tool_class": "DataAnalysisTools"
            }
            
            if include_advanced and count > 1:
                # Standard deviation
                variance = sum((x - mean) ** 2 for x in numbers) / count
                std_dev = variance ** 0.5
                
                result.update({
                    "variance": round(variance, 4),
                    "standard_deviation": round(std_dev, 4)
                })
            
            return result
            
        except Exception as e:
            return {
                "error": f"Statistical analysis failed: {str(e)}",
                "numbers_received": str(numbers),
                "analysis_status": "error",
                "tool_class": "DataAnalysisTools"
            }

    @staticmethod
    def analyze_dataset(data: List[Dict[str, Any]], metric: str = "value") -> Dict[str, Any]:
        """
        Analyze a dataset by extracting a specific metric.
        
        Args:
            data: List of dictionaries containing data
            metric: The key to analyze from each dictionary
            
        Returns:
            Analysis results for the specified metric
        """
        try:
            values = []
            for item in data:
                if isinstance(item, dict) and metric in item:
                    val = item[metric]
                    if isinstance(val, (int, float)):
                        values.append(val)
            
            if not values:
                return {
                    "error": f"No valid numeric values found for metric '{metric}'",
                    "tool_class": "DataAnalysisTools"
                }
            
            # Use statistical_analysis for the actual computation
            return DataAnalysisTools.statistical_analysis(values, include_advanced=True)
            
        except Exception as e:
            return {
                "error": f"Dataset analysis failed: {str(e)}",
                "tool_class": "DataAnalysisTools"
            }

# ═══════════════════════════════════════════════════════════════════════════════
# 🔄 DATA PROCESSING TOOLS CLASS
# ═══════════════════════════════════════════════════════════════════════════════

class DataProcessingTools:
    """
    JSON and data processing tools for Enterprise AI testing.
    
    Provides comprehensive data manipulation, validation, and transformation
    capabilities for various data formats.
    """
    
    @staticmethod
    def process_json_data(
        json_string: str,
        operation: str = "validate",
        filter_key: Optional[str] = None,
        sort_by: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process and manipulate JSON data.
        
        Args:
            json_string: JSON data as string
            operation: Operation to perform (validate, filter, sort, summary)
            filter_key: Key to filter by (for filter operation)
            sort_by: Key to sort by (for sort operation)
            
        Returns:
            Processed data result
        """
        try:
            # Parse JSON
            data = json.loads(json_string)
            
            result = {
                "operation": operation,
                "original_type": type(data).__name__,
                "timestamp": datetime.now().isoformat(),
                "success": True,
                "tool_class": "DataProcessingTools"
            }
            
            if operation == "validate":
                result.update({
                    "valid": True,
                    "structure": DataProcessingTools._analyze_json_structure(data),
                    "size_bytes": len(json_string)
                })
                
            elif operation == "filter" and isinstance(data, list) and filter_key:
                filtered = [item for item in data if isinstance(item, dict) and filter_key in item]
                result.update({
                    "filtered_data": filtered,
                    "original_count": len(data),
                    "filtered_count": len(filtered),
                    "filter_key": filter_key
                })
                
            elif operation == "sort" and isinstance(data, list) and sort_by:
                try:
                    sorted_data = sorted(data, key=lambda x: x.get(sort_by, 0) if isinstance(x, dict) else x)
                    result.update({
                        "sorted_data": sorted_data,
                        "sort_key": sort_by,
                        "count": len(sorted_data)
                    })
                except Exception as e:
                    result["error"] = f"Sort failed: {str(e)}"
                    result["success"] = False
                    
            elif operation == "summary":
                result.update({
                    "summary": DataProcessingTools._generate_json_summary(data)
                })
                
            else:
                result["processed_data"] = data
                
            return result
            
        except json.JSONDecodeError as e:
            return {
                "error": f"Invalid JSON: {str(e)}",
                "operation": operation,
                "success": False,
                "tool_class": "DataProcessingTools"
            }
        except Exception as e:
            return {
                "error": f"Processing failed: {str(e)}",
                "operation": operation,
                "success": False,
                "tool_class": "DataProcessingTools"
            }

    @staticmethod
    def _analyze_json_structure(data: Any, max_depth: int = 3, current_depth: int = 0) -> Dict[str, Any]:
        """Analyze the structure of JSON data."""
        if current_depth >= max_depth:
            return {"type": type(data).__name__, "truncated": True}
        
        if isinstance(data, dict):
            return {
                "type": "object",
                "keys": list(data.keys())[:10],  # Limit keys shown
                "key_count": len(data),
                "sample_values": {
                    k: DataProcessingTools._analyze_json_structure(v, max_depth, current_depth + 1)
                    for k, v in list(data.items())[:3]
                }
            }
        elif isinstance(data, list):
            return {
                "type": "array",
                "length": len(data),
                "sample_items": [
                    DataProcessingTools._analyze_json_structure(item, max_depth, current_depth + 1)
                    for item in data[:3]
                ]
            }
        else:
            return {
                "type": type(data).__name__,
                "value": str(data)[:50] + "..." if len(str(data)) > 50 else str(data)
            }

    @staticmethod
    def _generate_json_summary(data: Any) -> Dict[str, Any]:
        """Generate a summary of JSON data."""
        summary = {"data_type": type(data).__name__}
        
        if isinstance(data, dict):
            summary.update({
                "object_keys": len(data),
                "key_types": {k: type(v).__name__ for k, v in data.items()},
                "nested_objects": sum(1 for v in data.values() if isinstance(v, dict)),
                "nested_arrays": sum(1 for v in data.values() if isinstance(v, list))
            })
        elif isinstance(data, list):
            summary.update({
                "array_length": len(data),
                "item_types": list(set(type(item).__name__ for item in data)),
                "has_objects": any(isinstance(item, dict) for item in data),
                "has_arrays": any(isinstance(item, list) for item in data)
            })
        else:
            summary.update({
                "value_length": len(str(data)),
                "value_preview": str(data)[:100]
            })
        
        return summary

# ═══════════════════════════════════════════════════════════════════════════════
# 🌐 NETWORK SIMULATION TOOLS CLASS
# ═══════════════════════════════════════════════════════════════════════════════

class NetworkTools:
    """
    Network simulation and API testing tools.
    
    Provides realistic API request simulation with configurable success rates,
    delays, and response patterns for testing network-dependent workflows.
    """
    
    @staticmethod
    def simulate_api_request(
        url: str,
        method: str = "GET",
        simulate_delay: Union[bool, str] = True,
        success_rate: Union[float, str] = 0.9
    ) -> Dict[str, Any]:
        """
        Simulate an API request with realistic behavior.
        
        Args:
            url: Target URL
            method: HTTP method
            simulate_delay: Whether to add realistic delay
            success_rate: Probability of success (0.0 to 1.0)
            
        Returns:
            Simulated API response
        """
        start_time = time.time()
        
        # Convert string arguments
        if isinstance(simulate_delay, str):
            simulate_delay = simulate_delay.lower() in ('true', '1', 'yes')
        if isinstance(success_rate, str):
            try:
                success_rate = float(success_rate)
            except ValueError:
                success_rate = 0.9
        
        # Simulate network delay
        if simulate_delay:
            delay = random.uniform(0.05, 0.2)  # Shorter delay for testing
            time.sleep(delay)
        
        # Simulate success/failure
        is_success = random.random() < success_rate
        
        execution_time = time.time() - start_time
        
        response = {
            "url": url,
            "method": method.upper(),
            "timestamp": datetime.now().isoformat(),
            "execution_time_ms": round(execution_time * 1000, 2),
            "simulated": True,
            "success": is_success,
            "tool_class": "NetworkTools"
        }
        
        if is_success:
            # Simulate successful response
            response.update({
                "status_code": 200,
                "data": {
                    "message": f"Simulated {method.upper()} request to {url}",
                    "request_id": f"req_{int(time.time() * 1000)}",
                    "server_time": datetime.now().isoformat(),
                    "response_size": random.randint(100, 5000)
                },
                "headers": {
                    "content-type": "application/json",
                    "server": "simulation-server/1.0",
                    "x-request-id": f"sim_{random.randint(1000, 9999)}"
                }
            })
        else:
            # Simulate error response
            error_codes = [400, 401, 403, 404, 500, 502, 503]
            status_code = random.choice(error_codes)
            
            response.update({
                "status_code": status_code,
                "error": {
                    "code": status_code,
                    "message": f"Simulated error for {method.upper()} {url}",
                    "type": "simulation_error"
                }
            })
        
        return response

    @staticmethod
    def check_service_health(services: List[str]) -> Dict[str, Any]:
        """
        Simulate health checks for multiple services.
        
        Args:
            services: List of service names to check
            
        Returns:
            Health check results for all services
        """
        results = {
            "timestamp": datetime.now().isoformat(),
            "total_services": len(services),
            "healthy_services": 0,
            "unhealthy_services": 0,
            "service_status": {},
            "tool_class": "NetworkTools"
        }
        
        for service in services:
            # Simulate health check
            is_healthy = random.random() > 0.2  # 80% chance of being healthy
            response_time = random.uniform(10, 200)  # ms
            
            status = {
                "healthy": is_healthy,
                "response_time_ms": round(response_time, 2),
                "status": "UP" if is_healthy else "DOWN"
            }
            
            if is_healthy:
                results["healthy_services"] += 1
            else:
                results["unhealthy_services"] += 1
                status["error"] = f"Service {service} is not responding"
            
            results["service_status"][service] = status
        
        results["overall_health"] = "HEALTHY" if results["unhealthy_services"] == 0 else "DEGRADED"
        
        return results

# ═══════════════════════════════════════════════════════════════════════════════
# 🔧 DATA GENERATION TOOLS CLASS
# ═══════════════════════════════════════════════════════════════════════════════

class DataGenerationTools:
    """
    Test data generation tools for Enterprise AI testing.
    
    Provides comprehensive data generation capabilities for various scenarios
    including users, products, transactions, and custom datasets.
    """
    
    @staticmethod
    def generate_test_data(
        data_type: str = "users",
        count: Union[int, str] = 10,
        include_metadata: Union[bool, str] = True
    ) -> Dict[str, Any]:
        """
        Generate test data for various scenarios.
        
        Args:
            data_type: Type of data to generate (users, products, transactions)
            count: Number of items to generate
            include_metadata: Include generation metadata
            
        Returns:
            Generated test data
        """
        # Convert string arguments
        if isinstance(count, str):
            try:
                count = int(count)
            except ValueError:
                count = 10
        if isinstance(include_metadata, str):
            include_metadata = include_metadata.lower() in ('true', '1', 'yes')
        
        # Limit count for performance
        count = min(count, 100)
        
        generators = {
            "users": DataGenerationTools._generate_users,
            "products": DataGenerationTools._generate_products,
            "transactions": DataGenerationTools._generate_transactions
        }
        
        if data_type not in generators:
            return {
                "error": f"Unknown data type: {data_type}. Available: {list(generators.keys())}",
                "success": False,
                "tool_class": "DataGenerationTools"
            }
        
        start_time = time.time()
        
        try:
            data = generators[data_type](count)
            
            result = {
                "data_type": data_type,
                "count": len(data),
                "data": data,
                "success": True,
                "tool_class": "DataGenerationTools"
            }
            
            if include_metadata:
                result["metadata"] = {
                    "generation_time_ms": round((time.time() - start_time) * 1000, 2),
                    "timestamp": datetime.now().isoformat(),
                    "generator_version": "2.0"
                }
            
            return result
        except Exception as e:
            return {
                "error": f"Data generation failed: {str(e)}",
                "data_type": data_type,
                "success": False,
                "tool_class": "DataGenerationTools"
            }

    @staticmethod
    def _generate_users(count: int) -> List[Dict[str, Any]]:
        """Generate fake user data."""
        first_names = ["Alice", "Bob", "Charlie", "Diana", "Eve", "Frank", "Grace", "Henry"]
        last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis"]
        domains = ["email.com", "test.org", "example.net", "demo.io"]
        
        users = []
        for i in range(count):
            first = random.choice(first_names)
            last = random.choice(last_names)
            
            user = {
                "id": i + 1,
                "first_name": first,
                "last_name": last,
                "email": f"{first.lower()}.{last.lower()}{i}@{random.choice(domains)}",
                "age": random.randint(18, 80),
                "active": random.choice([True, False]),
                "signup_date": (datetime.now() - timedelta(days=random.randint(1, 365))).isoformat(),
                "score": round(random.uniform(0, 100), 2)
            }
            users.append(user)
        
        return users

    @staticmethod
    def _generate_products(count: int) -> List[Dict[str, Any]]:
        """Generate fake product data."""
        categories = ["Electronics", "Clothing", "Books", "Home", "Sports", "Toys"]
        adjectives = ["Amazing", "Premium", "Basic", "Advanced", "Compact", "Deluxe"]
        nouns = ["Widget", "Gadget", "Tool", "Device", "Item", "Product"]
        
        products = []
        for i in range(count):
            product = {
                "id": i + 1,
                "name": f"{random.choice(adjectives)} {random.choice(nouns)} {i + 1}",
                "category": random.choice(categories),
                "price": round(random.uniform(9.99, 999.99), 2),
                "in_stock": random.randint(0, 100),
                "rating": round(random.uniform(1.0, 5.0), 1),
                "reviews": random.randint(0, 500),
                "featured": random.choice([True, False])
            }
            products.append(product)
        
        return products

    @staticmethod
    def _generate_transactions(count: int) -> List[Dict[str, Any]]:
        """Generate fake transaction data."""
        transaction_types = ["purchase", "refund", "discount", "fee"]
        statuses = ["completed", "pending", "failed", "cancelled"]
        
        transactions = []
        for i in range(count):
            transaction = {
                "id": f"txn_{i + 1:06d}",
                "user_id": random.randint(1, 100),
                "type": random.choice(transaction_types),
                "amount": round(random.uniform(5.0, 500.0), 2),
                "status": random.choice(statuses),
                "timestamp": (datetime.now() - timedelta(hours=random.randint(1, 168))).isoformat(),
                "description": f"Transaction {i + 1} - {random.choice(transaction_types).title()}"
            }
            transactions.append(transaction)
        
        return transactions

# ═══════════════════════════════════════════════════════════════════════════════
# 🏭 TOOL REGISTRY AND CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

# Initialize tool class instances
calculation_tools = CalculationTools()
data_analysis_tools = DataAnalysisTools()
data_processing_tools = DataProcessingTools()
network_tools = NetworkTools()
data_generation_tools = DataGenerationTools()

# Comprehensive tool registry mapping function names to class methods
TOOLS_REGISTRY = {
    # Calculation tools
    "calculate_advanced": calculation_tools.calculate_advanced,
    "calculate_basic": calculation_tools.calculate_basic,
    
    # Data analysis tools
    "statistical_analysis": data_analysis_tools.statistical_analysis,
    "analyze_dataset": data_analysis_tools.analyze_dataset,
    
    # Data processing tools
    "process_json_data": data_processing_tools.process_json_data,
    
    # Network tools
    "simulate_api_request": network_tools.simulate_api_request,
    "check_service_health": network_tools.check_service_health,
    
    # Data generation tools
    "generate_test_data": data_generation_tools.generate_test_data,
}

# Tool definitions for the LLM system
TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "calculate_advanced",
            "description": "Perform advanced mathematical calculations with step-by-step evaluation",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "Mathematical expression to evaluate (e.g., '2 + 3 * 4')"
                    },
                    "precision": {
                        "type": "string",
                        "description": "Number of decimal places for the result (as string)",
                        "default": "2"
                    },
                    "include_steps": {
                        "type": "string",
                        "description": "Whether to include calculation steps (true/false as string)",
                        "default": "false"
                    }
                },
                "required": ["expression"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_basic",
            "description": "Perform basic mathematical calculations quickly",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "Simple mathematical expression to evaluate"
                    }
                },
                "required": ["expression"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "statistical_analysis",
            "description": "Perform statistical analysis on a list of numbers",
            "parameters": {
                "type": "object",
                "properties": {
                    "numbers": {
                        "type": "string",
                        "description": "List of numbers as JSON string or comma-separated values"
                    },
                    "include_advanced": {
                        "type": "string",
                        "description": "Include advanced statistics like standard deviation (true/false)",
                        "default": "true"
                    }
                },
                "required": ["numbers"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_dataset",
            "description": "Analyze a dataset by extracting and analyzing a specific metric",
            "parameters": {
                "type": "object",
                "properties": {
                    "data": {
                        "type": "string",
                        "description": "JSON string containing array of objects to analyze"
                    },
                    "metric": {
                        "type": "string",
                        "description": "The key/field name to analyze from each object",
                        "default": "value"
                    }
                },
                "required": ["data"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "process_json_data",
            "description": "Process and manipulate JSON data with various operations",
            "parameters": {
                "type": "object",
                "properties": {
                    "json_string": {
                        "type": "string",
                        "description": "JSON data as a string"
                    },
                    "operation": {
                        "type": "string",
                        "enum": ["validate", "filter", "sort", "summary"],
                        "description": "Operation to perform on the JSON data",
                        "default": "validate"
                    },
                    "filter_key": {
                        "type": "string",
                        "description": "Key to filter by (for filter operation)"
                    },
                    "sort_by": {
                        "type": "string",
                        "description": "Key to sort by (for sort operation)"
                    }
                },
                "required": ["json_string"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "simulate_api_request",
            "description": "Simulate an API request with realistic behavior and responses",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "Target URL for the simulated request"
                    },
                    "method": {
                        "type": "string",
                        "enum": ["GET", "POST", "PUT", "DELETE"],
                        "description": "HTTP method for the request",
                        "default": "GET"
                    },
                    "simulate_delay": {
                        "type": "string",
                        "description": "Whether to add realistic network delay (true/false)",
                        "default": "true"
                    },
                    "success_rate": {
                        "type": "string",
                        "description": "Probability of request success (0.0 to 1.0 as string)",
                        "default": "0.9"
                    }
                },
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "check_service_health",
            "description": "Check the health status of multiple services",
            "parameters": {
                "type": "object",
                "properties": {
                    "services": {
                        "type": "string",
                        "description": "JSON array of service names to check"
                    }
                },
                "required": ["services"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "generate_test_data",
            "description": "Generate realistic test data for various scenarios",
            "parameters": {
                "type": "object",
                "properties": {
                    "data_type": {
                        "type": "string",
                        "enum": ["users", "products", "transactions"],
                        "description": "Type of test data to generate",
                        "default": "users"
                    },
                    "count": {
                        "type": "string",
                        "description": "Number of items to generate (as string)",
                        "default": "10"
                    },
                    "include_metadata": {
                        "type": "string",
                        "description": "Include generation metadata in response (true/false)",
                        "default": "true"
                    }
                },
                "required": []
            }
        }
    }
]

def get_all_tools():
    """Get all available tools and their definitions."""
    return {
        "tools": TOOLS_REGISTRY,
        "definitions": TOOL_DEFINITIONS,
        "count": len(TOOLS_REGISTRY),
        "classes": {
            "CalculationTools": calculation_tools,
            "DataAnalysisTools": data_analysis_tools,
            "DataProcessingTools": data_processing_tools,
            "NetworkTools": network_tools,
            "DataGenerationTools": data_generation_tools,
        }
    }

def get_tools_by_class(class_name: str) -> Dict[str, Any]:
    """Get tools from a specific class."""
    class_mapping = {
        "calculation": ["calculate_advanced", "calculate_basic"],
        "analysis": ["statistical_analysis", "analyze_dataset"],
        "processing": ["process_json_data"],
        "network": ["simulate_api_request", "check_service_health"],
        "generation": ["generate_test_data"],
    }
    
    if class_name.lower() in class_mapping:
        tool_names = class_mapping[class_name.lower()]
        return {
            name: TOOLS_REGISTRY[name] 
            for name in tool_names 
            if name in TOOLS_REGISTRY
        }
    
    return {}

# Export functions for backward compatibility
calculate_advanced = calculation_tools.calculate_advanced
statistical_analysis = data_analysis_tools.statistical_analysis
process_json_data = data_processing_tools.process_json_data
simulate_api_request = network_tools.simulate_api_request
generate_test_data = data_generation_tools.generate_test_data