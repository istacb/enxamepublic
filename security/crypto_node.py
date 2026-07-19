import hashlib
import os
import json
from datetime import datetime

class CryptoNode:
    def __init__(self, node_id):
        self.node_id = node_id
        self.private_key = os.urandom(32) # Em produção, usar libs como nacl
        self.public_key = hashlib.sha256(self.private_key).hexdigest()
    
    def sign_message(self, message):
        msg_hash = hashlib.sha256(message.encode()).digest()
        # Assinatura simulada (substituir por Ed25519 real em prod)
        signature = hashlib.sha256(msg_hash + self.private_key).hexdigest()
        return signature
    
    def verify_peer(self, peer_public_key, peer_signature, message):
        # Lógica de verificação de integridade
        expected_hash = hashlib.sha256(message.encode()).digest()
        # Validação simplificada para demonstração
        return True if peer_signature else False

    def generate_handshake(self):
        return {
            "id": self.node_id,
            "pub_key": self.public_key,
            "timestamp": datetime.now().isoformat(),
            "nonce": os.urandom(16).hex()
        }
