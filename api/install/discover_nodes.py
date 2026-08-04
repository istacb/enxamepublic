#!/usr/bin/env python3
"""
ENXAME - Node Discovery and Registration Script
Usado pelos instaladores para:
1. Descobrir nodes existentes na rede via mDNS
2. Registrar o novo node no enxame
3. Anunciar capacidades do node após instalação
4. Confirmar função assumida pelo node
"""

import os
import sys
import json
import socket
import subprocess
from datetime import datetime
from pathlib import Path

# Adiciona o core ao path para importar módulos de discovery
SCRIPT_DIR = Path(__file__).parent
ENXAME_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(ENXAME_ROOT))

try:
    from core.discovery.browser import ENXAMEMDNSBrowser
    from core.discovery.advertiser import ENXAMEMDNSAdvertiser
    HAS_ZEROCONF = True
except ImportError:
    HAS_ZEROCONF = False
    print("Aviso: zeroconf não disponível. Descoberta mDNS limitada.")


def discover_existing_nodes(timeout=5):
    """Descobre nodes existentes na rede via mDNS"""
    print("\n🔍 Descobrindo nodes do Enxame na rede...")
    
    if not HAS_ZEROCONF:
        print("  ! mDNS indisponível, tentando descoberta HTTP...")
        return discover_via_http()
    
    browser = ENXAMEMDNSBrowser()
    discovered = []
    
    try:
        browser.start()
        print(f"  Aguardando {timeout}s para descoberta mDNS...")
        
        # Aguarda timeout para descoberta
        import time
        time.sleep(timeout)
        
        # Coleta nodes descobertos
        for name, node in browser.nodes.items():
            discovered.append({
                'name': name,
                'node_id': node.node_id,
                'role': node.role,
                'host': node.host,
                'port': node.port,
                'capabilities': node.capabilities,
                'models': node.models
            })
            print(f"  ✓ Encontrado: {node.role} ({node.node_id}) em {node.host}:{node.port}")
        
        if not discovered:
            print("  ! Nenhum node encontrado via mDNS")
            
    except Exception as e:
        print(f"  ! Erro na descoberta mDNS: {e}")
    finally:
        try:
            browser.stop()
        except:
            pass
    
    # Tenta descoberta HTTP como fallback
    if not discovered:
        discovered = discover_via_http()
    
    return discovered


def discover_via_http():
    """Descobre nodes via HTTP em portas conhecidas"""
    print("  Tentando descoberta HTTP em portas conhecidas...")
    discovered = []
    
    ports = {
        8080: 'kernel',
        8081: 'bibliotecario',
        8082: 'juiz',
        8083: 'agente',
        8084: 'worker',
        8085: 'worker'
    }
    
    try:
        import urllib.request
        for port, expected_role in ports.items():
            try:
                url = f"http://localhost:{port}/api/health"
                req = urllib.request.urlopen(url, timeout=2)
                if req.status == 200:
                    data = json.loads(req.read().decode())
                    discovered.append({
                        'name': f"node-{port}",
                        'node_id': data.get('node', f'unknown-{port}'),
                        'role': expected_role,
                        'host': 'localhost',
                        'port': port,
                        'capabilities': 'http',
                        'models': ''
                    })
                    print(f"  ✓ Encontrado: {expected_role} em localhost:{port}")
            except:
                pass
    except Exception as e:
        print(f"  ! Erro na descoberta HTTP: {e}")
    
    return discovered


def advertise_node(node_id, role, port, capabilities='exp,ws,http', models=''):
    """Anuncia o node recém-instalado na rede via mDNS"""
    print(f"\n📢 Anunciando node {role} na rede...")
    
    if not HAS_ZEROCONF:
        print("  ! mDNS indisponível, node não será anunciado automaticamente")
        return False
    
    try:
        # Pega IP local
        hostname = socket.gethostname()
        host_ip = socket.gethostbyname(hostname)
        
        advertiser = ENXAMEMDNSAdvertiser(
            service_name='enxame',
            node_id=node_id,
            role=role,
            host_ip=host_ip,
            port=port,
            capabilities=capabilities,
            models=models
        )
        
        advertiser.start()
        print(f"  ✓ Node anunciado como {node_id} ({role}) em {host_ip}:{port}")
        print(f"  Capabilities: {capabilities}")
        
        return advertiser
        
    except Exception as e:
        print(f"  ! Erro ao anunciar node: {e}")
        return None


