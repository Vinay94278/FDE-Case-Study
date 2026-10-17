"""A small registry that maps a config name to a builder function.

This is what makes components pluggable. To add a new LLM provider, document
source or log store:
    1. Write the class.
    2. Register a builder with @SOME_REGISTRY.register("my-name").
    3. Set the matching setting (for example LLM_PROVIDER=my-name).
No other code changes are needed.
"""
import logging
from typing import Any, Callable, Dict, List

from app.core.exceptions import ConfigurationException

logger = logging.getLogger(__name__)


class ComponentRegistry:
    def __init__(self, component_kind: str):
        self.component_kind = component_kind
        self._builders_by_name: Dict[str, Callable[..., Any]] = {}

    def register(self, component_name: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Decorator that registers a builder function under a name."""
        normalized_name = component_name.strip().lower()

        def decorator(builder_function: Callable[..., Any]) -> Callable[..., Any]:
            if normalized_name in self._builders_by_name:
                raise ConfigurationException(
                    technical_message="Duplicate " + self.component_kind + " name: " + normalized_name
                )
            self._builders_by_name[normalized_name] = builder_function
            return builder_function

        return decorator

    def get_available_names(self) -> List[str]:
        return sorted(self._builders_by_name.keys())

    def create(self, component_name: str, *builder_arguments: Any) -> Any:
        """Build the component registered under component_name."""
        normalized_name = component_name.strip().lower()
        if normalized_name not in self._builders_by_name:
            available_names = ", ".join(self.get_available_names())
            raise ConfigurationException(
                message="The service is not configured correctly.",
                technical_message=(
                    "Unknown " + self.component_kind + " '" + component_name + "'. "
                    + "Available: " + available_names
                ),
            )
        builder_function = self._builders_by_name[normalized_name]
        logger.info("Creating %s '%s'", self.component_kind, normalized_name)
        return builder_function(*builder_arguments)
