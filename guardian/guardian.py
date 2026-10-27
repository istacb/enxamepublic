import json
import os
import re
import time
from datetime import datetime
from typing import Any

from core.exp.input_sanitizer import InputSanitizer, get_sanitizer


class Guardian:
    """Instância de segurança do Enxame.

    O Guardião não é um serviço que o usuário acessa: ele roda em ronda
    (patrol) dentro de cada node, monitorando comportamento local e
    detectando tentativas de ataque/injeção. Ver guardian/patrol.py para o
    laço assíncrono que usa esta classe e envia os alertas encontrados
    para o Juiz, que agrega o estado de segurança de todo o cluster.
    """

    def __init__(self, node_id):
        self.node_id = node_id
        self.suspicious_nodes = set()
        self.quarantine_dir = 'quarantine'
        if not os.path.exists(self.quarantine_dir):
            os.makedirs(self.quarantine_dir)
        
        # Inicializa pipeline de sanitização em duas camadas
        self._sanitizer = get_sanitizer(strict_mode=False)

    def monitor_behavior(self, node_metrics):
        """Detecta anomalias de comportamento"""
        anomalies = []
        if node_metrics.get('response_time', 0) > 60:  # > 1 min
            anomalies.append('LATENCIA_CRITICA')
        if node_metrics.get('cpu', 0) > 95:
            anomalies.append('CPU_EXHAUSTAO')
        if node_metrics.get('mem', 0) > 95:
            anomalies.append('MEMORIA_EXHAUSTAO')
        return anomalies

    def build_alert(self, node_metrics: dict) -> dict | None:
        """Roda monitor_behavior e monta um alerta pronto para ser enviado
        ao Juiz (ou agregado localmente, se este node for o Juiz). Retorna
        None quando nenhuma anomalia é encontrada, para que a ronda não
        gere tráfego/ruído desnecessário."""
        anomalies = self.monitor_behavior(node_metrics)
        if not anomalies:
            return None
        return {
            'node_id': self.node_id,
            'anomalies': anomalies,
            'metrics': node_metrics,
            'timestamp': datetime.now().isoformat(),
        }

    def inspect_prompt(self, text: str) -> dict[str, Any]:
        """Pipeline de inspeção de segurança em duas camadas.
        
        Camada 1 (Heurística/Regex): Detecção instantânea de padrões nocivos.
        Camada 2 (Filtro Categórico): Validação estrutural do prompt.
        
        Returns:
            dict com:
                - safe: bool indicando se o prompt é seguro
                - layer: int indicando qual camada detectou (1 ou 2)
                - reasons: list[str] com motivos da detecção
                - sanitized_text: str com texto sanitizado (se seguro)
        """
        result = {
            'safe': True,
            'layer': None,
            'reasons': [],
            'sanitized_text': None,
            'error_message': None,
        }
        
        # === CAMADA 1: Heurística/Regex ===
        layer1_result = self._layer1_heuristic_scan(text)
        if not layer1_result['safe']:
            result['safe'] = False
            result['layer'] = 1
            result['reasons'] = layer1_result['reasons']
            result['error_message'] = self._build_friendly_error(layer1_result['reasons'])
            return result
        
        # === CAMADA 2: Filtro Categórico/Estrutural ===
        layer2_result = self._layer2_categorical_filter(text)
        if not layer2_result['safe']:
            result['safe'] = False
            result['layer'] = 2
            result['reasons'] = layer2_result['reasons']
            result['error_message'] = self._build_friendly_error(layer2_result['reasons'])
            return result
        
        # Prompt passou por ambas as camadas
        result['safe'] = True
        result['sanitized_text'] = self._sanitizer.sanitize_for_llm(text)
        return result

    def _layer1_heuristic_scan(self, text: str) -> dict[str, Any]:
        """Camada 1: Detecção instantânea via heurística e regex.
        
        Verifica:
        - Palavras-chave nocivas (jailbreak, bypass, ignore instructions)
        - Caracteres de controle suspeitos
        - Tentativas de bypass conhecidas
        """
        reasons = []
        text_lower = text.lower()
        
        # Padrões de jailbreak e prompt injection
        jailbreak_patterns = [
            ('ignore previous', 'Tentativa de ignorar instruções anteriores'),
            ('you are now', 'Tentativa de redefinir identidade do sistema'),
            ('system prompt', 'Tentativa de acessar prompt de sistema'),
            ('desconsidere', 'Tentativa de desconsiderar regras'),
            ('forget everything', 'Tentativa de resetar memória/contexto'),
            ('override security', 'Tentativa de sobrescrever segurança'),
            ('bypass filter', 'Tentativa de burlar filtros'),
            ('developer mode', 'Tentativa de ativar modo desenvolvedor'),
            ('dan mode', 'Tentativa de ativar modo DAN'),
            ('act as if you can', 'Tentativa de simular capacidades irrestritas'),
            ('pretend you are', 'Tentativa de personificação indevida'),
            ('disable safety', 'Tentativa de desativar proteções'),
        ]
        
        for pattern, reason in jailbreak_patterns:
            if pattern in text_lower:
                reasons.append(reason)
        
        # Caracteres de controle suspeitos
        control_chars = ['\x00', '\x1b', '\x9b']
        for char in control_chars:
            if char in text:
                reasons.append(f'Caractere de controle detectado: {repr(char)}')
        
        # Tentativas de injeção de código
        code_injection_patterns = [
            r'__builtins__',
            r'__import__',
            r'eval\s*\(',
            r'exec\s*\(',
            r'os\.system',
            r'subprocess\.',
            r'globals\s*\(\)',
            r'locals\s*\(\)',
        ]
        
        for pattern in code_injection_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                reasons.append(f'Padrão de injeção de código: {pattern}')
        
        # Usa o detector do InputSanitizer como complemento
        detected, patterns = self._sanitizer.detect_prompt_injection(text)
        if detected:
            reasons.append(f'Padrões de injection detectados: {len(patterns)} ocorrências')
        
        return {
            'safe': len(reasons) == 0,
            'reasons': reasons,
        }

    def _layer2_categorical_filter(self, text: str) -> dict[str, Any]:
        """Camada 2: Filtro categórico/estrutural.
        
        Valida a estrutura do prompt garantindo que não há:
        - Comandos de sobrescrita de instrução de sistema
        - Tentativas de escape de contexto
        - Estruturas de prompt maliciosas
        """
        reasons = []
        text_lower = text.lower()
        
        # Verifica tentativa de sobrescrita de instrução de sistema
        system_override_indicators = [
            'nova instrução:',
            'new instruction:',
            'instrução de sistema:',
            'system instruction:',
            'regra principal:',
            'primeira regra:',
            'ignore todas as regras',
            'esqueça todas as diretrizes',
        ]
        
        for indicator in system_override_indicators:
            if indicator in text_lower:
                reasons.append(f'Tentativa de sobrescrita de sistema: "{indicator}"')
        
        # Verifica tentativas de escape de contexto
        escape_attempts = [
            text.count('"""') >= 4,
            text.count("'''") >= 4,
            text.count('<<<') >= 2 and text.count('>>>') >= 2,
            text.count('---BEGIN---') >= 1 or text.count('---END---') >= 1,
        ]
        
        if sum(escape_attempts) >= 2:
            reasons.append('Múltiplas tentativas de delimitação de contexto suspeitas')
        
        # Verifica comandos embutidos suspeitos
        if self._sanitizer._has_embedded_commands(text):
            reasons.append('Comandos embutidos suspeitos detectados na estrutura do prompt')
        
        # Verifica proporção de caracteres especiais (possível ofuscação)
        special_chars_ratio = sum(1 for c in text if not c.isalnum() and not c.isspace()) / max(len(text), 1)
        if special_chars_ratio > 0.4 and len(text) > 50:
            reasons.append('Proporção excessiva de caracteres especiais (possível ofuscação)')
        
        # Verifica tentativas de acesso a dados sensíveis
        sensitive_keywords = [
            'api key',
            'senha',
            'password',
            'token secreto',
            'secret token',
            'chave privada',
            'private key',
            'credential',
        ]
        
        for keyword in sensitive_keywords:
            if keyword in text_lower and ('revele' in text_lower or 'mostre' in text_lower or 'exponha' in text_lower):
                reasons.append(f'Tentativa de vazamento de dados sensíveis: "{keyword}"')
        
        return {
            'safe': len(reasons) == 0,
            'reasons': reasons,
        }

    def _build_friendly_error(self, reasons: list[str]) -> str:
        """Constrói mensagem de erro amigável para o usuário."""
        return (
            f"⚠️ Sua requisição não pôde ser processada por conter padrões inseguros.\n"
            f"Motivos detectados:\n"
            + "\n".join(f"  • {reason}" for reason in reasons[:3])
            + "\n\nPor favor, reformule sua solicitação de forma mais clara e direta."
        )

    def detect_injection(self, text):
        """Método legado mantido para compatibilidade.
        Usa a nova pipeline de inspeção."""
        result = self.inspect_prompt(text)
        return not result['safe']

    def quarantine_node(self, node_id, reason):
        print(f'[GUARDIAN] Isolando nó {node_id}: {reason}')
        log_entry = {
            'action': 'QUARANTINE',
            'target': node_id,
            'reason': reason,
            'timestamp': datetime.now().isoformat(),
        }
        with open(os.path.join(self.quarantine_dir, f'{node_id}_log.json'), 'w') as f:
            json.dump(log_entry, f)
        self.suspicious_nodes.add(node_id)

    def verify_integrity(self, file_path):
        # Verificação de hash seria implementada aqui
        return True

    def sentinel_mode(self):
        """Loop principal que nunca dorme"""
        while True:
            # Monitoramento contínuo
            time.sleep(5)
            # Lógica de monitoramento de rede e recursos
            pass
