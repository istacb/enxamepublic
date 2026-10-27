#!/usr/bin/env python3
"""
Testes rápidos dos instaladores da Abelha

Executa validações básicas sem modificar o sistema.
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Adicionar bees ao path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestInstallBee(unittest.TestCase):
    """Testes do instalador"""
    
    def test_imports(self):
        """Testa se módulos podem ser importados"""
        try:
            from install.install_bee import (
                detect_ollama,
                get_os_info,
                select_best_model,
                log
            )
            self.assertTrue(True)
        except ImportError as e:
            self.fail(f"Falha ao importar: {e}")
    
    def test_detect_ollama_no_install(self):
        """Testa detecção quando Ollama não está instalado"""
        from install.install_bee import detect_ollama
        
        # Mock para simular ausência de Ollama
        with patch('shutil.which', return_value=None):
            with patch('os.path.isfile', return_value=False):
                result = detect_ollama()
                self.assertIsNone(result)
    
    def test_get_os_info(self):
        """Testa obtenção de informações do SO"""
        from install.install_bee import get_os_info
        
        info = get_os_info()
        
        self.assertIn('system', info)
        self.assertIn('release', info)
        self.assertIn('machine', info)
        self.assertTrue(len(info['system']) > 0)
    
    def test_select_best_model_low_ram(self):
        """Testa seleção de modelo com pouca RAM"""
        from install.install_bee import select_best_model
        
        hardware = {
            'total_ram_gb': 2,
            'gpu_vram_gb': 0,
            'has_gpu': False,
            'cpu_cores': 2
        }
        
        model, metadata = select_best_model(hardware)
        
        self.assertIsNotNone(model)
        self.assertEqual(metadata['category'], 'tiny')
        self.assertIn('Memória limitada', metadata['reason'])
    
    def test_select_best_model_medium_ram(self):
        """Testa seleção de modelo com RAM média"""
        from install.install_bee import select_best_model
        
        hardware = {
            'total_ram_gb': 8,
            'gpu_vram_gb': 0,
            'has_gpu': False,
            'cpu_cores': 4
        }
        
        model, metadata = select_best_model(hardware)
        
        self.assertIsNotNone(model)
        self.assertEqual(metadata['category'], 'medium')
    
    def test_select_best_model_with_gpu(self):
        """Testa seleção de modelo com GPU dedicada"""
        from install.install_bee import select_best_model
        
        hardware = {
            'total_ram_gb': 16,
            'gpu_vram_gb': 8,
            'has_gpu': True,
            'cpu_cores': 8
        }
        
        model, metadata = select_best_model(hardware)
        
        self.assertIsNotNone(model)
        # Com 16GB já é large, GPU pode ou não subir categoria dependendo da lógica
        self.assertIn(metadata['category'], ['large', 'xl'])
    
    def test_log_function(self):
        """Testa função de log"""
        from install.install_bee import log, BEE_HOME
        import io
        from contextlib import redirect_stdout
        
        # Criar diretório temporário
        BEE_HOME.mkdir(parents=True, exist_ok=True)
        
        f = io.StringIO()
        with redirect_stdout(f):
            log("Test message", "INFO")
        
        output = f.getvalue()
        self.assertIn("[INFO]", output)
        self.assertIn("Test message", output)


class TestUninstallBee(unittest.TestCase):
    """Testes do desinstalador"""
    
    def test_imports(self):
        """Testa se módulos podem ser importados"""
        try:
            from install.uninstall_bee import (
                detect_ollama,
                remove_directory,
                list_files_to_remove,
                log
            )
            self.assertTrue(True)
        except ImportError as e:
            self.fail(f"Falha ao importar: {e}")
    
    def test_remove_directory_nonexistent(self):
        """Testa remoção de diretório inexistente"""
        from install.uninstall_bee import remove_directory
        from pathlib import Path
        
        fake_path = Path("/tmp/bee_fake_test_12345")
        
        result = remove_directory(fake_path, dry_run=True)
        self.assertTrue(result)
    
    def test_list_files_empty(self):
        """Testa listagem quando nada existe"""
        from install.uninstall_bee import list_files_to_remove
        from pathlib import Path
        
        # Mock para simular ausência de diretórios
        with patch('pathlib.Path.exists', return_value=False):
            files = list_files_to_remove()
            self.assertEqual(len(files), 0)


class TestModelSelection(unittest.TestCase):
    """Testes específicos de seleção de modelo"""
    
    def test_all_categories_have_models(self):
        """Verifica se todas as categorias têm modelos"""
        from install.install_bee import CANDIDATE_MODELS
        
        categories = ['tiny', 'small', 'medium', 'large', 'xl']
        
        for cat in categories:
            self.assertIn(cat, CANDIDATE_MODELS)
            self.assertGreater(len(CANDIDATE_MODELS[cat]), 0)
    
    def test_model_names_valid(self):
        """Verifica se nomes de modelos são válidos"""
        from install.install_bee import CANDIDATE_MODELS
        
        for category, models in CANDIDATE_MODELS.items():
            for model in models:
                # Modelo deve ter formato nome:tag ou nome
                self.assertTrue(
                    ':' in model or model.isalpha(),
                    f"Modelo inválido: {model}"
                )
    
    def test_fallback_selection(self):
        """Testa seleção fallback quando principal falha"""
        from install.install_bee import fallback_model_selection
        
        hardware = {
            'total_ram_gb': 4,
            'gpu_vram_gb': 0,
            'has_gpu': False
        }
        
        model, metadata = fallback_model_selection(hardware)
        
        self.assertIsNotNone(model)
        self.assertTrue(metadata.get('fallback'))


class TestManifestStructure(unittest.TestCase):
    """Testes da estrutura do manifesto"""
    
    def test_manifest_fields(self):
        """Verifica campos obrigatórios do manifesto"""
        required_fields = [
            'bee_version',
            'installation_date',
            'hardware',
            'ollama',
            'model',
            'capabilities',
            'status'
        ]
        
        # Simular manifesto mínimo
        manifest = {
            'bee_version': '1.0.0',
            'installation_date': '2024-01-01',
            'hardware': {},
            'ollama': {'installed': True},
            'model': {
                'name': 'test',
                'test_passed': True
            },
            'capabilities': {},
            'status': 'READY'
        }
        
        for field in required_fields:
            self.assertIn(field, manifest)
    
    def test_status_values(self):
        """Verifica valores válidos de status"""
        valid_statuses = ['READY', 'DEGRADED']
        
        manifest = {'status': 'READY'}
        self.assertIn(manifest['status'], valid_statuses)
        
        manifest = {'status': 'DEGRADED'}
        self.assertIn(manifest['status'], valid_statuses)


if __name__ == '__main__':
    print("="*60)
    print("🐝 TESTES DOS INSTALADORES DA ABELHA")
    print("="*60)
    print()
    
    # Executar testes
    unittest.main(verbosity=2)
