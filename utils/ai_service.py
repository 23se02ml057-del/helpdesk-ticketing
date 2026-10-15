"""
OpenRouter AI Service for Help Desk & Ticket Management System.

This module provides a production-ready wrapper around the OpenRouter API.
It handles authentication, timeouts, error handling, and response validation.

Architecture:
    - Configuration is read from Flask app config (sourced from .env)
    - OpenAI client is initialized lazily within app context
    - All API calls return structured JSON responses
    - Specific exceptions are caught and logged appropriately

Usage in Flask routes:
    from utils.ai_service import AIService
    ai_service = AIService()

    # Within a request context:
    result = ai_service.chat(messages=[...])
    summary = ai_service.summarize_ticket(subject, description)
"""

import json  # Used for parsing JSON responses from AI
import logging  # Used for logging errors and debug info
import re  # Used for word boundary matching
from typing import Optional, List, Dict, Any  # Type hints for better code clarity

# OpenAI SDK - OpenRouter is fully compatible with the OpenAI API format
from openai import OpenAI, APITimeoutError, APIError, APIConnectionError, RateLimitError, AuthenticationError, NotFoundError
from flask import current_app  # Access Flask app config within request context


# ---------------------------------------------------------------------------
# Module-level logger - logs ai_service events to Flask's logger
# ---------------------------------------------------------------------------
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
# These are the Flask config keys defined in config.py
# Using constants prevents typos when accessing config values
CONFIG_API_KEY = "OPENROUTER_API_KEY"  # API key for OpenRouter authentication
CONFIG_BASE_URL = "OPENROUTER_BASE_URL"  # Base URL for OpenRouter API
CONFIG_MODEL = "OPENROUTER_MODEL"  # Default AI model to use
CONFIG_FALLBACK_MODELS = "OPENROUTER_FALLBACK_MODELS"  # Fallback models if primary fails
CONFIG_SITE_URL = "OPENROUTER_SITE_URL"  # Site URL required by OpenRouter
CONFIG_APP_NAME = "OPENROUTER_APP_NAME"  # App name shown in OpenRouter dashboard
CONFIG_TIMEOUT = "OPENROUTER_TIMEOUT"  # Request timeout in seconds

# Default values used when config keys are missing from .env
DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"  # OpenRouter's official API endpoint
DEFAULT_MODEL = "poolside/laguna-s-2.1:free"  # Free tier model
DEFAULT_SITE_URL = "http://localhost:5000"  # Default local development URL
DEFAULT_APP_NAME = "HelpDesk AI"  # Default app name
DEFAULT_TIMEOUT = 60  # Default timeout of 60 seconds for API requests


class AIServiceError(Exception):
    """
    Base exception class for AI Service errors.
    All AI-related exceptions inherit from this class,
    making it easy to catch all AI errors with a single except block.
    """
    pass


class AIConfigurationError(AIServiceError):
    """
    Raised when OpenRouter is not properly configured.
    Typically means the API key is missing or invalid.
    """
    pass


class AIAPIError(AIServiceError):
    """
    Raised when the OpenRouter API returns an error response.
    Contains the error message from the API.
    """
    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code  # HTTP status code if available


class AIResponseError(AIServiceError):
    """
    Raised when the AI response is invalid or cannot be parsed.
    For example, when JSON parsing fails or required fields are missing.
    """
    pass


