import json
import os
import time
from datetime import datetime


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

    def detect_injection(self, text):
        patterns = ['ignore previous', 'you are now', 'system prompt', 'desconsidere']
        text_lower = text.lower()
        for p in patterns:
            if p in text_lower:
                return True
        return False

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
