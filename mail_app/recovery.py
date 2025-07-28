"""
Mail App Error Recovery Mechanisms
"""
import logging
import time
from typing import Callable, Any, Optional, Dict
from functools import wraps
from django.core.cache import cache
from django.conf import settings

from .error_handlers import MailAppError, ErrorType, ErrorSeverity
from .logging_config import get_mail_logger

logger = get_mail_logger('mail_app.recovery')


class RetryConfig:
    """Configuration for retry mechanisms"""
    
    def __init__(
        self,
        max_attempts: int = 3,
        delay: float = 1.0,
        backoff_factor: float = 2.0,
        max_delay: float = 60.0,
        retry_on_exceptions: tuple = None
    ):
        self.max_attempts = max_attempts
        self.delay = delay
        self.backoff_factor = backoff_factor
        self.max_delay = max_delay
        self.retry_on_exceptions = retry_on_exceptions or (Exception,)


def retry_on_failure(config: RetryConfig = None):
    """Decorator for automatic retry with exponential backoff"""
    
    if config is None:
        config = RetryConfig()
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            
            for attempt in range(config.max_attempts):
                try:
                    result = func(*args, **kwargs)
                    
                    # Log successful retry
                    if attempt > 0:
                        logger.info(f"Function {func.__name__} succeeded on attempt {attempt + 1}")
                    
                    return result
                    
                except config.retry_on_exceptions as e:
                    last_exception = e
                    
                    # Don't retry on last attempt
                    if attempt == config.max_attempts - 1:
                        break
                    
                    # Calculate delay with exponential backoff
                    delay = min(
                        config.delay * (config.backoff_factor ** attempt),
                        config.max_delay
                    )
                    
                    logger.warning(
                        f"Function {func.__name__} failed on attempt {attempt + 1}, "
                        f"retrying in {delay}s: {str(e)}"
                    )
                    
                    time.sleep(delay)
            
            # All attempts failed
            logger.error(f"Function {func.__name__} failed after {config.max_attempts} attempts")
            raise last_exception
        
        return wrapper
    return decorator


