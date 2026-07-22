from typing import Dict, Any, Type
from .core.controller import Controller
from .core.scheduler import Scheduler
from .core.judge import Judge
from .core.guard import Guard
from .core.librarian import Librarian
from .services.specialists import SpecialistService
from .config import settings

class Container:
    """Dependency Injection Container for Enxame Services."""
    
    def __init__(self):
        self._services: Dict[str, Any] = {}
        self._initialized = False

    def initialize(self):
        """Initialize all services with their dependencies."""
        if self._initialized:
            return
        
        # Initialize leaf services first
        self._services["guard"] = Guard()
        self._services["librarian"] = Librarian()
        self._services["specialists"] = SpecialistService()
        self._services["scheduler"] = Scheduler()
        self._services["judge"] = Judge()
        
        # Initialize controller with dependencies
        self._services["controller"] = Controller(
            guard=self._services["guard"],
            librarian=self._services["librarian"],
            scheduler=self._services["scheduler"],
            specialists=self._services["specialists"],
            judge=self._services["judge"]
        )
        
        self._initialized = True

    def get(self, name: str) -> Any:
        """Get a service by name."""
        if not self._initialized:
            self.initialize()
        return self._services.get(name)

# Global container instance
_container = Container()

def get_container() -> Container:
    """Get the global DI container."""
    return _container