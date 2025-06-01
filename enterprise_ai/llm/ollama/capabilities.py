"""
Universal model capability detection for Ollama provider using schema classes.

This module provides advanced model capability detection that works with any Ollama model
by analyzing the actual model metadata rather than relying on hardcoded model names.
"""

import re
from typing import Dict, Set, Optional, Any, List

from enterprise_ai.constants import ModelFeature
from enterprise_ai.logger import get_logger
from enterprise_ai.schema import ModelCapabilities

logger = get_logger("llm.ollama.capabilities")


class OllamaCapabilities:
    """
    Universal capability detector that works with any Ollama model by analyzing
    the actual model metadata from Ollama's /api/show endpoint.
    """

    def __init__(self):
        """Initialize the universal capabilities detector."""
        self._capability_cache = {}
        self._template_patterns = self._compile_template_patterns()

    def _compile_template_patterns(self) -> Dict[str, re.Pattern]:
        """Compile regex patterns for template analysis."""
        return {
            # Enhanced thinking/reasoning patterns - MORE COMPREHENSIVE
            "thinking": re.compile(r'\{\{\s*[.$]*\s*(?:if\s+)?(?:and\s+)?\$?\.?(?:IsThinkSet|Think|Thinking)\s*[^}]*\}\}', re.IGNORECASE),
            "think_tags": re.compile(r'<think>|<thinking>|</think>|</thinking>', re.IGNORECASE),
            "think_variables": re.compile(r'\$\.(?:IsThinkSet|Think|Thinking)\b', re.IGNORECASE),
            "think_conditionals": re.compile(r'\{\{\s*if.*(?:Think|Thinking|IsThinkSet)', re.IGNORECASE),
            
            # Tool/Function calling patterns
            "tools": re.compile(r'\{\{\s*(?:if\s+)?\.Tools\s*\}\}', re.IGNORECASE),
            "toolcalls": re.compile(r'\{\{\s*(?:range\s+)?\.ToolCalls\s*\}\}', re.IGNORECASE),
            "function": re.compile(r'\{\{\s*\.Function\.(Name|Arguments)\s*\}\}', re.IGNORECASE),
            "tool_response": re.compile(r'tool_response|ipython', re.IGNORECASE),
            
            # Vision patterns in templates
            "vision": re.compile(r'vision|image|visual', re.IGNORECASE),
            
            # Multi-turn conversation patterns
            "conversation": re.compile(r'\{\{\s*range.*Messages\s*\}\}', re.IGNORECASE),
            
            # System message support
            "system": re.compile(r'\{\{\s*(?:if\s+)?\.System\s*\}\}', re.IGNORECASE),
        }

    def detect_model_capabilities(
        self, 
        model_name: str, 
        model_data: Optional[Dict] = None,
        explicit_capabilities: Optional[Set[str]] = None
    ) -> ModelCapabilities:
        """
        Detect model capabilities universally using actual Ollama model metadata.
        
        Args:
            model_name: Name of the model
            model_data: Model metadata from Ollama /api/show
            explicit_capabilities: Override capabilities if provided
            
        Returns:
            ModelCapabilities schema object with detected capabilities
        """
        # Use explicit capabilities if provided
        if explicit_capabilities is not None:
            capabilities = ModelCapabilities()
            capabilities.update_from_features(explicit_capabilities)
            self._set_technical_specs(capabilities, model_name, model_data)
            return capabilities

        # Check cache
        cache_key = f"{model_name}:{hash(str(model_data))}"
        if cache_key in self._capability_cache:
            return self._capability_cache[cache_key]

        # Initialize capabilities with universal defaults
        capabilities = ModelCapabilities(
            supports_streaming=True,  # All Ollama models support streaming
            supports_async=True,      # Our implementation supports async
        )

        # Set technical specifications first
        self._set_technical_specs(capabilities, model_name, model_data)

        if model_data:
            # 1. PRIMARY: Use native capabilities field (most reliable)
            native_capabilities = self._detect_native_capabilities(model_data)
            
            # 2. SECONDARY: Analyze template for advanced features
            template_capabilities = self._analyze_template_capabilities(model_data)
            
            # 3. TERTIARY: Check projector info for vision
            vision_capabilities = self._detect_vision_from_projector(model_data)
            
            # 4. QUATERNARY: Analyze model architecture and families
            arch_capabilities = self._detect_architecture_capabilities(model_data)
            
            # Combine all capability sources
            all_capabilities = (
                native_capabilities | 
                template_capabilities | 
                vision_capabilities | 
                arch_capabilities
            )
            
            # Apply detected capabilities to schema
            self._apply_capabilities_to_schema(capabilities, all_capabilities, model_data)
        
        # Set additional model characteristics
        self._set_model_characteristics(capabilities, model_name, model_data)
        
        # Cache the result
        self._capability_cache[cache_key] = capabilities
        
        detected_features = capabilities.to_feature_set()
        logger.info(f"Detected capabilities for {model_name}: {detected_features}")
        
        return capabilities

    def _detect_native_capabilities(self, model_data: Dict[str, Any]) -> Set[str]:
        """
        Extract capabilities from the native 'capabilities' field.
        This is the most reliable source.
        """
        capabilities = set()
        
        native_caps = model_data.get("capabilities", [])
        if isinstance(native_caps, list):
            for cap in native_caps:
                cap_lower = str(cap).lower()
                
                # Map Ollama capabilities to our feature set
                if cap_lower == "tools":
                    capabilities.add("tools")
                elif cap_lower == "vision":
                    capabilities.add("vision")
                elif cap_lower == "completion":
                    capabilities.add("completion")
                # Add more mappings as Ollama adds new capabilities
        
        return capabilities

    def _analyze_template_capabilities(self, model_data: Dict[str, Any]) -> Set[str]:
        """Analyze template with direct pattern matching."""
        capabilities = set()
        
        template = model_data.get("template", "")
        if not template:
            return capabilities
        
        # Direct pattern checks - no complex logic
        if any(pattern.search(template) for name, pattern in self._template_patterns.items() 
            if name in ["thinking", "think_tags", "think_variables", "think_conditionals"]):
            capabilities.add("thinking")
            capabilities.add("reasoning")
            logger.debug("Thinking capability detected from template")
        
        if any(pattern.search(template) for name, pattern in self._template_patterns.items() 
            if name in ["tools", "toolcalls", "function", "tool_response"]):
            capabilities.add("tools")
            logger.debug("Tools capability detected from template")
        
        if self._template_patterns["vision"].search(template):
            capabilities.add("vision")
            logger.debug("Vision capability detected from template")
        
        if self._template_patterns["conversation"].search(template):
            capabilities.add("conversation")
            logger.debug("Conversation capability detected from template")
        
        if self._template_patterns["system"].search(template):
            capabilities.add("system_messages")
            logger.debug("System capability detected from template")
        
        return capabilities

    def _detect_vision_from_projector(self, model_data: Dict[str, Any]) -> Set[str]:
        """
        Detect vision capabilities from projector_info section.
        This is definitive for vision models.
        """
        capabilities = set()
        
        projector_info = model_data.get("projector_info", {})
        if projector_info:
            # Any projector info indicates vision capability
            capabilities.add("vision")
            
            # Check for specific vision features
            if projector_info.get("clip.has_vision_encoder", False):
                capabilities.add("vision")
            
            if projector_info.get("clip.has_llava_projector", False):
                capabilities.add("vision")
                capabilities.add("multimodal")
        
        return capabilities

    def _detect_architecture_capabilities(self, model_data: Dict[str, Any]) -> Set[str]:
        """
        Detect capabilities based on model architecture and families.
        This is used as fallback and for additional context.
        """
        capabilities = set()
        
        details = model_data.get("details", {})
        
        # Check model families
        families = details.get("families", [])
        if isinstance(families, list):
            for family in families:
                family_lower = str(family).lower()
                
                if family_lower == "clip":
                    capabilities.add("vision")
                elif family_lower in ["llama", "qwen", "granite"]:
                    capabilities.add("instruct")  # These are typically instruction-tuned
        
        # Check architecture
        model_info = model_data.get("model_info", {})
        architecture = model_info.get("general.architecture", "").lower()
        
        if architecture:
            # Architecture-specific capabilities
            if "llama" in architecture:
                capabilities.add("conversation")
            elif "qwen" in architecture:
                capabilities.add("multilingual")
            elif "granite" in architecture:
                capabilities.add("enterprise")  # Granite is enterprise-focused
        
        return capabilities

    def _apply_capabilities_to_schema(
        self, 
        capabilities: ModelCapabilities, 
        detected_caps: Set[str], 
        model_data: Dict[str, Any]
    ) -> None:
        """Apply detected capabilities to the ModelCapabilities schema."""
        
        # Core capabilities
        if "tools" in detected_caps:
            capabilities.supports_tools = True
        
        if "vision" in detected_caps:
            capabilities.supports_vision = True
            capabilities.supported_formats.extend(["jpeg", "png", "gif", "webp", "bmp"])
        
        # Handle thinking capability
        if "thinking" in detected_caps or "reasoning" in detected_caps:
            capabilities.supports_thinking = True
        
        # Advanced capabilities
        if "thinking" in detected_caps:
            capabilities.specializations.append("reasoning")
        
        if "multilingual" in detected_caps:
            capabilities.languages.extend(["zh", "es", "fr", "de", "ja", "ko"])
        else:
            capabilities.languages = ["en"]  # Default to English
        
        if "enterprise" in detected_caps:
            capabilities.specializations.append("enterprise")
        
        if "conversation" in detected_caps:
            capabilities.specializations.append("conversation")
        
        # ADD: Enhanced capability inference
        # Infer additional capabilities based on model characteristics
        model_name_lower = model_data.get("name", "").lower() if model_data else ""
        
        # Text generation capability (all models can do this)
        capabilities.specializations.append("text_generation")
        
        # Code generation inference
        if any(indicator in model_name_lower for indicator in ["code", "coder", "programming"]):
            capabilities.specializations.append("code_generation")
            capabilities.supports_tools = True  # Code models typically support tools
        
        # Reasoning inference from model families/architecture
        details = model_data.get("details", {}) if model_data else {}
        families = details.get("families", [])
        
        for family in families:
            family_lower = str(family).lower()
            if family_lower in ["qwen", "llama", "granite"]:
                # These families typically support reasoning
                capabilities.specializations.append("reasoning")
                capabilities.supports_thinking = True

    def _set_technical_specs(
        self, 
        capabilities: ModelCapabilities, 
        model_name: str, 
        model_data: Optional[Dict]
    ) -> None:
        """Set technical specifications from model metadata."""
        
        if not model_data:
            # Fallback defaults
            capabilities.max_context_window = 4096
            capabilities.max_output_tokens = 2048
            return
        
        # Extract context window from model_info
        context_window = self._extract_context_window(model_data)
        capabilities.max_context_window = context_window
        
        # Calculate max output tokens (conservative approach)
        # Typically 25-50% of context window, but cap at reasonable limits
        if context_window:
            max_output = min(
                context_window // 2,  # Conservative: half of context
                8192  # Reasonable upper limit for output
            )
            capabilities.max_output_tokens = max(max_output, 512)  # Minimum 512 tokens
        else:
            capabilities.max_output_tokens = 2048

    def _extract_context_window(self, model_data: Dict[str, Any]) -> int:
        """
        Extract context window size from model metadata.
        Uses multiple strategies to find the context length.
        """
        model_info = model_data.get("model_info", {})
        
        # Strategy 1: Direct architecture-specific context length
        context_keys = [
            f"{arch}.context_length" 
            for arch in ["llama", "qwen", "qwen3", "granite", "mistral", "phi", "gemma"]
        ]
        
        for key in context_keys:
            if key in model_info:
                try:
                    return int(model_info[key])
                except (ValueError, TypeError):
                    continue
        
        # Strategy 2: Generic context keys
        generic_keys = [
            "general.context_length",
            "context_length", 
            "max_position_embeddings",
            "max_sequence_length"
        ]
        
        for key in generic_keys:
            if key in model_info:
                try:
                    return int(model_info[key])
                except (ValueError, TypeError):
                    continue
        
        # Strategy 3: Infer from model size and architecture
        param_count = model_info.get("general.parameter_count", 0)
        if param_count:
            # Rough heuristic based on parameter count
            if param_count > 60_000_000_000:  # 60B+
                return 128_000
            elif param_count > 10_000_000_000:  # 10B+
                return 32_768
            elif param_count > 1_000_000_000:   # 1B+
                return 16_384
            else:
                return 8_192
        
        # Default fallback
        return 4096

    def _set_model_characteristics(
        self, 
        capabilities: ModelCapabilities, 
        model_name: str, 
        model_data: Optional[Dict]
    ) -> None:
        """Set additional model characteristics and specializations."""
        
        if not model_data:
            return
        
        details = model_data.get("details", {})
        model_info = model_data.get("model_info", {})
        
        # Determine specializations based on model characteristics
        specializations = []
        
        # Check for coding specialization
        if any(indicator in model_name.lower() for indicator in 
               ["code", "coder", "programming", "dev", "engineer"]):
            specializations.append("code_generation")
        
        # Check for reasoning/thinking models
        template = model_data.get("template", "")
        if "thinking" in template.lower() or "think" in template.lower():
            specializations.append("reasoning")
        
        # Check for instruction tuning
        finetune = model_info.get("general.finetune", "").lower()
        if "instruct" in finetune or "chat" in finetune:
            specializations.append("instruction_following")
        
        # Check parameter size for classification
        param_size = details.get("parameter_size", "")
        if param_size:
            if "B" in param_size:  # Billion parameters
                try:
                    size = float(param_size.replace("B", ""))
                    if size >= 70:
                        specializations.append("large_scale")
                    elif size >= 10:
                        specializations.append("medium_scale") 
                    else:
                        specializations.append("efficient")
                except ValueError:
                    pass
        
        capabilities.specializations.extend(specializations)

    def detect_capabilities(
        self, 
        model_name: str, 
        model_data: Optional[Dict] = None,
        explicit_capabilities: Optional[Set[str]] = None
    ) -> Set[str]:
        """
        Backward compatibility method that returns feature set.
        """
        capabilities = self.detect_model_capabilities(model_name, model_data, explicit_capabilities)
        return capabilities.to_feature_set()

    def get_model_specifications(
        self, 
        model_name: str, 
        model_data: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Extract comprehensive model specifications.
        
        Returns:
            Dictionary with technical specifications
        """
        if not model_data:
            return {}
        
        details = model_data.get("details", {})
        model_info = model_data.get("model_info", {})
        
        specs = {
            "architecture": model_info.get("general.architecture", "unknown"),
            "parameter_count": model_info.get("general.parameter_count", 0),
            "parameter_size": details.get("parameter_size", "unknown"),
            "format": details.get("format", "unknown"),
            "quantization": details.get("quantization_level", "unknown"),
            "context_window": self._extract_context_window(model_data),
            "families": details.get("families", []),
            "capabilities": model_data.get("capabilities", []),
        }
        
        # Add vision-specific specs if available
        projector_info = model_data.get("projector_info", {})
        if projector_info:
            specs["vision"] = {
                "has_vision_encoder": projector_info.get("clip.has_vision_encoder", False),
                "image_size": projector_info.get("clip.vision.image_size", 0),
                "patch_size": projector_info.get("clip.vision.patch_size", 0),
            }
        
        return specs

    def is_model_suitable_for_task(
        self, 
        model_name: str, 
        task_requirements: Set[str],
        model_data: Optional[Dict] = None
    ) -> bool:
        """
        Check if model is suitable for specific task requirements.
        
        Args:
            model_name: Name of the model
            task_requirements: Set of required capabilities
            model_data: Model metadata
            
        Returns:
            True if model meets all requirements
        """
        capabilities = self.detect_model_capabilities(model_name, model_data)
        available_features = capabilities.to_feature_set()
        
        # Enhanced mapping for broader capability matching
        capability_aliases = {
            "streaming": {"streaming", "async"},
            "conversation": {"streaming", "async", "text_generation"},
            "text_generation": {"streaming", "async"},
            "function_calling": {"tools"},
            "multimodal": {"vision"},
            "reasoning": {"thinking", "reasoning"},
            "code_generation": {"tools", "reasoning"},
        }
        
        # Expand task requirements with aliases
        expanded_requirements = set(task_requirements)
        for req in task_requirements:
            if req in capability_aliases:
                expanded_requirements.update(capability_aliases[req])
        
        # Check if model has the core capability or related features
        for req in task_requirements:
            if req in available_features:
                continue  # Direct match
            elif req in capability_aliases:
                # Check if any alias matches
                if not any(alias in available_features for alias in capability_aliases[req]):
                    logger.debug(f"Model {model_name} missing capability: {req}")
                    return False
            else:
                # Basic capability matching
                basic_caps = {
                    "text_generation": capabilities.supports_streaming or capabilities.supports_async,
                    "vision_analysis": capabilities.supports_vision,
                    "tool_usage": capabilities.supports_tools,
                    "reasoning": capabilities.supports_thinking or "reasoning" in capabilities.specializations,
                    "coding": capabilities.supports_tools or "code_generation" in capabilities.specializations,
                }
                
                if req in basic_caps and not basic_caps[req]:
                    logger.debug(f"Model {model_name} missing basic capability: {req}")
                    return False
        
        return True

    def clear_cache(self) -> None:
        """Clear the capability cache."""
        self._capability_cache.clear()
        logger.debug("Capability cache cleared")

    def get_cache_stats(self) -> Dict[str, int]:
        """Get cache statistics."""
        return {
            "cached_models": len(self._capability_cache),
            "cache_size_bytes": sum(
                len(str(key)) + len(str(value)) 
                for key, value in self._capability_cache.items()
            )
        }