class CircuitBreaker:
    """Circuit breaker pattern implementation"""
    
    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: type = Exception
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        
        # State management
        self.failure_count = 0
        self.last_failure_time = None
        self.state = 'CLOSED'  # CLOSED, OPEN, HALF_OPEN
        
        # Cache keys for distributed state management
        self.cache_key_failures = f"circuit_breaker_{name}_failures"
        self.cache_key_state = f"circuit_breaker_{name}_state"
        self.cache_key_last_failure = f"circuit_breaker_{name}_last_failure"
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection"""
        
        # Load state from cache
        self._load_state()
        
        if self.state == 'OPEN':
            if self._should_attempt_reset():
                self.state = 'HALF_OPEN'
                logger.info(f"Circuit breaker {self.name} entering HALF_OPEN state")
            else:
                raise MailAppError(
                    f"Circuit breaker {self.name} is OPEN",
                    error_type=ErrorType.EXTERNAL_API_ERROR,
                    severity=ErrorSeverity.HIGH,
                    user_message="Der Dienst ist momentan nicht verfügbar. Bitte versuchen Sie es später erneut."
                )
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
            
        except self.expected_exception as e:
            self._on_failure()
            raise e
    
    def _load_state(self):
        """Load circuit breaker state from cache"""
        self.failure_count = cache.get(self.cache_key_failures, 0)
        self.state = cache.get(self.cache_key_state, 'CLOSED')
        self.last_failure_time = cache.get(self.cache_key_last_failure)
    
    def _save_state(self):
        """Save circuit breaker state to cache"""
        cache.set(self.cache_key_failures, self.failure_count, 3600)
        cache.set(self.cache_key_state, self.state, 3600)
        cache.set(self.cache_key_last_failure, self.last_failure_time, 3600)
    
    def _on_success(self):
        """Handle successful execution"""
        if self.state == 'HALF_OPEN':
            logger.info(f"Circuit breaker {self.name} resetting to CLOSED state")
            
        self.failure_count = 0
        self.state = 'CLOSED'
        self.last_failure_time = None
        self._save_state()
    
    def _on_failure(self):
        """Handle failed execution"""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = 'OPEN'
            logger.warning(
                f"Circuit breaker {self.name} opening due to {self.failure_count} failures"
            )
        
        self._save_state()
    
    def _should_attempt_reset(self) -> bool:
        """Check if circuit breaker should attempt to reset"""
        if self.last_failure_time is None:
            return True
        
        return time.time() - self.last_failure_time >= self.recovery_timeout


def circuit_breaker(
    name: str = None,
    failure_threshold: int = 5,
    recovery_timeout: int = 60,
    expected_exception: type = Exception
):
    """Decorator for circuit breaker pattern"""
    
    def decorator(func: Callable) -> Callable:
        breaker_name = name or f"{func.__module__}.{func.__name__}"
        breaker = CircuitBreaker(
            name=breaker_name,
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
            expected_exception=expected_exception
        )
        
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            return breaker.call(func, *args, **kwargs)
        
        return wrapper
    return decorator


class FallbackHandler:
    """Handler for providing fallback functionality"""
    
    def __init__(self, fallback_func: Callable = None):
        self.fallback_func = fallback_func
    
    def execute_with_fallback(
        self,
        primary_func: Callable,
        fallback_func: Callable = None,
        *args,
        **kwargs
    ) -> Any:
        """Execute primary function with fallback on failure"""
        
        fallback = fallback_func or self.fallback_func
        
        try:
            return primary_func(*args, **kwargs)
        except Exception as e:
            logger.warning(f"Primary function {primary_func.__name__} failed, using fallback: {str(e)}")
            
            if fallback:
                try:
                    return fallback(*args, **kwargs)
                except Exception as fallback_error:
                    logger.error(f"Fallback function also failed: {str(fallback_error)}")
                    raise e  # Raise original exception
            else:
                raise e


def with_fallback(fallback_func: Callable):
    """Decorator for adding fallback functionality"""
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            handler = FallbackHandler(fallback_func)
            return handler.execute_with_fallback(func, *args, **kwargs)
        
        return wrapper
    return decorator


class GracefulDegradation:
    """Handle graceful degradation of functionality"""
    
    def __init__(self, features: Dict[str, bool] = None):
        self.features = features or {}
        self.cache_key = "mail_app_feature_flags"
        self._load_features()
    
    def _load_features(self):
        """Load feature flags from cache/database"""
        cached_features = cache.get(self.cache_key, {})
        self.features.update(cached_features)
    
    def _save_features(self):
        """Save feature flags to cache"""
        cache.set(self.cache_key, self.features, 3600)
    
    def is_feature_enabled(self, feature_name: str) -> bool:
        """Check if a feature is enabled"""
        return self.features.get(feature_name, True)
    
    def disable_feature(self, feature_name: str, reason: str = None):
        """Disable a feature"""
        self.features[feature_name] = False
        self._save_features()
        
        logger.warning(f"Feature {feature_name} disabled" + (f": {reason}" if reason else ""))
    
    def enable_feature(self, feature_name: str):
        """Enable a feature"""
        self.features[feature_name] = True
        self._save_features()
        
        logger.info(f"Feature {feature_name} enabled")
    
    def with_degradation(self, feature_name: str, fallback_result: Any = None):
        """Context manager for graceful degradation"""
        return FeatureDegradationContext(self, feature_name, fallback_result)


class FeatureDegradationContext:
    """Context manager for feature degradation"""
    
    def __init__(self, degradation: GracefulDegradation, feature_name: str, fallback_result: Any):
        self.degradation = degradation
        self.feature_name = feature_name
        self.fallback_result = fallback_result
    
    def __enter__(self):
        if not self.degradation.is_feature_enabled(self.feature_name):
            raise FeatureDisabledException(self.feature_name, self.fallback_result)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type and exc_type != FeatureDisabledException:
            # Feature failed, disable it temporarily
            self.degradation.disable_feature(
                self.feature_name,
                f"Feature failed with {exc_type.__name__}: {str(exc_val)}"
            )


class FeatureDisabledException(Exception):
    """Exception raised when a feature is disabled"""
    
    def __init__(self, feature_name: str, fallback_result: Any = None):
        self.feature_name = feature_name
        self.fallback_result = fallback_result
        super().__init__(f"Feature {feature_name} is disabled")


# Global instances
degradation_manager = GracefulDegradation({
    'email_sync': True,
    'email_send': True,
    'attachment_download': True,
    'search': True,
    'auto_refresh': True
})


# Convenience decorators with common configurations
def retry_on_api_error(max_attempts: int = 3):
    """Retry decorator specifically for API errors"""
    return retry_on_failure(RetryConfig(
        max_attempts=max_attempts,
        delay=2.0,
        backoff_factor=2.0,
        retry_on_exceptions=(
            ConnectionError,
            TimeoutError,
            MailAppError
        )
    ))

def retry_on_database_error(max_attempts: int = 2):
    """Retry decorator specifically for database errors"""
    from django.db import DatabaseError, IntegrityError
    
    return retry_on_failure(RetryConfig(
        max_attempts=max_attempts,
        delay=1.0,
        backoff_factor=1.5,
        retry_on_exceptions=(DatabaseError,)
    ))


# Example usage functions
def create_resilient_api_call(func: Callable, circuit_breaker_name: str = None) -> Callable:
    """Create a resilient API call with retry, circuit breaker, and fallback"""
    
    @retry_on_api_error(max_attempts=3)
    @circuit_breaker(
        name=circuit_breaker_name or func.__name__,
        failure_threshold=5,
        recovery_timeout=60
    )
    @wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    
    return wrapper