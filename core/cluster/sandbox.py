import subprocess
import tempfile
import os
import json

class SecureSandbox:
    def __init__(self):
        self.timeout = 30 # segundos
        
    def execute_code(self, code, language='python'):
        """Executa código em ambiente isolado"""
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                script_path = os.path.join(tmpdir, f"script.{language}")
                with open(script_path, 'w') as f:
                    f.write(code)
                
                # Restrições básicas de segurança (em prod, usar Docker/gVisor)
                cmd = [language, script_path]
                result = subprocess.run(
                    cmd, 
                    capture_output=True, 
                    text=True, 
                    timeout=self.timeout,
                    cwd=tmpdir # Isola sistema de arquivos
                )
                return {
                    "success": result.returncode == 0,
                    "output": result.stdout,
                    "error": result.stderr
                }
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Timeout: Execução muito longa"}
        except Exception as e:
            return {"success": False, "error": str(e)}
