import threading
from collections import deque
import json

class HotCache:
    def __init__(self, max_size=100):
        self.buffer = deque(maxlen=max_size)
        self.lock = threading.Lock()
        self.mirrors = [] # Nós espelhados
    
    def add_context(self, task_id, context_data):
        with self.lock:
            entry = {"id": task_id, "data": context_data, "ts": __import__('time').time()}
            self.buffer.append(entry)
            self._mirror_to_peers(entry)
    
    def _mirror_to_peers(self, entry):
        # Simula envio para nós vizinhos para failover instantâneo
        for peer in self.mirrors:
            try:
                # peer.send(entry)
                pass
            except:
                pass
    
    def get_recent(self, count=10):
        with self.lock:
            return list(self.buffer)[-count:]
            
    def add_mirror(self, peer_node):
        self.mirrors.append(peer_node)
