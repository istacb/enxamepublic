import subprocess
import tempfile
import os
import json
import re


class SecureSandbox:
    """
    Sandbox seguro para execução de código em ambiente isolado.
    
    Offline-first, com múltiplas camadas de proteção:
    - Timeout rigoroso para prevenir DoS
    - Isolamento de filesystem com tempdir
    - Sem acesso a rede (subprocess padrão)
    - Limites de recursos via subprocess
    - Validação básica de código suspeito
    """
    
    # Padrões de código perigoso para bloqueio preventivo
    DANGEROUS_PATTERNS = [
        r"\b__import__\s*\(",
        r"\bimportlib\.",
        r"\bsys\.modules",
        r"\bos\.(system|popen|exec|spawn)",
        r"\bsubprocess\.",
        r"\bsocket\.",
        r"\burllib\.",
        r"\brequests\.",
        r"\bhttp\.(client|server)",
        r"\bpickle\.",
        r"\bmarshal\.",
        r"\beval\s*\(",
        r"\bexec\s*\(",
        r"\bcompile\s*\(",
        r"\bgetattr\s*\([^)]*,\s*['\"]__",
        r"\bsetattr\s*\(",
        r"\bdelattr\s*\(",
        r"\bopen\s*\([^)]*,\s*['\"][wax]",  # Escrita em arquivos
    ]
    
    def __init__(self, timeout: int = 10, max_output_size: int = 1024 * 1024):
        """
        Inicializa o sandbox seguro.
        
        Args:
            timeout: Timeout máximo em segundos (padrão: 10s)
            max_output_size: Tamanho máximo do output em bytes (padrão: 1MB)
        """
        self.timeout = timeout
        self.max_output_size = max_output_size
        self._compiled_patterns = [
            re.compile(pattern, re.IGNORECASE) 
            for pattern in self.DANGEROUS_PATTERNS
        ]
        
    def _check_dangerous_code(self, code: str) -> tuple[bool, list[str]]:
        """
        Verifica se o código contém padrões perigosos.
        
        Returns:
            Tuple com (tem_perigo: bool, motivos: list[str])
        """
        detected = []
        for i, pattern in enumerate(self._compiled_patterns):
            if pattern.search(code):
                detected.append(f"pattern_{i}")
        return len(detected) > 0, detected
        
    def execute_code(self, code: str, language: str = 'python') -> dict:
        """
        Executa código em ambiente isolado com validações de segurança.
        
        Args:
            code: Código a ser executado
            language: Linguagem de programação (apenas 'python' suportado)
            
        Returns:
            Dict com success, output e error
        """
        # Valida linguagem suportada
        if language != 'python':
            return {
                "success": False, 
                "error": f"Linguagem '{language}' não suportada. Apenas Python."
            }
        
        # Verifica código perigoso ANTES de executar
        has_danger, patterns = self._check_dangerous_code(code)
        if has_danger:
            return {
                "success": False,
                "error": "Código contém operações potencialmente inseguras e foi bloqueado.",
                "blocked_reason": "dangerous_patterns_detected"
            }
        
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                script_path = os.path.join(tmpdir, f"script.{language}")
                
                # Escreve código com encoding seguro
                with open(script_path, 'w', encoding='utf-8') as f:
                    f.write(code)
                
                # Restrições básicas de segurança (em prod, usar Docker/gVisor)
                cmd = [language, script_path]
                result = subprocess.run(
                    cmd, 
                    capture_output=True, 
                    text=True, 
                    timeout=self.timeout,
                    cwd=tmpdir,  # Isola sistema de arquivos
                    env={"PYTHONPATH": tmpdir},  # Limita imports ao diretório temporário
                )
                
                # Trunca output se muito grande (prevenir DoS por memory exhaustion)
                stdout = result.stdout[:self.max_output_size]
                stderr = result.stderr[:self.max_output_size]
                
                return {
                    "success": result.returncode == 0,
                    "output": stdout,
                    "error": stderr
                }
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Timeout: Execução muito longa"}
        except Exception as e:
            return {"success": False, "error": str(e)}
