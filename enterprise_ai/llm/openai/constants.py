# Provider metadata
PROVIDER_NAME = "openai"
PROVIDER_DESCRIPTION = "OpenAI GPT models with Azure and AWS Bedrock support"
DEFAULT_MODEL = "gpt-4o-mini"
SUPPORTED_FEATURES = [
    "streaming",
    "async", 
    "tools",
    "vision",
    "reasoning",
]

# Model categories
REASONING_MODELS = ["o1", "o3-mini"]
MULTIMODAL_MODELS = [
    "gpt-4-vision-preview",
    "gpt-4o",
    "gpt-4o-mini",
    "claude-3-opus-20240229",
    "claude-3-sonnet-20240229",
    "claude-3-haiku-20240307",
]