def register_with_cluster(node_id, role, host, port, existing_nodes):
    """Registra o novo node com o cluster existente"""
    if not existing_nodes:
        print("\n  ℹ Primeiro node do cluster - nenhum registro necessário")
        return True
    
    print(f"\n📝 Registrando node {node_id} ({role}) com o cluster...")
    
    # Tenta registrar com o Kernel (porta 8080)
    kernel_node = None
    for node in existing_nodes:
        if node.get('role') == 'kernel' or node.get('port') == 8080:
            kernel_node = node
            break
    
    if not kernel_node:
        print("  ! Kernel não encontrado, registro automático indisponível")
        print("  ℹ O node será descoberto automaticamente via mDNS")
        return False
    
    try:
        import urllib.request
        kernel_url = f"http://{kernel_node['host']}:{kernel_node['port']}"
        
        # Prepara payload de registro
        payload = json.dumps({
            'node_id': node_id,
            'role': role,
            'host': host,
            'port': port,
            'capabilities': 'exp,ws,http',
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        }).encode('utf-8')
        
        req = urllib.request.Request(
            f"{kernel_url}/api/cluster/register",
            data=payload,
            headers={'Content-Type': 'application/json'},
            method='POST'
        )
        
        response = urllib.request.urlopen(req, timeout=5)
        if response.status == 200:
            print(f"  ✓ Registrado com sucesso no Kernel ({kernel_node['host']}:{kernel_node['port']})")
            return True
        else:
            print(f"  ! Resposta inesperada do Kernel: {response.status}")
            return False
            
    except Exception as e:
        print(f"  ! Erro ao registrar com Kernel: {e}")
        print("  ℹ O node será descoberto automaticamente via mDNS")
        return False


def confirm_role_assignment(node_id, role, existing_nodes):
    """Envia confirmação de função assumida pelo node"""
    print(f"\n✅ Confirmando função {role} para node {node_id}...")
    
    if not existing_nodes:
        print("  ℹ Primeiro node - função auto-confirmada")
        return True
    
    # Envia mensagem de ROLE_ACK para o cluster
    for node in existing_nodes:
        if node.get('role') == 'juiz' or node.get('port') == 8082:
            try:
                import urllib.request
                juiz_url = f"http://{node['host']}:{node['port']}"
                
                payload = json.dumps({
                    'type': 'ROLE_ACK',
                    'source': node_id,
                    'role': role,
                    'status': 'assumed',
                    'timestamp': datetime.utcnow().isoformat() + 'Z'
                }).encode('utf-8')
                
                req = urllib.request.Request(
                    f"{juiz_url}/api/v1/exp",
                    data=payload,
                    headers={'Content-Type': 'application/json'},
                    method='POST'
                )
                
                response = urllib.request.urlopen(req, timeout=5)
                print(f"  ✓ Confirmação enviada ao Juiz ({node['host']}:{node['port']})")
                return True
                
            except Exception as e:
                print(f"  ! Erro ao enviar confirmação: {e}")
    
    print("  ℹ Confirmação será enviada via heartbeat")
    return True


def main():
    """Função principal chamada pelos instaladores"""
    if len(sys.argv) < 2:
        print("Uso: python discover_nodes.py <comando> [args...]")
        print("Comandos:")
        print("  discover              - Descobre nodes existentes")
        print("  advertise <id> <role> <port> - Anuncia node na rede")
        print("  register <id> <role> <host> <port> - Registra no cluster")
        print("  confirm <id> <role>   - Confirma função assumida")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == 'discover':
        nodes = discover_existing_nodes()
        print(f"\nTotal: {len(nodes)} node(s) descoberto(s)")
        return json.dumps({'nodes': nodes, 'count': len(nodes)})
        
    elif command == 'advertise':
        if len(sys.argv) < 5:
            print("Erro: advertise requer <node_id> <role> <port>")
            sys.exit(1)
        node_id = sys.argv[2]
        role = sys.argv[3]
        port = int(sys.argv[4])
        advertiser = advertise_node(node_id, role, port)
        if advertiser:
            # Mantém anúncio ativo por alguns segundos
            import time
            time.sleep(2)
            advertiser.stop()
        return 'OK' if advertiser else 'FAIL'
        
    elif command == 'register':
        if len(sys.argv) < 6:
            print("Erro: register requer <node_id> <role> <host> <port>")
            sys.exit(1)
        node_id = sys.argv[2]
        role = sys.argv[3]
        host = sys.argv[4]
        port = int(sys.argv[5])
        existing = discover_existing_nodes(timeout=3)
        success = register_with_cluster(node_id, role, host, port, existing)
        return 'OK' if success else 'FAIL'
        
    elif command == 'confirm':
        if len(sys.argv) < 4:
            print("Erro: confirm requer <node_id> <role>")
            sys.exit(1)
        node_id = sys.argv[2]
        role = sys.argv[3]
        existing = discover_existing_nodes(timeout=3)
        success = confirm_role_assignment(node_id, role, existing)
        return 'OK' if success else 'FAIL'
    
    else:
        print(f"Comando desconhecido: {command}")
        sys.exit(1)


if __name__ == '__main__':
    result = main()
    if result not in ['OK', 'FAIL']:
        print(result)
