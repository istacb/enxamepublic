import time
import json
import os
from datetime import datetime

class Guardian:
    def __init__(self, node_id):
        self.node_id = node_id
        self.suspicious_nodes = set()
        self.quarantine_dir = "quarantine"
        if not os.path.exists(self.quarantine_dir):
            os.makedirs(self.quarantine_dir)
        
    def monitor_behavior(self, node_metrics):
        """Detecta anomalias de comportamento"""
        anomalies = []
        if node_metrics.get('response_time', 0) > 60: # > 1 min
            anomalies.append("LATENCIA_CRITICA")
        if node_metrics.get('cpu', 0) > 95:
            anomalies.append("CPU_EXHAUSTAO")
        return anomalies

    def detect_injection(self, text):
        patterns = ["ignore previous", "you are now", "system prompt", "desconsidere"]
        text_lower = text.lower()
        for p in patterns:
            if p in text_lower:
                return True
        return False

    def quarantine_node(self, node_id, reason):
        print(f"[GUARDIAN] Isolando nó {node_id}: {reason}")
        log_entry = {
            "action": "QUARANTINE",
            "target": node_id,
            "reason": reason,
            "timestamp": datetime.now().isoformat()
        }
        with open(os.path.join(self.quarantine_dir, f"{node_id}_log.json"), 'w') as f:
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