class AIService:
    """
    Production-ready OpenRouter AI Service wrapper.
    
    This class provides a clean interface to OpenRouter's API with:
    - Automatic configuration loading from Flask app config
    - Lazy initialization of the OpenAI client
    - Request timeout handling
    - Comprehensive error handling and logging
    - Structured JSON responses for all operations
    
    All methods must be called within a Flask application context
    because they access current_app.config.
    
    Example:
        from flask import Flask
        from utils.ai_service import AIService
        
        app = Flask(__name__)
        ai_service = AIService()
        
        with app.app_context():
            result = ai_service.chat([{"role": "user", "content": "Hello"}])
    """
    
    def __init__(self):
        """
        Initialize the AIService instance.
        
        The OpenAI client is NOT created here because we need a Flask
        application context to access config values. The client is created
        lazily on first use via _get_client().
        """
        self._client: Optional[OpenAI] = None  # Private attribute for the OpenAI client
    
    def _get_config(self) -> Dict[str, Any]:
        """
        Retrieve OpenRouter configuration from Flask app config.
        """
        config = current_app.config
        
        api_key = config.get(CONFIG_API_KEY, "").strip()
        
        logger.info("[OpenRouter] Loading configuration")
        
        if not api_key:
            raise AIConfigurationError(
                f"OpenRouter API key not configured. "
                f"Set {CONFIG_API_KEY} in your .env file."
            )
        
        fallback_models = config.get(CONFIG_FALLBACK_MODELS, "")
        if isinstance(fallback_models, str):
            fallback_models = [m.strip() for m in fallback_models.split(",") if m.strip()]
        else:
            fallback_models = []
        
        return {
            "api_key": api_key,
            "base_url": config.get(CONFIG_BASE_URL, DEFAULT_BASE_URL).strip(),
            "model": config.get(CONFIG_MODEL, DEFAULT_MODEL).strip(),
            "fallback_models": fallback_models,
            "site_url": config.get(CONFIG_SITE_URL, DEFAULT_SITE_URL).strip(),
            "app_name": config.get(CONFIG_APP_NAME, DEFAULT_APP_NAME).strip(),
            "timeout": int(config.get(CONFIG_TIMEOUT, DEFAULT_TIMEOUT)),
        }
    
    def _get_client(self) -> OpenAI:
        """
        Get or create the OpenAI client configured for OpenRouter.
        
        Uses lazy initialization: the client is created only on first use
        and then cached for subsequent calls. This avoids creating the
        client outside of an application context.
        
        Returns:
            OpenAI client instance configured for OpenRouter
            
        Raises:
            AIConfigurationError: If configuration is invalid
        """
        # If client already exists, return it (cached)
        if self._client is not None:
            return self._client
        
        # Get configuration - this validates the API key exists
        config = self._get_config()
        
        # Create the OpenAI client with OpenRouter-specific settings
        # base_url tells the SDK to send requests to OpenRouter instead of OpenAI
        # default_headers are required by OpenRouter for analytics and tracking
        self._client = OpenAI(
            api_key=config["api_key"],  # Authentication key
            base_url=config["base_url"],  # OpenRouter API endpoint
            timeout=config["timeout"],  # Request timeout in seconds
            default_headers={
                "HTTP-Referer": config["site_url"],  # Required by OpenRouter
                "X-Title": config["app_name"],  # Your app name for OpenRouter dashboard
            },
        )
        
        logger.info(f"OpenRouter client initialized with model: {config['model']}")
        return self._client
    
    def is_configured(self) -> bool:
        """
        Check if OpenRouter is properly configured.
        
        This is a safe way to check configuration without making an API call.
        Can be used to show/hide AI features in the UI.
        
        Returns:
            bool: True if API key is configured, False otherwise
        """
        try:
            config = self._get_config()
            return bool(config["api_key"])
        except AIConfigurationError:
            return False
    
    def _validate_messages(self, messages: List[Dict[str, str]]) -> None:
        """
        Validate the messages parameter for chat completions.
        
        Args:
            messages: List of message dictionaries
            
        Raises:
            ValueError: If messages is empty or contains invalid entries
            TypeError: If messages is not a list
        """
        # Messages must be a list
        if not isinstance(messages, list):
            raise TypeError(f"messages must be a list, got {type(messages).__name__}")
        
        # Messages cannot be empty
        if not messages:
            raise ValueError("messages list cannot be empty")
        
        # Each message must be a dict with 'role' and 'content' keys
        for i, msg in enumerate(messages):
            if not isinstance(msg, dict):
                raise ValueError(f"Message {i} must be a dictionary, got {type(msg).__name__}")
            if "role" not in msg:
                raise ValueError(f"Message {i} missing 'role' key")
            if "content" not in msg:
                raise ValueError(f"Message {i} missing 'content' key")
            if msg["role"] not in ("system", "user", "assistant"):
                raise ValueError(f"Message {i} has invalid role: {msg['role']}")
    
    def _validate_response(self, response: Any) -> str:
        """
        Validate and extract content from an OpenRouter API response.
        
        Args:
            response: The raw response object from OpenAI SDK
            
        Returns:
            str: The AI-generated content text
            
        Raises:
            AIResponseError: If response is invalid or content is missing
        """
        # Check if response has choices
        if not hasattr(response, "choices") or not response.choices:
            raise AIResponseError("API response missing 'choices' field")
        
        # Get the first choice (we only request one)
        choice = response.choices[0]
        
        # Check if choice has message
        if not hasattr(choice, "message"):
            raise AIResponseError("API response choice missing 'message' field")
        
        # Check if message has content
        if not hasattr(choice.message, "content") or choice.message.content is None:
            raise AIResponseError("API response message missing 'content' field")
        
        # Return the content string
        content = choice.message.content.strip()
        
        # Content should not be empty
        if not content:
            raise AIResponseError("API returned empty content")
        
        # Check if the model returned an image error as text content
        # Some models return errors as text instead of raising exceptions
        content_lower = content.lower()
        image_error_phrases = [
            "cannot read image",
            "does not support image",
            "image input",
            "unsupported image",
            "image type",
            "multimodal",
            "vision model",
            "no endpoints found that support image",
        ]
        if any(phrase in content_lower for phrase in image_error_phrases):
            raise AIResponseError(
                "AI service cannot process images. Please remove any images from your message and try again."
            )
        
        return content
    
    @staticmethod
    def _strip_image_references(text: str) -> str:
        if not isinstance(text, str):
            return text
        original = text
        text = re.sub(r"data:image\/[^;]+;base64,[A-Za-z0-9+/=]+", "[image removed]", text, flags=re.IGNORECASE)
        text = re.sub(r"<img[^>]*src\s*=\s*['\"][^'\"]*['\"][^>]*>", "[image removed]", text, flags=re.IGNORECASE)
        text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "[image removed]", text, flags=re.IGNORECASE)
        for ext in ("png", "jpg", "jpeg", "gif", "webp", "svg", "ico", "bmp", "tiff"):
            text = re.sub(r"(?i)\b[\w\-]+(?:\.[\w\-]+)*\." + ext + r"\b", "[image removed]", text)
            text = re.sub(r"(?i)\b[\w\-]+(?:\.[\w\-]+)*\." + ext.upper() + r"\b", "[image removed]", text)
        for ext in ("png", "jpg", "jpeg", "gif", "webp", "svg", "ico", "bmp", "tiff"):
            text = re.sub(r"(?i)\.[\w\-]+" + ext + r"\b", "[image removed]", text)
            text = re.sub(r"(?i)\.[\w\-]+" + ext.upper() + r"\b", "[image removed]", text)
        text = re.sub(r"(?i)\bimage\.[a-z]{1,4}\b", "[image removed]", text)
        text = re.sub(r"(?i)\bscreenshot\.[a-z]{1,4}\b", "[image removed]", text)
        if text != original:
            logger.warning(f"[AI] Stripped image references from text: {original[:200]}...")
        return text

    def _sanitize_message(self, msg: Dict[str, Any]) -> Dict[str, Any]:
        clean_msg = {"role": msg.get("role", "user"), "content": msg.get("content", "")}
        for key in list(clean_msg.keys()):
            if key.lower() in ("image", "image_url", "images", "file", "files", "attachment", "attachments"):
                del clean_msg[key]
        if isinstance(clean_msg["content"], str):
            clean_msg["content"] = self._strip_image_references(clean_msg["content"])
        elif isinstance(clean_msg["content"], list):
            sanitized_content = []
            for item in clean_msg["content"]:
                if isinstance(item, dict):
                    if item.get("type") in ("image_url", "image", "file", "attachment"):
                        continue
                    if item.get("type") == "text" and isinstance(item.get("text"), str):
                        item = dict(item)
                        item["text"] = self._strip_image_references(item["text"])
                    sanitized_content.append(item)
            clean_msg["content"] = sanitized_content if sanitized_content else " "
        return clean_msg
    
    def chat(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> Dict[str, Any]:
        """
        Send a chat completion request to OpenRouter.
        
        This is the core method that all other AI methods use internally.
        It handles the raw API communication, timeout, and error handling.
        
        Args:
            messages: List of message dictionaries with 'role' and 'content' keys.
                     Example: [
                         {"role": "system", "content": "You are a helpful assistant."},
                         {"role": "user", "content": "Hello!"}
                     ]
            model: Override the default model for this specific request.
                  If None, uses the model from .env configuration.
            temperature: Controls randomness of the response.
                        Range: 0.0 (deterministic) to 1.0 (creative).
                        Default: 0.7
            max_tokens: Maximum number of tokens to generate in the response.
                       Default: 1024
        
        Returns:
            Dict with the following structure:
            On success:
            {
                "success": True,
                "content": str,  # The AI-generated text
                "model": str,    # The model that generated the response
                "finish_reason": str,  # Why generation stopped (e.g., "stop")
                "total_tokens": int  # Total tokens used (prompt + completion)
            }
            
            On failure:
            {
                "success": False,
                "error": str,  # Error message
                "content": ""  # Always empty on failure
            }
        """
        # Validate input messages before making API call
        self._validate_messages(messages)
        
        config = self._get_config()
        client = self._get_client()
        
        models_to_try = [model or config["model"]] + config.get("fallback_models", [])
        tried_models = []
        
        for selected_model in models_to_try:
            if selected_model in tried_models:
                continue
            tried_models.append(selected_model)
            
            try:
                logger.info(f"[OpenRouter] Attempting model: {selected_model}")
                
                sanitized_messages = [self._sanitize_message(msg) for msg in messages]
                
                for msg in sanitized_messages:
                    if isinstance(msg.get("content"), str):
                        stripped = self._strip_image_references(msg["content"])
                        if stripped != msg["content"]:
                            logger.warning(f"[OpenRouter] Aggressive image strip applied before API call")
                            msg["content"] = stripped
                
                response = client.chat.completions.create(
                    model=selected_model,
                    messages=sanitized_messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                
                content = self._validate_response(response)
                logger.info(f"[OpenRouter] Success with model: {selected_model}")
                return {
                    "success": True,
                    "content": content,
                    "model": response.model,
                    "finish_reason": response.choices[0].finish_reason,
                    "total_tokens": response.usage.total_tokens if response.usage else None,
                }
            
            except RateLimitError as e:
                logger.warning(f"[OpenRouter] Rate limit on {selected_model}: {str(e)}")
                continue
            
            except NotFoundError as e:
                logger.warning(f"[OpenRouter] Model not found {selected_model}: {str(e)}")
                continue
            
            except AuthenticationError as e:
                error_msg = "OpenRouter authentication failed. Please check your API key."
                logger.error(error_msg)
                return {
                    "success": False,
                    "error": error_msg,
                    "content": "",
                }
            
            except APITimeoutError as e:
                logger.warning(f"[OpenRouter] Timeout on {selected_model}: {str(e)}")
                continue
            
            except APIConnectionError as e:
                logger.warning(f"[OpenRouter] Connection error on {selected_model}: {str(e)}")
                continue
            
            except APIError as e:
                status_code = getattr(e, 'status_code', None)
                error_code = getattr(e, 'code', None)
                error_str = str(e)
                is_image_error = any(phrase in error_str.lower() for phrase in [
                    "does not support image",
                    "no endpoints found that support image",
                    "image input",
                    "cannot read image",
                    "cannot read \"image",
                    "image.png",
                    "unsupported image",
                    "image type",
                    "vision",
                    "multimodal",
                ])
                if is_image_error:
                    logger.warning(f"[OpenRouter] Image input not supported on {selected_model}: {error_str}")
                    return {
                        "success": False,
                        "error": "AI service cannot process images. Please remove any images from your message and try again.",
                        "content": "",
                    }
                if status_code in (429, 404, 400) or (isinstance(error_code, str) and error_code in ("rate_limit_exceeded", "model_not_found", "invalid_request_error")):
                    logger.warning(f"[OpenRouter] Error {status_code} / {error_code} on {selected_model}: {error_str}")
                    continue
                logger.error(f"[OpenRouter] API error on {selected_model}: {error_str}")
                if hasattr(e, 'body') and e.body is not None:
                    logger.error(f"[OpenRouter] Response body: {e.body}")
                return {
                    "success": False,
                    "error": "AI service encountered an error. Please try again later.",
                    "content": "",
                }
            
            except AIResponseError as e:
                error_msg = str(e)
                is_image_error = "cannot process images" in error_msg.lower() or "image" in error_msg.lower()
                if is_image_error:
                    logger.warning(f"[OpenRouter] Image error from {selected_model}: {error_msg}")
                    return {
                        "success": False,
                        "error": error_msg,
                        "content": "",
                    }
                logger.warning(f"[OpenRouter] Invalid response from {selected_model}: {error_msg}")
                continue
            
            except Exception as e:
                logger.warning(f"[OpenRouter] Unexpected error on {selected_model}: {str(e)}")
                continue
        
        logger.error(f"[OpenRouter] All models failed: {tried_models}")
        return {
            "success": False,
            "error": "All AI models are currently unavailable. Please try again later.",
            "content": "",
        }
    
    # -------------------------------------------------------------------
    # Deterministic classification rules (no LLM randomness)
    # -------------------------------------------------------------------
    
    _CATEGORY_RULES = {
        "Network": [
            "internet", "wifi", "lan", "wan", "vpn", "router", "switch", "firewall",
            "dns", "ip address", "server network", "network cable", "bandwidth",
            "slow internet", "no internet", "connection lost", "network error",
            "network", "connectivity", "ethernet", "proxy", "subnet", "gateway",
            "dhcp", "nat", "packet loss", "latency", "throughput",
            "hacking", "password hacking", "wifi security", "wireless security",
            "unauthorized access", "security issue", "intrusion"
        ],
        "Hardware": [
            "printer", "mouse", "keyboard", "laptop", "desktop", "cpu", "monitor",
            "scanner", "webcam", "ram", "hard disk", "ssd", "battery", "power supply",
            "usb", "speaker", "microphone", "paper jam", "hardware failure",
            "hardware", "device", "peripheral", "touchpad", "screen", "display",
            "charger", "adapter", "motherboard", "graphics card", "fan", "heating",
            "not proper working", "not working properly", "damaged", "broken"
        ],
        "Software": [
            "application", "software", "windows", "linux", "ms office", "outlook",
            "gmail", "chrome", "browser", "login", "software installation", "update error",
            "application crash", "excel", "word", "powerpoint", "email", "operating system",
            "bug", "program", "app", "sap", "erp", "crm", "database", "sql", "oracle",
            "java", "python", "coding", "development", "api", "integration", "plugin",
            "not opening", "not starting", "crash", "freeze", "hang", "error message"
        ],
        "Financial": [
            "invoice", "payment", "expense", "budget", "tax", "gst", "purchase order",
            "billing", "refund", "vendor payment", "financial report", "accounts",
            "finance", "accounting", "revenue", "cost", "audit", "receipt", "voucher",
            "cheque", "bank", "transaction", "ledger", "balance sheet", "profit loss",
            "not successfully", "failed payment", "payment failure", "transaction failed"
        ],
        "HR": [
            "payroll", "salary", "leave", "attendance", "employee id", "hr policy",
            "recruitment", "offer letter", "joining", "resignation", "hr", "human resource",
            "bonus", "increment", "promotion", "transfer", "leave balance", "holiday",
            "timesheet", "time sheet", "performance", "appraisal", "employee record"
        ],
        "Technical": [
            "password reset", "account locked", "user creation", "user access",
            "active directory", "authentication", "permission issue", "profile issue",
            "domain login", "system access", "password", "reset", "locked", "account",
            "user id", "login issue", "access denied", "credential", "mfa", "otp",
            "two factor", "single sign on", "sso", "identity", "provisioning",
            "server", "network infrastructure", "data center", "cloud", "aws", "azure"
        ],
    }
    
    _PRIORITY_RULES = {
        "Critical": [
            ("server down", 5), ("entire office down", 5), ("all users down", 5), ("network failure", 5),
            ("data loss", 5), ("security breach", 5), ("system down", 5), ("complete outage", 5),
            ("production down", 5), ("critical failure", 5), ("major outage", 5), ("outage", 4),
            ("database corrupted", 5), ("database crash", 5), ("server crash", 5),
            ("cannot work", 4), ("unavailable", 4), ("down for everyone", 4), ("all services down", 4),
            ("ransomware", 5), ("breach", 4),
            ("complete failure", 5), ("all systems down", 5), ("company wide down", 5),
            ("payment gateway down", 5), ("transaction failure", 4), ("cannot access anything", 5),
            ("firewall down", 5), ("dns failure", 4), ("active directory down", 5),
            ("data corruption", 5), ("entire office", 4),
            ("all users", 4), ("everyone", 3), ("whole company", 4), ("company wide", 4),
            ("security issue", 4), ("unauthorized access", 5), ("data breach", 5),
            ("critical system", 4), ("emergency", 5), ("urgent", 4),
            ("critical server", 5), ("server outage", 5), ("critical outage", 5)
        ],
        "High": [
            ("internet slow", 2), ("internet not working", 3), ("application not working", 3), ("vpn not connecting", 3),
            ("multiple users affected", 3), ("team affected", 3), ("sla breach", 3), ("urgent", 3), ("important", 3),
            ("deadline", 3), ("meeting", 2), ("presentation", 3), ("client", 2), ("customer facing", 3),
            ("not sending", 2), ("cannot access", 3), ("blocked", 3), ("asap", 3), ("immediate", 3),
            ("critical issue", 3), ("high priority", 3), ("escalate", 3), ("not reaching", 2),
            ("connection refused", 3), ("timeout", 2), ("504", 3), ("500", 3), ("503", 3),
            ("email not working", 3), ("application crash", 3), ("software crash", 3), ("system overheating", 3),
            ("internet completely down", 4), ("completely down", 4), ("totally down", 4),
            ("multiple employees", 3), ("whole team", 3), ("entire department", 3),
            ("vpn disconnected", 3), ("remote access down", 3), ("remote desktop down", 3),
            ("server issue", 3), ("network issue", 2), ("wifi down", 3), ("wi-fi down", 3),
            ("database issue", 3), ("sql error", 3), ("oracle error", 3),
            ("crash", 2), ("system crash", 3), ("frequent crash", 4), ("keeps crashing", 4),
            ("payment failure", 3), ("payment failed", 3), ("transaction failed", 3), ("billing issue", 3),
            ("security alert", 3), ("virus", 3), ("malware", 3), ("phishing", 3),
            ("data backup failed", 4), ("backup failure", 4), ("restore failed", 4),
            ("server unreachable", 3), ("internet down", 3), ("internet not working", 3),
            ("not functioning", 2), ("malfunctioning", 2), ("down", 2),
            ("hacking", 4), ("hacked", 5), ("security issue", 3), ("unauthorized", 4), ("intrusion", 4),
            ("not opening", 2), ("not starting", 2), ("failure", 2),
            ("payment issue", 3), ("payment not successfully", 3), ("transaction issue", 3),
            ("server down", 5), ("outage", 4), ("critical failure", 4), ("major outage", 4),
            ("firewall down", 5), ("dns failure", 4), ("data loss", 5), ("data corruption", 5),
            ("ransomware", 5), ("breach", 4), ("company wide down", 4), ("all systems down", 4)
        ],
        "Medium": [
            ("printer issue", 2), ("laptop slow", 2), ("single user", 1),
            ("standard", 1), ("normal", 1), ("minor", 1), ("workaround available", 1),
            ("slow", 1), ("performance", 1), ("lag", 1), ("freeze", 1), ("hang", 1),
            ("update", 1), ("install", 1), ("configuration", 1), ("setup", 1), ("request", 1),
            ("problem", 1), ("error", 1), ("failed", 1), ("not responding", 1), ("not loading", 1), ("stuck", 1), ("frozen", 1),
            ("email not receiving", 2), ("network cable disconnected", 2), ("disconnected", 1),
            ("wifi issue", 2), ("connection issue", 2), ("connectivity issue", 2),
            ("software issue", 2), ("application error", 2), ("login issue", 2),
            ("screen flicker", 2), ("display issue", 2), ("sound issue", 2), ("audio issue", 2),
            ("printing issue", 2), ("scan issue", 2), ("scanner issue", 2),
            ("peripheral", 1), ("device issue", 1), ("hardware issue", 1),
            ("configuration issue", 2), ("setup issue", 2), ("access issue", 2),
            ("help", 1), ("assistance", 1), ("support needed", 1),
            ("network issue", 2), ("internet issue", 2), ("connectivity problem", 2),
            ("blue screen", 2), ("bsod", 2), ("screen flickering", 2),
            ("slow internet", 2), ("internet speed", 1), ("bandwidth", 1),
            ("error message", 1), ("popup", 1), ("notification", 1),
            ("internet slow", 2), ("slow connection", 2), ("intermittent", 1),
            ("very slow", 2), ("extremely slow", 2), ("sluggish", 2)
        ],
        "Low": [
            ("mouse issue", 1), ("keyboard issue", 1), ("monitor issue", 1), ("cosmetic", 1),
            ("enhancement", 1), ("nice to have", 1), ("non critical", 1), ("low priority", 1),
            ("slightly", 1), ("minor issue", 1), ("annoying", 1), ("inconvenience", 1), ("small", 1),
            ("question", 1), ("query", 1), ("information", 1), ("how to", 1), ("tutorial", 1),
            ("mouse", 1), ("keyboard", 1), ("monitor", 1), ("webcam", 1), ("speaker", 1), ("microphone", 1),
            ("battery", 1), ("touchpad", 1), ("screen flicker", 1), ("display", 1), ("charger", 1),
            ("paper jam", 1), ("toner", 1), ("cartridge", 1), ("dust", 1), ("clean", 1),
            ("mouse not working", 1), ("printer not printing", 1), ("password reset", 1),
            ("keyboard not working", 1), ("monitor flickering", 1), ("speaker not working", 1),
            ("webcam not working", 1), ("microphone not working", 1), ("battery issue", 1),
            ("touchpad issue", 1), ("charger issue", 1), ("adapter issue", 1),
            ("cosmetic damage", 1), ("scratch", 1), ("dent", 1), ("stain", 1),
            ("printer", 1), ("mouse", 1), ("keyboard", 1), ("monitor", 1),
            ("webcam", 1), ("speaker", 1), ("microphone", 1), ("battery", 1),
            ("touchpad", 1), ("charger", 1), ("adapter", 1), ("paper jam", 1),
            ("not proper working", 1), ("not working properly", 1), ("minor inconvenience", 1)
        ],
    }
    
    _CATEGORY_TO_DEPARTMENT = {
        "Network": "Networking",
        "Hardware": "Hardware",
        "Software": "Software Team",
        "Technical": "Technical",
        "HR": "HR",
        "Financial": "Financial",
    }
    
    @classmethod
    def classify_category(cls, title: str, description: str) -> Dict[str, Any]:
        text = f"{title} {description}".lower()
        scores = {}
        for category, keywords in cls._CATEGORY_RULES.items():
            score = sum(1 for kw in keywords if kw in text)
            scores[category] = score
        
        best = max(scores, key=scores.get)
        if scores[best] == 0:
            return {
                "success": True,
                "category": "Technical",
                "confidence": "low",
                "reasoning": "No keywords matched, defaulting to Technical",
            }
        
        confidence = "high" if scores[best] >= 2 else "medium" if scores[best] == 1 else "low"
        return {
            "success": True,
            "category": best,
            "confidence": confidence,
            "reasoning": f"Matched {scores[best]} keyword(s) for {best}",
        }
    
    @classmethod
    def classify_priority(cls, title: str, description: str, category: str = None) -> Dict[str, Any]:
        text = f"{title} {description}".lower()
        
        def word_boundary_match(keyword: str, content: str) -> bool:
            pattern = r'\b' + re.escape(keyword) + r'\b'
            return bool(re.search(pattern, content))
        
        # Severity modifiers that amplify or reduce priority
        amplifiers = {
            "completely": ("Critical", 1.5), "totally": ("Critical", 1.5), "entirely": ("Critical", 1.5), "fully": ("Critical", 1.5),
            "all": ("High", 1.3), "every": ("High", 1.3), "multiple": ("High", 1.3), "several": ("High", 1.2),
            "urgent": ("High", 1.5), "asap": ("High", 1.5), "immediate": ("High", 1.5), "critical": ("Critical", 1.5),
            "emergency": ("Critical", 1.5), "deadline": ("High", 1.3), "important": ("High", 1.2),
            "cannot": ("High", 1.2), "unable": ("High", 1.2), "blocked": ("High", 1.2),
            "down": ("High", 1.2), "outage": ("Critical", 1.3), "failure": ("High", 1.2), "crashed": ("High", 1.2)
        }
        
        reducers = {
            "slightly": 0.7, "minor": 0.7, "small": 0.7, "cosmetic": 0.5,
            "nice to have": 0.5, "enhancement": 0.5, "optional": 0.6,
            "when possible": 0.7, "low priority": 0.5, "non-critical": 0.5,
            "eventually": 0.6, "someday": 0.5, "would be nice": 0.5
        }
        
        scope_indicators = {
            "entire office": ("Critical", 3), "all users": ("Critical", 3),
            "company wide": ("Critical", 3), "everyone": ("Critical", 2),
            "whole team": ("High", 1), "multiple users": ("High", 1),
            "team affected": ("High", 1), "department": ("High", 0.5),
            "single user": ("Low", -1), "only me": ("Low", -1), "just me": ("Low", -1),
            "one person": ("Low", -1), "my computer": ("Low", -0.5),
            "my laptop": ("Low", -0.5), "my desk": ("Low", -0.5)
        }
        
        scores = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0}
        
        # Score based on weighted keyword matches using word boundaries
        for priority, keywords in cls._PRIORITY_RULES.items():
            for keyword, weight in keywords:
                if word_boundary_match(keyword, text):
                    match = re.search(r'\b' + re.escape(keyword) + r'\b', text)
                    if match:
                        keyword_idx = match.start()
                        context_before = text[max(0, keyword_idx-50):keyword_idx]
                        context_after = text[keyword_idx:keyword_idx+50]
                        context = context_before + " " + context_after
                        
                        multiplier = 1.0
                        for amp, (target_priority, mult) in amplifiers.items():
                            if word_boundary_match(amp, context) and priority == target_priority:
                                multiplier *= mult
                        
                        for red, mult in reducers.items():
                            if word_boundary_match(red, context):
                                multiplier *= mult
                        
                        scores[priority] += weight * multiplier
        
        # Score based on scope indicators using word boundaries
        for scope, (priority, boost) in scope_indicators.items():
            if word_boundary_match(scope, text):
                scores[priority] += max(1, abs(boost) * 2)
        
        # Context-aware adjustments
        critical_context = ["data loss", "data corruption", "security breach", "hacked", "ransomware",
                          "server down", "database corrupted", "database crash", "server crash",
                          "all systems down", "company wide", "entire office", "production down",
                          "server unreachable", "cannot access anything"]
        for phrase in critical_context:
            if word_boundary_match(phrase, text):
                scores["Critical"] += 3
        
        high_context = ["payment failed", "payment failure", "transaction failed", "not receiving emails",
                       "email not working", "vpn not connecting", "remote access down",
                       "software crash", "system overheating", "multiple employees",
                       "customer facing", "client meeting", "deadline today", "server unreachable"]
        for phrase in high_context:
            if word_boundary_match(phrase, text):
                scores["High"] += 2
        
        low_context = ["mouse not working", "keyboard not working", "monitor flickering",
                      "printer not printing", "password reset", "webcam not working",
                      "speaker not working", "touchpad issue", "charger issue",
                      "single user", "only my", "just my", "forgot my password",
                      "forgot password", "password forgotten"]
        for phrase in low_context:
            if word_boundary_match(phrase, text):
                scores["Low"] += 2
        
        # Adjust for scope: if it's a slow/single-user issue, don't let scope push to Critical
        slow_indicators = ["slow", "lag", "performance", "speed"]
        is_slow_issue = any(word_boundary_match(ind, text) for ind in slow_indicators)
        if is_slow_issue:
            for scope, (priority, boost) in scope_indicators.items():
                if word_boundary_match(scope, text) and priority == "Critical":
                    scores["Critical"] -= 2
        
        # Category-aware priority adjustments
        if category:
            category_lower = category.lower()
            if category_lower == "hardware":
                for phrase in ["not working", "not proper working", "issue", "problem", "broken", "damaged"]:
                    if word_boundary_match(phrase, text):
                        scores["Low"] += 2
                        scores["High"] = max(0, scores["High"] - 1)
            elif category_lower == "network":
                for phrase in ["slow", "lag", "speed", "intermittent", "disconnected", "not working", "not connecting"]:
                    if word_boundary_match(phrase, text):
                        if phrase in ["not working", "not connecting"]:
                            scores["High"] += 2
                        else:
                            scores["Medium"] += 2
                        scores["Critical"] = max(0, scores["Critical"] - 1)
            elif category_lower == "financial":
                for phrase in ["payment", "transaction", "billing", "invoice", "not successfully", "failed"]:
                    if word_boundary_match(phrase, text):
                        scores["High"] += 2
            elif category_lower == "software":
                for phrase in ["crash", "error", "not opening", "not starting", "freeze", "hang"]:
                    if word_boundary_match(phrase, text):
                        scores["Medium"] += 2
                        scores["High"] = max(0, scores["High"] - 1)
        
        # Determine winner
        best_priority = max(scores, key=scores.get)
        best_score = scores[best_priority]
        
        # Calculate confidence
        if best_score >= 5:
            confidence = "high"
        elif best_score >= 3:
            confidence = "medium"
        else:
            confidence = "low"
        
        # Category-aware fallback instead of blindly defaulting to Medium
        if best_score == 0:
            if category:
                category_lower = category.lower()
                if category_lower == "hardware":
                    best_priority = "Low"
                else:
                    best_priority = "Medium"
            else:
                best_priority = "Medium"
            confidence = "low"
        
        reasoning = f"Severity scoring: Critical={scores['Critical']}, High={scores['High']}, Medium={scores['Medium']}, Low={scores['Low']}"
        
        return {
            "success": True,
            "priority": best_priority,
            "confidence": confidence,
            "reasoning": reasoning,
        }
    
    @classmethod
    def get_department_for_category(cls, category: str) -> str:
        return cls._CATEGORY_TO_DEPARTMENT.get(category, "IT management")
    
    def classify_category_from_db(self, ticket_subject: str, ticket_description: str) -> Dict[str, Any]:
        from flask import current_app
        from help_db import db
        from sqlalchemy import text
        
        with current_app.app_context():
            db_categories = db.session.execute(
                text("SELECT category_name FROM categories ORDER BY category_name")
            ).fetchall()
            available_categories = [r[0] for r in db_categories]
        
        if not available_categories:
            return {
                "success": False,
                "category": None,
                "reasoning": "No categories available in database",
                "error": "No categories found",
            }
        
        text_content = f"{ticket_subject} {ticket_description}".lower()
        
        category_hints = {
            "Wi-Fi Issue": ["wifi", "wireless", "wi-fi", "internet not working on laptop", "wireless connection", "wifi password", "wifi not connecting"],
            "Network Issue": ["network", "lan", "wan", "router", "switch", "dns", "dhcp", "vpn", "firewall", "ethernet", "cable", "connectivity", "network speed", "slow internet"],
            "Hardware Issue": ["printer", "mouse", "keyboard", "laptop", "monitor", "hardware", "device", "computer", "desktop", "ram", "hard disk", "motherboard", "power supply"],
            "Software Issue": ["software", "application", "app", "browser", "ms office", "email", "outlook", "gmail", "installation", "error", "crash", "bug"],
            "System Access": ["password reset", "account locked", "windows login", "user account", "domain login", "access", "login issue", "system access"],
            "Email Issue": ["email", "gmail", "outlook", "mail not working", "email configuration", "email recovery"],
            "Login Issue": ["login", "cannot login", "login problem", "credential", "authentication"],
            "Password Reset": ["password reset", "forgot password", "reset password", "password change"],
            "Printer Issue": ["printer", "print", "printing", "printer not working", "printer jam"],
            "Payment Issue": ["payment", "billing", "invoice", "transaction", "refund", "payment failed"],
            "Billing": ["billing", "invoice", "payment", "charge", "billing problem"],
            "Invoice": ["invoice", "billing", "payment", "invoice issue"],
            "Expense": ["expense", "reimbursement", "cost", "expense report"],
            "Reimbursement": ["reimbursement", "expense refund", "claim"],
            "Salary": ["salary", "payroll", "payslip", "salary issue"],
            "Attendance": ["attendance", "time tracking", "check-in", "check-out", "attendance system"],
            "Employee Benefits": ["benefits", "insurance", "leave benefits", "employee benefits"],
            "Employee Documents": ["employee document", "document", "verification", "records", "hr documents", "employee records", "document management", "document verification"],
            "Leave Request": ["leave", "vacation", "holiday", "leave balance", "leave approval"],
            "Payroll": ["payroll", "salary processing", "payslip", "payroll issue"],
            "Recruitment": ["recruitment", "hiring", "onboarding", "interview", "job posting"],
            "Asset Request": ["asset", "laptop request", "device request", "asset allocation"],
            "Facilities": ["facilities", "room booking", "office facility", "maintenance request"],
            "General Administration": ["administration", "general admin", "office support", "admin task"],
            "ID Card": ["id card", "access card", "identity card", "id card issue"],
            "Office Maintenance": ["maintenance", "repair", "office repair", "facility repair"],
            "Account Issue": ["account", "profile", "account issue", "account verification", "account recovery"],
            "Customer Complaint": ["complaint", "customer complaint", "dissatisfaction", "complaint escalation"],
            "General Query": ["general query", "question", "inquiry", "information request"],
            "Product Issue": ["product", "product issue", "product support", "product guidance"],
            "Service Issue": ["service", "service issue", "service support", "service outage"],
        }
        
        # Fetch skills for each category to improve scoring
        skills_by_category = {}
        for cat in available_categories:
            skills = db.session.execute(
                text("SELECT skill_name FROM skills WHERE category = :cat ORDER BY skill_name"),
                {"cat": cat}
            ).fetchall()
            skills_by_category[cat] = [s[0].lower() for s in skills]
        
        scores = {}
        for category in available_categories:
            score = 0
            
            # Score based on category name words
            cat_words = set(category.lower().replace("issue", "").replace("request", "").split())
            text_words = set(text_content.split())
            overlap = cat_words & text_words
            score += len(overlap) * 2
            
            # Score based on hints
            hints = category_hints.get(category, [])
            for hint in hints:
                if hint in text_content:
                    score += 3
            
            # Score based on skills
            for skill_name in skills_by_category.get(category, []):
                skill_words = set(skill_name.split())
                skill_overlap = skill_words & text_words
                if len(skill_overlap) >= 2:
                    score += 5
                elif len(skill_overlap) == 1:
                    score += 2
                
                # Check if skill name appears in text
                if skill_name in text_content:
                    score += 4
            
            # Specific disambiguation rules
            if "document" in text_content:
                if category == "Employee Documents":
                    score += 8
                elif category == "Account Issue":
                    score -= 3
            
            if "account" in text_content and "document" not in text_content:
                if category == "Account Issue":
                    score += 6
            
            if "employee" in text_content:
                if category in ["Employee Documents", "Employee Benefits", "Leave Request", "Payroll", "Attendance"]:
                    score += 3
            
            scores[category] = score
        
        best_category = max(scores, key=scores.get)
        best_score = scores[best_category]
        
        if best_score == 0:
            return {
                "success": True,
                "category": "General Query",
                "confidence": "low",
                "reasoning": "No strong category match found, defaulting to General Query",
            }
        
        confidence = "high" if best_score >= 10 else "medium" if best_score >= 5 else "low"
        
        return {
            "success": True,
            "category": best_category,
            "confidence": confidence,
            "reasoning": f"Best match: {best_category} (score: {best_score})",
        }
    
    def get_department_for_category_from_db(self, category: str) -> Dict[str, Any]:
        from flask import current_app
        from help_db import db
        from sqlalchemy import text
        
        with current_app.app_context():
            row = db.session.execute(
                text("""
                    SELECT d.department_id, d.department_name
                    FROM categories c
                    JOIN departments d ON c.department_id = d.department_id
                    WHERE c.category_name = :category
                    LIMIT 1
                """),
                {"category": category}
            ).fetchone()
            
            if row:
                return {
                    "success": True,
                    "department_id": row[0],
                    "department_name": row[1],
                }
            
            return {
                "success": False,
                "department_id": None,
                "department_name": None,
                "error": f"Category '{category}' not found in database",
            }
    
    def analyze_category_from_db_categories(self, ticket_subject: str, ticket_description: str) -> Dict[str, Any]:
        from flask import current_app
        from help_db import db
        from sqlalchemy import text
        
        with current_app.app_context():
            db_categories = db.session.execute(
                text("SELECT category_name FROM categories ORDER BY category_name")
            ).fetchall()
            available_categories = [r[0] for r in db_categories]
        
        if not available_categories:
            return {
                "success": False,
                "category": None,
                "reasoning": "No categories available in database",
                "error": "No categories found",
            }
        
        categories_str = ", ".join(available_categories)
        
        category_hints = {
            "Wi-Fi Issue": "WiFi, wireless, Wi-Fi, internet not working on laptop, wireless connection, wifi password, wifi not connecting",
            "Network Issue": "network, LAN, WAN, router, switch, DNS, DHCP, VPN, firewall, ethernet, cable, connectivity, network speed, slow internet",
            "Hardware Issue": "printer, mouse, keyboard, laptop, monitor, hardware, device, computer, desktop, RAM, hard disk, motherboard, power supply",
            "Software Issue": "software, application, app, browser, MS Office, email, outlook, gmail, installation, error, crash, bug",
            "System Access": "password reset, account locked, windows login, user account, domain login, access, login issue, system access",
            "Email Issue": "email, gmail, outlook, mail not working, email configuration, email recovery",
            "Login Issue": "login, cannot login, login problem, credential, authentication",
            "Password Reset": "password reset, forgot password, reset password, password change",
            "Printer Issue": "printer, print, printing, printer not working, printer jam",
            "Payment Issue": "payment, billing, invoice, transaction, refund, payment failed",
            "Billing": "billing, invoice, payment, charge, billing problem",
            "Invoice": "invoice, billing, payment, invoice issue",
            "Expense": "expense, reimbursement, cost, expense report",
            "Reimbursement": "reimbursement, expense refund, claim",
            "Salary": "salary, payroll, payslip, salary issue",
            "Attendance": "attendance, time tracking, check-in, check-out, attendance system",
            "Employee Benefits": "benefits, insurance, leave benefits, employee benefits",
            "Employee Documents": "documents, verification, records, HR documents, employee records",
            "Leave Request": "leave, vacation, holiday, leave balance, leave approval",
            "Payroll": "payroll, salary processing, payslip, payroll issue",
            "Recruitment": "recruitment, hiring, onboarding, interview, job posting",
            "Asset Request": "asset, laptop request, device request, asset allocation",
            "Facilities": "facilities, room booking, office facility, maintenance request",
            "General Administration": "administration, general admin, office support, admin task",
            "ID Card": "ID card, access card, identity card, ID card issue",
            "Office Maintenance": "maintenance, repair, office repair, facility repair",
            "Account Issue": "account, profile, account issue, account verification",
            "Customer Complaint": "complaint, customer complaint, dissatisfaction, complaint escalation",
            "General Query": "general query, question, inquiry, information request",
            "Product Issue": "product, product issue, product support, product guidance",
            "Service Issue": "service, service issue, service support, service outage",
        }
        
        hints_text = "\n".join([f"- {cat}: {hint}" for cat, hint in category_hints.items() if cat in available_categories])
        
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a help desk triage expert. Your job is to analyze tickets "
                    "and determine the most appropriate category from the provided list.\n\n"
                    f"Available categories: {categories_str}\n\n"
                    "CATEGORY HINTS:\n"
                    f"{hints_text}\n\n"
                    "RULES:\n"
                    "1. Analyze BOTH the title and description carefully\n"
                    "2. Choose the SINGLE best matching category from the available list only\n"
                    "3. Do NOT default to the same category for every ticket\n"
                    "4. Respond ONLY with a valid JSON object in this exact format:\n"
                    '{"category": "exact category name from the list", "reasoning": "one sentence explanation"}\n'
                    "5. Do NOT include markdown formatting or any other text\n"
                    "6. Be accurate and vary your choices based on the actual issue"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Analyze the category of this ticket:\n\n"
                    f"Subject: {ticket_subject.strip()}\n"
                    f"Description: {ticket_description.strip()}\n\n"
                    f"Available categories: {categories_str}\n\n"
                    f"JSON Response:"
                ),
            },
        ]
        
        result = self.chat(messages=messages, temperature=0.1, max_tokens=150)
        
        if not result["success"]:
            return {
                "success": False,
                "category": available_categories[0] if available_categories else None,
                "reasoning": f"AI analysis failed: {result['error']}",
                "error": result["error"],
            }
        
        try:
            category_data = json.loads(result["content"])
            if "category" not in category_data:
                raise ValueError("Missing 'category' field")
            
            category = category_data["category"]
            if category not in available_categories:
                raise ValueError(f"Invalid category: {category}")
            
            return {
                "success": True,
                "category": category,
                "reasoning": category_data.get("reasoning", ""),
                "model": result.get("model"),
            }
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Failed to parse category response: {result['content']}, error: {str(e)}")
            return {
                "success": False,
                "category": available_categories[0] if available_categories else None,
                "reasoning": f"AI returned invalid response, defaulting to first category",
                "error": f"Invalid AI response: {str(e)}",
            }
    
    def find_best_skill_for_category(self, category: str, ticket_issue: str) -> Dict[str, Any]:
        from flask import current_app
        from help_db import db
        from sqlalchemy import text
        
        with current_app.app_context():
            skills = db.session.execute(
                text("""
                    SELECT s.skill_id, s.skill_name
                    FROM skills s
                    WHERE s.category = :category
                    ORDER BY s.skill_name
                """),
                {"category": category}
            ).fetchall()
            
            if not skills:
                return {
                    "success": False,
                    "skill_id": None,
                    "skill_name": None,
                    "reasoning": f"No skills found for category '{category}'",
                }
            
            issue_lower = ticket_issue.lower().strip() if ticket_issue else ""
            best_skill_id = None
            best_skill_name = None
            best_score = 0
            
            for skill in skills:
                skill_id, skill_name = skill
                skill_lower = skill_name.lower().strip()
                score = 0
                
                # Exact match
                if issue_lower == skill_lower:
                    score += 50
                
                # Partial match
                elif issue_lower in skill_lower or skill_lower in issue_lower:
                    score += 30
                
                # Word overlap
                else:
                    skill_words = set(skill_lower.split())
                    issue_words = set(issue_lower.split())
                    overlap = skill_words & issue_words
                    if len(overlap) >= 2:
                        score += 20
                    elif len(overlap) == 1:
                        score += 10
                
                if score > best_score:
                    best_score = score
                    best_skill_id = skill_id
                    best_skill_name = skill_name
            
            if best_skill_id:
                return {
                    "success": True,
                    "skill_id": best_skill_id,
                    "skill_name": best_skill_name,
                    "score": best_score,
                    "reasoning": f"Best matching skill for {category}: {best_skill_name}",
                }
            
            return {
                "success": False,
                "skill_id": None,
                "skill_name": None,
                "reasoning": f"No matching skill found for category '{category}'",
            }
    
    @classmethod
    def _score_agent(cls, agent_id, first_name, last_name, open_tickets, ticket_issue, ticket_category, agent_categories, agent_skills, required_skill_id=None, llm_required_skill_ids=None):
        score = 0
        reasons = []
        matched_skill_id = None
        matched_by_llm = False
        issue_lower = ticket_issue.lower().strip() if ticket_issue else ""
        
        skill_map = {s[1].lower().strip(): s[0] for s in agent_skills} if agent_skills else {}
        skill_names = list(skill_map.keys())
        category_names = [c[0].lower().strip() for c in agent_categories] if agent_categories else []
        
        for skill_name in skill_names:
            if issue_lower == skill_name:
                score += 50
                matched_skill_id = skill_map.get(skill_name)
                reasons.append(f"Exact skill match: {skill_name}")
                break
        
        if score < 50:
            for skill_name in skill_names:
                skill_words = set(skill_name.lower().split())
                issue_words = set(issue_lower.split())
                overlap = skill_words & issue_words
                if len(overlap) >= 2:
                    score += 40
                    matched_skill_id = skill_map.get(skill_name)
                    reasons.append(f"Strong skill match: {skill_name}")
                    break
        
        if ticket_category:
            cat_lower = ticket_category.lower().strip()
            for c in category_names:
                if c == cat_lower:
                    score += 25
                    reasons.append("Category match")
                    break
        
        if not matched_skill_id:
            for skill_name in skill_names:
                if issue_lower and issue_lower in skill_name:
                    score += 20
                    matched_skill_id = skill_map.get(skill_name)
                    reasons.append(f"Issue in skill: {skill_name}")
                    break
        
        keyword_groups = [
            ["wifi", "wireless", "wi-fi"],
            ["network", "networking", "lan", "wan"],
            ["hardware", "device", "peripheral"],
            ["software", "application", "app"],
            ["login", "password", "account", "access"],
            ["payment", "billing", "invoice", "transaction"],
            ["hr", "employee", "staff", "payroll", "leave"],
            ["printer", "print"],
            ["email", "mail", "outlook", "gmail"],
            ["database", "sql", "db"],
        ]
        for group in keyword_groups:
            if any(kw in issue_lower for kw in group):
                if any(any(kw in skill_name for kw in group) for skill_name in skill_names):
                    score += 10
                    reasons.append("Keyword match")
                    break
        
        if llm_required_skill_ids:
            for skill_name, sid in skill_map.items():
                if sid in llm_required_skill_ids:
                    score += 100
                    matched_skill_id = sid
                    matched_by_llm = True
                    reasons.append(f"LLM Semantic Match: {skill_name}")
                    break

        if required_skill_id and not matched_by_llm:
            for skill_name in skill_names:
                if str(required_skill_id) == str(skill_map.get(skill_name)):
                    score += 15
                    matched_skill_id = required_skill_id
                    reasons.append(f"Required skill match: {skill_name}")
                    break
        
        return {
            "agent_id": agent_id,
            "name": f"{first_name} {last_name}",
            "score": score,
            "open_tickets": open_tickets,
            "reasons": reasons,
            "matched_skill_id": matched_skill_id,
            "matched_by_llm": matched_by_llm
        }
    
    @classmethod
    def analyze_required_skills(cls, title: str, description: str, available_skills: list) -> list:
        if not title and not description:
            return []
            
        instance = cls()
        if not instance.is_configured():
            return []
            
        # Provide minimal structure for tokens
        skills_context = str([{"id": s[0], "name": s[1]} for s in available_skills])
        
        prompt = f"""
        You are an intelligent IT Help Desk agent routing engine.
        A customer has submitted a ticket.
        
        Ticket Title: {title}
        Ticket Description: {description}
        
        We have the following exact skillset assignments in our database:
        {skills_context}
        
        Analyze the ticket's problem. STRICTLY output ONLY a raw JSON array containing the integer IDs of the skills that are directly relevant or critical to solving this ticket. 
        Do not output markdown format. Do not output anything else. If no skills match, output [].
        Example valid output:
        [1, 5, 12]
        """
        
        try:
            result = instance.chat([
                {"role": "system", "content": "You are a precise classifier. You output ONLY raw JSON integer arrays."},
                {"role": "user", "content": prompt}
            ])
            if result.get("success"):
                content = result.get("content", "[]").strip()
                if content.startswith("```json"):
                    content = content[7:]
                if content.startswith("```"):
                    content = content[3:]
                if content.endswith("```"):
                    content = content[:-3]
                
                import json
                parsed_ids = json.loads(content.strip())
                if isinstance(parsed_ids, list):
                    return [int(x) for x in parsed_ids]
        except Exception as e:
            logger.error(f"Error in analyze_required_skills LLM call: {str(e)}")
            
        return []

    @classmethod
    def find_best_agent(cls, department_name: str, category: str = None, issue_title: str = None, issue_description: str = None, allow_fallback: bool = True, required_skill_id=None) -> Dict[str, Any]:
        from flask import current_app
        from help_db import db
        from sqlalchemy import text
        
        with current_app.app_context():
            resolved_dept = None
            if department_name:
                rows = db.session.execute(
                    text("SELECT department_name FROM departments")
                ).fetchall()
                db_names = [r[0].strip() for r in rows if r[0]]
                target_lower = department_name.lower().strip()
                db_names_lower = [n.lower().strip() for n in db_names]
                
                for i, name in enumerate(db_names_lower):
                    if name == target_lower:
                        resolved_dept = db_names[i]
                        break
                
                if not resolved_dept:
                    for i, name in enumerate(db_names_lower):
                        if target_lower in name or name in target_lower:
                            resolved_dept = db_names[i]
                            break
                
                if not resolved_dept:
                    aliases = {
                        "software team": ["software", "software development"],
                        "networking": ["network", "network team", "it network"],
                        "hardware": ["hardware support", "hardware team"],
                        "technical": ["technical support", "it support", "it management"],
                        "hr": ["human resources", "hr department"],
                        "financial": ["finance", "finance team", "billing"],
                    }
                    target_aliases = aliases.get(target_lower, [])
                    for alias in target_aliases:
                        alias_lower = alias.lower().strip()
                        for i, name in enumerate(db_names_lower):
                            if alias_lower == name or alias_lower in name or name in alias_lower:
                                resolved_dept = db_names[i]
                                break
                        if resolved_dept:
                            break
            
            if not resolved_dept:
                return {
                    "success": False,
                    "agent_id": None,
                    "agent_name": None,
                    "reasoning": f"Department '{department_name}' not found",
                }
            
            dept_row = db.session.execute(
                text("SELECT department_id FROM departments WHERE TRIM(department_name) = :dept"),
                {"dept": resolved_dept}
            ).fetchone()
            
            if not dept_row:
                return {
                    "success": False,
                    "agent_id": None,
                    "agent_name": None,
                    "reasoning": f"Department '{department_name}' not found",
                }
            
            department_id = dept_row[0]
            agents = db.session.execute(
                text("""
                    SELECT u.user_id, u.first_name, u.last_name,
                           COUNT(t.ticket_id) as open_tickets
                    FROM users u
                    LEFT JOIN tickets t ON u.user_id = t.assigned_to
                        AND t.status_name IN ('Open', 'In Progress')
                    WHERE u.role_id = 3
                      AND u.status = 'Active'
                      AND u.department_id = :dept_id
                    GROUP BY u.user_id, u.first_name, u.last_name
                    ORDER BY open_tickets ASC
                """),
                {"dept_id": department_id}
            ).fetchall()
            
            if not agents:
                return {
                    "success": False,
                    "agent_id": None,
                    "agent_name": None,
                    "reasoning": f"No active agent found in {department_name}",
                }
            
            # Fetch all global skills for LLM evaluation
            all_skills = db.session.execute(text("SELECT skill_id, skill_name FROM skills")).fetchall()
            
            # Sub-request the LLM for highest semantic exactness
            llm_required_skill_ids = cls.analyze_required_skills(issue_title, issue_description, all_skills)
            
            scored_agents = []
            for agent in agents:
                agent_id = agent[0]
                first_name = agent[1]
                last_name = agent[2]
                open_tickets = agent[3]
                
                agent_categories = db.session.execute(
                    text("""
                        SELECT uc.category_name
                        FROM user_categories uc
                        WHERE uc.user_id = :agent_id
                    """),
                    {"agent_id": agent_id}
                ).fetchall()
                
                agent_skills = db.session.execute(
                    text("""
                        SELECT s.skill_id, s.skill_name
                        FROM skills s
                        JOIN agent_skills ag ON s.skill_id = ag.skill_id
                        WHERE ag.user_id = :agent_id
                        ORDER BY s.skill_name
                    """),
                    {"agent_id": agent_id}
                ).fetchall()
                
                scored = cls._score_agent(
                    agent_id, first_name, last_name, open_tickets,
                    issue_title, category, agent_categories, agent_skills,
                    required_skill_id=required_skill_id,
                    llm_required_skill_ids=llm_required_skill_ids
                )
                scored_agents.append(scored)
            
            scored_agents.sort(key=lambda x: (-x["score"], x["open_tickets"]))
            best = scored_agents[0]
            
            if best["score"] > 0:
                reason_parts = best["reasons"] + [f"Open tickets: {best['open_tickets']}"]
                reasoning = " | ".join(reason_parts)
                assignment_method = "AI Semantic Skill Match" if best.get("matched_by_llm") else "AI Categorical Match"
                
                return {
                    "success": True,
                    "agent_id": best["agent_id"],
                    "agent_name": best["name"],
                    "department_id": department_id,
                    "open_tickets": best["open_tickets"],
                    "match_score": best["score"],
                    "matched_skill_id": best.get("matched_skill_id"),
                    "assignment_method": assignment_method,
                    "reasoning": reasoning,
                }
            
            if not allow_fallback:
                return {
                    "success": False,
                    "agent_id": None,
                    "agent_name": None,
                    "reasoning": "No suitable Agent with the required skill is currently available.",
                    "department_id": department_id,
                    "match_score": 0,
                }
            
            reasoning = f"Fallback Department Match (open tickets: {best['open_tickets']})"
            assignment_method = "Fallback Department Match"
            
            return {
                "success": True,
                "agent_id": best["agent_id"],
                "agent_name": best["name"],
                "department_id": department_id,
                "open_tickets": best["open_tickets"],
                "match_score": 0,
                "matched_skill_id": None,
                "assignment_method": assignment_method,
                "reasoning": reasoning,
            }
    
    def summarize_ticket(self, ticket_subject: str, ticket_description: str) -> Dict[str, Any]:
        """
        Generate an AI summary for a help desk ticket.
        
        This method sends the ticket details to OpenRouter and asks the AI
        to provide a concise summary including the core issue, urgency level,
        and suggested department.
        
        Args:
            ticket_subject: The subject/title of the ticket.
                           Example: "Internet not working"
            ticket_description: The full description of the ticket.
                              Example: "Customer cannot connect to WiFi since morning."
        
        Returns:
            Dict with the following structure:
            On success:
            {
                "success": True,
                "summary": str,  # AI-generated summary (2-3 sentences)
                "model": str     # Model used for generation
            }
            
            On failure:
            {
                "success": False,
                "error": str,    # Error message
                "summary": ""    # Always empty on failure
            }
        """
        # Validate inputs
        if not ticket_subject or not ticket_subject.strip():
            return {
                "success": False,
                "error": "Ticket subject cannot be empty",
                "summary": "",
            }
        
        if not ticket_description or not ticket_description.strip():
            return {
                "success": False,
                "error": "Ticket description cannot be empty",
                "summary": "",
            }
        
        # Build the message list for the AI
        # System message sets the AI's role and instructions
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a help desk assistant specializing in ticket triage. "
                    "Your task is to summarize the ticket below in exactly 2-3 sentences. "
                    "Your summary must include: "
                    "(1) the core issue, "
                    "(2) the urgency level (Low/Medium/High/Critical), "
                    "(3) the most likely department to handle it "
                    "(Technical/Billing/Account/General). "
                    "Be concise and factual."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Please summarize this help desk ticket:\n\n"
                    f"Subject: {ticket_subject.strip()}\n"
                    f"Description: {ticket_description.strip()}"
                ),
            },
        ]
        
        # Call the core chat method with specific parameters for summarization
        # temperature=0.3 for more focused, deterministic output
        # max_tokens=300 to keep summary concise
        result = self.chat(messages=messages, temperature=0.3, max_tokens=300)
        
        # Check if the chat call was successful
        if result["success"]:
            return {
                "success": True,
                "summary": result["content"],
                "model": result.get("model"),
            }
        else:
            # Return the error from the chat call
            return {
                "success": False,
                "error": result["error"],
                "summary": "",
            }
    
    def analyze_priority(self, ticket_subject: str, ticket_description: str, category: str = None, issue_type: str = None) -> Dict[str, Any]:
        """
        Analyze a ticket and return the recommended priority level.
        
        This method sends the ticket details to OpenRouter and asks the AI
        to classify the urgency as Low, Medium, High, or Critical based on
        the impact and urgency of the issue.
        
        Args:
            ticket_subject: The subject/title of the ticket.
                           Example: "Internet not working"
            ticket_description: The full description of the ticket.
                               Example: "Customer cannot connect to WiFi since morning."
            category: Optional category context to help the AI understand the issue type.
            issue_type: Optional specific issue type for additional context.
        
        Returns:
            Dict with the following structure:
            On success:
            {
                "success": True,
                "priority": str,  # One of: Low, Medium, High, Critical
                "reasoning": str, # Brief explanation of the priority choice
                "model": str      # Model used for generation
            }
            
            On failure:
            {
                "success": False,
                "priority": "Medium",  # Safe fallback priority
                "reasoning": str,      # Error message or fallback reason
                "error": str           # Technical error message
            }
        """
        # Validate inputs
        if not ticket_subject or not ticket_description:
            return {
                "success": False,
                "priority": "Medium",
                "reasoning": "Missing ticket subject or description",
                "error": "Invalid input",
            }
        
        # Build the message list for the AI
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a senior help desk triage expert with deep technical knowledge. "
                    "Your job is to analyze BOTH the ticket title AND description to determine "
                    "the correct priority level based on issue severity and business impact.\n\n"
                    f"CATEGORY CONTEXT: {category if category else 'Not specified'}\n"
                    f"ISSUE TYPE: {issue_type if issue_type else 'Not specified'}\n"
                    "Use the category and issue type to better understand the context, but judge priority "
                    "based on the actual severity described in the title and description.\n\n"
                    "PRIORITY DEFINITIONS (read carefully):\n\n"
                    "CRITICAL - Complete system/office failure affecting everyone:\n"
                    "  - Entire office or all users cannot work\n"
                    "  - Server down, database corrupted, data loss, security breach\n"
                    "  - Production systems completely unavailable\n"
                    "  - Examples: 'Server down', 'Database corrupted', 'Entire office internet down', "
                    "'All users locked out', 'Security breach detected'\n\n"
                    "HIGH - Major service disruption affecting multiple users or business operations:\n"
                    "  - Internet completely down for user/team, email not receiving for team\n"
                    "  - Payment failures, software crashes, system overheating\n"
                    "  - VIP/client-facing issues, SLA breach risk\n"
                    "  - Examples: 'Internet completely down', 'Payment failed', 'Software crash', "
                    "'Email not receiving', 'System overheating', 'VPN not connecting for remote team'\n\n"
                    "MEDIUM - Standard operational issue with workaround available:\n"
                    "  - Single user connectivity issue, network cable disconnected\n"
                    "  - Non-critical application errors, minor configuration issues\n"
                    "  - Examples: 'Network cable disconnected', 'Email sync issue', 'Single user slow computer'\n\n"
                    "LOW - Minor issue, no time sensitivity, peripheral or cosmetic:\n"
                    "  - Peripheral device issues (mouse, keyboard, monitor)\n"
                    "  - Password reset requests, printer not printing\n"
                    "  - Enhancement requests, general questions\n"
                    "  - Examples: 'Mouse not working', 'Printer not printing', 'Password reset', "
                    "'Monitor flickering', 'Request for new keyboard'\n\n"
                    "ANALYSIS RULES:\n"
                    "1. Analyze BOTH title and description together - do not rely on title alone\n"
                    "2. Consider the SEVERITY of the issue, not just the device type\n"
                    "3. A 'server down' is Critical, but 'mouse not working' is Low\n"
                    "4. 'Internet completely down' is High, 'network cable disconnected' is Medium\n"
                    "5. 'Payment failed' is High, 'password reset' is Low\n"
                    "6. 'Software crash' is High, 'printer not printing' is Low\n"
                    "7. 'Database corrupted' is Critical, 'email not receiving' is Medium\n"
                    "8. If confidence is low or the issue is ambiguous, choose the SAFEST appropriate priority - do NOT default to Medium simply because the issue is vague\n"
                    "9. Do NOT assign Medium to every ticket - vary based on actual severity\n"
                    "10. If the description is vague, infer only what can reasonably be inferred and choose the safest appropriate priority (Low, Medium, High, or Critical) based on the actual severity\n\n"
                    "Respond ONLY with a valid JSON object in this exact format:\n"
                    '{"priority": "Low" or "Medium" or "High" or "Critical", '
                    '"reasoning": "one sentence explaining why this priority was chosen"}\n'
                    "Do NOT include markdown formatting, code blocks, or any other text."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Analyze the priority of this ticket:\n\n"
                    f"Category: {category if category else 'Not specified'}\n"
                    f"Issue Type: {issue_type if issue_type else 'Not specified'}\n"
                    f"Title: {ticket_subject.strip()}\n"
                    f"Description: {ticket_description.strip()}\n\n"
                    f"JSON Response:"
                ),
            },
        ]
        
        # Call the core chat method
        # temperature=0.1 for very deterministic, consistent classification
        # max_tokens=150 since we only need a small JSON response
        result = self.chat(messages=messages, temperature=0.1, max_tokens=150)
        
        # Check if the chat call was successful
        if not result["success"]:
            # Fallback to deterministic classification
            fallback = self.classify_priority(ticket_subject, ticket_description, category=category)
            return {
                "success": False,
                "priority": fallback.get("priority", "Medium"),
                "reasoning": f"AI analysis failed: {result['error']}. Used fallback: {fallback.get('reasoning', '')}",
                "error": result["error"],
            }
        
        # Try to parse the JSON response from the AI
        try:
            import json
            content = result["content"].strip()
            
            # Handle cases where AI wraps JSON in markdown
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.strip()
            
            priority_data = json.loads(content)
            
            # Validate the parsed JSON has required fields
            if "priority" not in priority_data:
                raise ValueError("Missing 'priority' field in AI response")
            
            priority = priority_data["priority"]
            
            # Validate priority value is one of the allowed values
            valid_priorities = {"Low", "Medium", "High", "Critical"}
            if priority not in valid_priorities:
                raise ValueError(f"Invalid priority value: {priority}")
            
            # Return validated priority data
            return {
                "success": True,
                "priority": priority,
                "reasoning": priority_data.get("reasoning", ""),
                "model": result.get("model"),
            }
            
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Failed to parse priority response: {result['content']}, error: {str(e)}")
            # Fallback to deterministic classification
            fallback = self.classify_priority(ticket_subject, ticket_description, category=category)
            return {
                "success": False,
                "priority": fallback.get("priority", "Medium"),
                "reasoning": f"AI returned invalid response, used fallback: {fallback.get('reasoning', '')}",
                "error": f"Invalid AI response: {str(e)}",
            }
    
    def auto_assign_department(self, ticket_subject: str, ticket_description: str) -> Dict[str, Any]:
        """
        Automatically determine the correct department for a ticket.
        
        Args:
            ticket_subject: The ticket title
            ticket_description: The ticket description
            
        Returns:
            Dict with department suggestion:
            {
                "success": True,
                "department": str,
                "reasoning": str,
                "confidence": str
            }
        """
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a help desk routing expert. Your job is to determine the correct department "
                    "for a ticket based on its content.\n\n"
                    "Department mapping (respond ONLY with the exact department name listed):\n"
                    "- Hardware issues (printer, mouse, keyboard, laptop, monitor, device, hardware) → Hardware\n"
                    "- Network issues (internet, wifi, network, LAN, VPN, router, server, DNS, connection, slow internet) → Networking\n"
                    "- Software issues (email, gmail, outlook, application, software, login, browser, MS Office, software installation) → Software Team\n"
                    "- HR issues (leave, salary, employee, payroll, attendance, HR policy, employee ID) → HR\n"
                    "- IT support issues (password reset, account locked, windows login, user account, domain login, access) → IT management\n"
                    "- Financial issues (billing, invoice, payment, financial) → Financial\n"
                    "- General technical issues → Technical\n\n"
                    "Respond ONLY with JSON in this exact format:\n"
                    '{"department": "exact department name from the list above", "reasoning": "one sentence explanation"}\n'
                    "Do NOT include markdown or any other text."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Route this ticket:\n\n"
                    f"Title: {ticket_subject.strip()}\n"
                    f"Description: {ticket_description.strip()}\n\n"
                    f"JSON Response:"
                ),
            },
        ]
        
        result = self.chat(messages=messages, temperature=0.1, max_tokens=150)
        
        if not result["success"]:
            return {
                "success": False,
                "department": "Technical",
                "reasoning": f"AI routing failed: {result['error']}",
                "error": result["error"],
            }
        
        try:
            import json
            dept_data = json.loads(result["content"])
            
            department = dept_data.get("department", "Technical")
            reasoning = dept_data.get("reasoning", "Auto-assigned by AI")
            
            return {
                "success": True,
                "department": department,
                "reasoning": reasoning,
                "confidence": "high",
                "model": result.get("model"),
            }
            
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Failed to parse department response: {result['content']}, error: {str(e)}")
            return {
                "success": False,
                "department": "Technical",
                "reasoning": "AI returned invalid response, defaulting to Technical",
                "error": f"Invalid AI response: {str(e)}",
            }

    def analyze_category(self, ticket_subject: str, ticket_description: str, available_categories: List[str]) -> Dict[str, Any]:
        categories_str = ", ".join(available_categories) if available_categories else "General, Technical, Billing, Account"
        
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a help desk triage expert. Your job is to analyze tickets "
                    "and determine the most appropriate category from the provided list.\n\n"
                    f"Available categories: {categories_str}\n\n"
                    "CATEGORY DEFINITIONS:\n"
                    "- Hardware: Physical devices including printer, mouse, keyboard, laptop, monitor, computer, hardware failure, device issues\n"
                    "- Network: Internet connectivity, WiFi, LAN, VPN, router, server connectivity, DNS, slow internet, network cable, connection issues\n"
                    "- Software: Email (Gmail, Outlook), applications, MS Office, browser issues, software installation, login problems, application errors, software bugs\n"
                    "- HR: Payroll, leave management, attendance, salary, employee ID, HR policies, employee records, leave balance\n"
                    "- Technical: Password reset, account locked, Windows login, user account issues, domain login, access problems, general technical support\n"
                    "- Financial: Billing, invoices, payments, financial queries, refunds, charges\n\n"
                    "RULES:\n"
                    "1. Analyze BOTH the title and description carefully\n"
                    "2. Choose the SINGLE best matching category from the available list only\n"
                    "3. Do NOT default to the same category for every ticket\n"
                    "4. Respond ONLY with a valid JSON object in this exact format:\n"
                    '{"category": "exact category name from the list", "reasoning": "one sentence explanation"}\n'
                    "5. Do NOT include markdown formatting or any other text\n"
                    "6. Be accurate and vary your choices based on the actual issue"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Analyze the category of this ticket:\n\n"
                    f"Subject: {ticket_subject.strip()}\n"
                    f"Description: {ticket_description.strip()}\n\n"
                    f"Available categories: {categories_str}\n\n"
                    f"JSON Response:"
                ),
            },
        ]
        
        result = self.chat(messages=messages, temperature=0.1, max_tokens=150)

        if not result["success"]:
            return {
                "success": False,
                "category": available_categories[0] if available_categories else "General",
                "reasoning": f"AI analysis failed: {result['error']}",
                "error": result["error"],
            }

        try:
            import json
            category_data = json.loads(result["content"])

            if "category" not in category_data:
                raise ValueError("Missing 'category' field in AI response")

            category = category_data["category"]

            if category not in available_categories:
                raise ValueError(f"Invalid category value: {category}")

            return {
                "success": True,
                "category": category,
                "reasoning": category_data.get("reasoning", ""),
                "model": result.get("model"),
            }

        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Failed to parse category response: {result['content']}, error: {str(e)}")
            return {
                "success": False,
                "category": available_categories[0] if available_categories else "General",
                "reasoning": f"AI returned invalid response, defaulting to first category",
                "error": f"Invalid AI response: {str(e)}",
            }

    def suggest_response(
        self,
        ticket_subject: str,
        ticket_description: str,
        customer_name: str = "Customer",
    ) -> Dict[str, Any]:
        """
        Generate a professional response suggestion with troubleshooting steps for a help desk ticket.
        
        This method sends the ticket details to OpenRouter and asks the AI
        to draft a polite, professional response with actionable troubleshooting steps.
        
        Args:
            ticket_subject: The subject/title of the ticket.
                           Example: "Internet not working"
            ticket_description: The full description of the ticket.
                              Example: "Customer cannot connect to WiFi since morning."
            customer_name: The customer's name for personalization.
                          Default: "Customer"
        
        Returns:
            Dict with the following structure:
            On success:
            {
                "success": True,
                "suggestion": str,      # AI-generated professional response
                "troubleshooting": str, # Step-by-step troubleshooting guide
                "model": str            # Model used for generation
            }
            
            On failure:
            {
                "success": False,
                "error": str,           # Error message
                "suggestion": "",       # Always empty on failure
                "troubleshooting": ""   # Always empty on failure
            }
        """
        # Validate inputs
        if not ticket_subject or not ticket_subject.strip():
            return {
                "success": False,
                "error": "Ticket subject cannot be empty",
                "suggestion": "",
                "troubleshooting": "",
            }
        
        if not ticket_description or not ticket_description.strip():
            return {
                "success": False,
                "error": "Ticket description cannot be empty",
                "suggestion": "",
                "troubleshooting": "",
            }
        
        # Build the message list for the AI
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a professional help desk agent with excellent technical skills. "
                    "Your task is to write a polite, empathetic, and helpful response to a customer's ticket "
                    "with clear troubleshooting steps.\n\n"
                    "Response Structure:\n"
                    "1. Acknowledge their issue and apologize for the inconvenience\n"
                    "2. Provide 2-3 clear, step-by-step troubleshooting steps they can try\n"
                    "3. Offer further assistance if needed\n"
                    "4. Thank them for contacting support\n"
                    "5. Keep the tone professional but warm\n"
                    "6. Keep the response concise (under 200 words)\n\n"
                    "Format your response EXACTLY as follows:\n"
                    "REPLY:\n"
                    "[Your professional response here]\n\n"
                    "TROUBLESHOOTING:\n"
                    "1. [Step 1]\n"
                    "2. [Step 2]\n"
                    "3. [Step 3]"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Write a professional response with troubleshooting steps for this customer ticket:\n\n"
                    f"Customer Name: {customer_name.strip()}\n"
                    f"Subject: {ticket_subject.strip()}\n"
                    f"Issue: {ticket_description.strip()}\n\n"
                    f"Response:"
                ),
            },
        ]
        
        # Call the core chat method
        # temperature=0.5 for balanced creativity and professionalism
        # max_tokens=800 to allow complete response with troubleshooting steps
        result = self.chat(messages=messages, temperature=0.5, max_tokens=800)
        
        # Check if the chat call was successful
        if result["success"]:
            content = result["content"]
            
            # Parse the response to extract REPLY and TROUBLESHOOTING sections
            suggestion = ""
            troubleshooting = ""
            
            try:
                # Split by REPLY: and TROUBLESHOOTING: markers
                reply_match = content.split("REPLY:")
                if len(reply_match) >= 2:
                    suggestion = reply_match[1].split("TROUBLESHOOTING:")[0].strip()
                
                troubleshoot_match = content.split("TROUBLESHOOTING:")
                if len(troubleshoot_match) >= 2:
                    troubleshooting = troubleshoot_match[1].strip()
                
                # If parsing failed, use the entire content as suggestion
                if not suggestion:
                    suggestion = content.strip()
                    
            except Exception:
                # If parsing fails, use the entire content as suggestion
                suggestion = content.strip()
            
            return {
                "success": True,
                "suggestion": suggestion,
                "troubleshooting": troubleshooting,
                "model": result.get("model"),
            }
        else:
            # Return the error from the chat call
            return {
                "success": False,
                "error": result["error"],
                "suggestion": "",
                "troubleshooting": "",
            }
    
    def analyze_sentiment(self, text: str) -> Dict[str, Any]:
        """
        Analyze the sentiment of a text (positive, negative, or neutral).
        
        This method sends text to OpenRouter and asks the AI to classify
        the sentiment with a confidence level and reasoning.
        
        Args:
            text: The text to analyze.
                 Example: "I'm very frustrated with the service!"
        
        Returns:
            Dict with the following structure:
            On success:
            {
                "success": True,
                "sentiment": str,      # "positive", "negative", or "neutral"
                "confidence": str,     # "high", "medium", or "low"
                "reasoning": str       # Brief explanation of the classification
            }
            
            On failure:
            {
                "success": False,
                "sentiment": "unknown",
                "confidence": "low",
                "reasoning": str,  # Error message or parse failure reason
                "error": str       # Technical error message
            }
        """
        # Validate input
        if not text or not text.strip():
            return {
                "success": False,
                "sentiment": "unknown",
                "confidence": "low",
                "reasoning": "Text cannot be empty",
                "error": "Empty text provided",
            }
        
        # Build the message list for the AI
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a sentiment analysis expert. "
                    "Analyze the sentiment of the provided text. "
                    "Respond ONLY with a valid JSON object in this exact format:\n"
                    '{"sentiment": "positive" or "negative" or "neutral", '
                    '"confidence": "high" or "medium" or "low", '
                    '"reasoning": "one sentence explanation"}\n'
                    "Do not include any other text or markdown formatting."
                ),
            },
            {
                "role": "user",
                "content": f"Analyze the sentiment of this text:\n\n{text.strip()}\n\nJSON Response:",
            },
        ]
        
        # Call the core chat method
        # temperature=0.1 for very deterministic, consistent classification
        # max_tokens=200 since we only need a small JSON response
        result = self.chat(messages=messages, temperature=0.1, max_tokens=200)
        
        # Check if the chat call was successful
        if not result["success"]:
            return {
                "success": False,
                "sentiment": "unknown",
                "confidence": "low",
                "reasoning": f"AI Error: {result['error']}",
                "error": result["error"],
            }
        
        # Try to parse the JSON response from the AI
        try:
            # The AI should return a JSON string like:
            # {"sentiment": "negative", "confidence": "high", "reasoning": "..."}
            sentiment_data = json.loads(result["content"])
            
            # Validate the parsed JSON has required fields
            required_fields = {"sentiment", "confidence", "reasoning"}
            if not required_fields.issubset(sentiment_data.keys()):
                raise AIResponseError(
                    f"Missing required fields in sentiment response. "
                    f"Got: {list(sentiment_data.keys())}"
                )
            
            # Validate sentiment value
            valid_sentiments = {"positive", "negative", "neutral"}
            if sentiment_data["sentiment"] not in valid_sentiments:
                raise AIResponseError(
                    f"Invalid sentiment value: {sentiment_data['sentiment']}"
                )
            
            # Return validated sentiment data
            return {
                "success": True,
                "sentiment": sentiment_data["sentiment"],
                "confidence": sentiment_data["confidence"],
                "reasoning": sentiment_data["reasoning"],
            }
            
        except json.JSONDecodeError as e:
            # AI returned invalid JSON
            logger.error(f"Failed to parse sentiment JSON: {result['content']}")
            return {
                "success": False,
                "sentiment": "unknown",
                "confidence": "low",
                "reasoning": f"Failed to parse AI response as JSON: {str(e)}",
                "error": "Invalid JSON response from AI",
            }
        
        except AIResponseError as e:
            # JSON was valid but missing required fields
            logger.error(f"Invalid sentiment response structure: {str(e)}")
            return {
                "success": False,
                "sentiment": "unknown",
                "confidence": "low",
                "reasoning": str(e),
                "error": "Invalid response structure from AI",
            }
    
    def validate_ticket(
        self,
        ticket_subject: str,
        ticket_description: str,
        selected_category: str,
        available_categories: List[str],
    ) -> Dict[str, Any]:
        """
        Validate a ticket category before creation.
        
        This method analyzes the ticket and determines if the selected category is correct.
        It returns a strict validation result - if the category is wrong, it MUST be corrected.
        
        Args:
            ticket_subject: The ticket title
            ticket_description: The ticket description
            selected_category: Category chosen by the user
            available_categories: List of valid categories
            
        Returns:
            Dict with validation result:
            {
                "success": True,
                "is_valid": bool,
                "suggested_category": str or None,
                "message": str,
                "confidence": str
            }
        """
        categories_str = ", ".join(available_categories) if available_categories else "General, Technical, Billing, Account"
        
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a help desk triage expert. Your job is to validate ticket categories.\n\n"
                    f"Available categories: {categories_str}\n\n"
                    "Rules:\n"
                    "1. Analyze the ticket title and description carefully\n"
                    "2. If the selected category matches the actual issue, return:\n"
                    '{"is_valid": true, "message": "Category is correct."}\n'
                    "3. If the selected category is WRONG, return:\n"
                    '{"is_valid": false, "suggested_category": "correct category from list", "message": "The selected category does not match the issue. Suggested Category: [correct category]"}\n'
                    "4. Respond ONLY with valid JSON, no markdown, no extra text"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Validate this ticket category:\n\n"
                    f"Title: {ticket_subject.strip()}\n"
                    f"Description: {ticket_description.strip()}\n"
                    f"Selected Category: {selected_category}\n\n"
                    f"JSON Response:"
                ),
            },
        ]
        
        result = self.chat(messages=messages, temperature=0.1, max_tokens=150)
        
        if not result["success"]:
            return {
                "success": False,
                "is_valid": False,
                "message": f"Validation failed: {result['error']}",
                "error": result["error"],
            }
        
        try:
            import json
            validation_data = json.loads(result["content"])
            
            is_valid = validation_data.get("is_valid", False)
            suggested_category = validation_data.get("suggested_category")
            
            return {
                "success": True,
                "is_valid": is_valid,
                "suggested_category": suggested_category,
                "message": validation_data.get("message", "Category validation complete."),
                "confidence": "high" if is_valid else "medium",
                "model": result.get("model"),
            }
            
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Failed to parse validation response: {result['content']}, error: {str(e)}")
            return {
                "success": False,
                "is_valid": False,
                "message": "Validation failed. Please try again.",
                "error": f"Invalid AI response: {str(e)}",
            }
    
    def chat_with_ai(
        self,
        user_message: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """
        General-purpose AI chat for the help desk assistant.
        
        This method maintains conversation history and provides context-aware
        responses. It's designed for interactive chat sessions.
        
        Args:
            user_message: The user's current message.
                         Example: "How do I handle an angry customer?"
            conversation_history: Optional list of previous messages for context.
                                Each message should have 'role' and 'content' keys.
                                Example: [
                                    {"role": "user", "content": "What is SLA?"},
                                    {"role": "assistant", "content": "SLA stands for..."}
                                ]
        
        Returns:
            Dict with the following structure:
            On success:
            {
                "success": True,
                "response": str,  # AI-generated response
                "model": str      # Model used for generation
            }
            
            On failure:
            {
                "success": False,
                "response": str,  # Error message (for display to user)
                "error": str      # Technical error message (for logging)
            }
        """
        # Validate input
        if not user_message or not user_message.strip():
            return {
                "success": False,
                "response": "Please enter a message.",
                "error": "Empty user message",
            }
        
        # Initialize conversation history if not provided
        if conversation_history is None:
            conversation_history = []
        
        # Build the complete message list
        # Start with a system message that defines the AI's role and capabilities
        messages = [
            {
                "role": "system",
                "content": (
                    "You are an AI assistant for a Help Desk and Ticket Management System. "
                    "You help agents and admins with:\n"
                    "- Answering questions about tickets, users, and policies\n"
                    "- Suggesting responses to customer issues\n"
                    "- Analyzing ticket patterns and trends\n"
                    "- Providing technical troubleshooting guidance\n"
                    "- Explaining how to use the help desk system\n\n"
                    "Guidelines:\n"
                    "- Be concise, professional, and helpful\n"
                    "- If you don't know something, say so honestly\n"
                    "- Provide actionable advice when possible\n"
                    "- Keep responses under 200 words unless detail is requested"
                ),
            },
        ]
        
        # Add conversation history to maintain context
        # This allows the AI to remember previous messages in the conversation
        messages.extend(conversation_history)
        
        # Add the current user message at the end
        messages.append({"role": "user", "content": user_message.strip()})
        
        # Call the core chat method
        # temperature=0.7 for natural, conversational responses
        # max_tokens=1024 to allow detailed responses
        result = self.chat(messages=messages, temperature=0.7, max_tokens=1024)
        
        # Check if the chat call was successful
        if result["success"]:
            return {
                "success": True,
                "response": result["content"],
                "model": result.get("model"),
            }
        else:
            # Return user-friendly error without exposing internal details
            return {
                "success": False,
                "response": "AI service is temporarily unavailable. Please try again later.",
                "error": result["error"],
            }


# ---------------------------------------------------------------------------
# Global instance - created once per application context
# ---------------------------------------------------------------------------
# This instance is imported by routes and used throughout the application.
# It is safe to import this instance in multiple files because the actual
# OpenAI client is created lazily on first use.
ai_service = AIService()
