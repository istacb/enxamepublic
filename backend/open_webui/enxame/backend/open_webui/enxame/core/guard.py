from ..models.schemas import ValidationResult, ThreatLevel
from ..logging_config import get_logger
import re
from typing import List

logger = get_logger("guard")

class Validator:
    """Base class for validators."""
    def validate(self, text: str) -> ValidationResult:
        raise NotImplementedError

class JailbreakValidator(Validator):
    patterns = [
        r"ignore previous instructions",
        r"bypass rules",
        r"no restrictions",
        r"without limitations",
        r"act as.*without moral",
    ]
    
    def validate(self, text: str) -> ValidationResult:
        threats = []
        for pattern in self.patterns:
            if re.search(pattern, text, re.IGNORECASE):
                threats.append(f"Jailbreak pattern: {pattern}")
        
        if threats:
            return ValidationResult(
                allowed=False,
                threat_level=ThreatLevel.HIGH,
                reasons=threats,
                actions=["block_request", "log_incident"]
            )
        return ValidationResult(allowed=True)

class InjectionValidator(Validator):
    patterns = [
        r"execute code",
        r"eval\(",
        r"shell command",
        r"rm -rf",
        r"drop table",
        r"dump database",
    ]
    
    def validate(self, text: str) -> ValidationResult:
        threats = []
        for pattern in self.patterns:
            if re.search(pattern, text, re.IGNORECASE):
                threats.append(f"Injection pattern: {pattern}")
        
        if threats:
            return ValidationResult(
                allowed=False,
                threat_level=ThreatLevel.CRITICAL,
                reasons=threats,
                actions=["block_request", "alert_admin"]
            )
        return ValidationResult(allowed=True)

class Guard:
    def __init__(self):
        self.validators: List[Validator] = [
            JailbreakValidator(),
            InjectionValidator()
        ]
    
    async def validate(self, query: str, user_id: str = "anonymous") -> ValidationResult:
        """Validate input against all registered validators."""
        final_result = ValidationResult(allowed=True)
        
        for validator in self.validators:
            result = validator.validate(query)
            if not result.allowed:
                final_result.allowed = False
                final_result.threat_level = max(
                    final_result.threat_level, 
                    result.threat_level,
                    key=lambda x: ["none", "low", "medium", "high", "critical"].index(x.value)
                )
                final_result.reasons.extend(result.reasons)
                final_result.actions.extend(result.actions)
        
        if not final_result.allowed:
            logger.warning(f"Security violation by user {user_id}: {final_result.reasons}")
        
        return final_result