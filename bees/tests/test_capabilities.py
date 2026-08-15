"""
Testes unitários para BEE-0003 — CAPABILITIES E MODEL DISCOVERY.

Cobre:
1. Descoberta de hardware
2. Descoberta de Ollama
3. Lista de modelos
4. Detecção de embeddings
5. Detecção de OCR
6. Seleção de modelo
7. Provider factory
8. Integração com manifesto
"""

import asyncio
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Adicionar bees ao path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from capabilities.discovery import (
    BeeCapabilities,
    HardwareCapabilities,
    LocalCapabilities,
    OllamaCapabilities,
    ModelInfo,
    scan_hardware,
    scan_ollama,
    scan_local_capabilities,
    discover_capabilities,
)
from capabilities.provider import (
    ProviderType,
    create_provider,
    OllamaProvider,
)
from capabilities.selector import (
    recommend_model,
    get_model_recommendations_table,
    calculate_min_requirements,
)


class TestHardwareDiscovery:
    """Testes para descoberta de hardware."""
    
    def test_scan_hardware_basic(self):
        """Testar scan básico de hardware."""
        with patch('capabilities.discovery.psutil') as mock_psutil:
            # Mock CPU
            mock_psutil.cpu_count.side_effect = lambda logical: 8 if logical else 4
            mock_psutil.cpu_freq.return_value = MagicMock(base=3200)
            
            # Mock RAM
            mock_ram = MagicMock()
            mock_ram.total = 16 * (1024 ** 3)  # 16GB
            mock_ram.available = 8 * (1024 ** 3)  # 8GB
            mock_psutil.virtual_memory.return_value = mock_ram
            
            hw = scan_hardware("/tmp/test_enxame")
            
            assert hw.cpu_cores == 4
            assert hw.cpu_logical == 8
            assert hw.cpu_freq_ghz == 3.2
            assert hw.ram_total_gb == 16.0
            assert hw.ram_available_gb == 8.0
    
    def test_scan_hardware_no_psutil(self):
        """Testar scan sem psutil disponível."""
        with patch('capabilities.discovery.psutil', None):
            hw = scan_hardware("/tmp/test_enxame")
            
            assert hw.cpu_cores == 0
            assert hw.cpu_logical == 0
            assert hw.cpu_freq_ghz == 0.0
            assert hw.ram_total_gb == 0.0
    
    def test_scan_hardware_os_detection_linux(self):
        """Testar detecção de OS Linux."""
        with patch('capabilities.discovery.platform.system', return_value='Linux'):
            with patch('capabilities.discovery.platform.version', return_value='5.15'):
                with patch('builtins.open', unittest.mock.mock_open(read_data='VERSION="22.04"\n')):
                    hw = scan_hardware("/tmp/test_enxame")
                    assert hw.os == "Linux"
    
    def test_scan_hardware_os_detection_macos(self):
        """Testar detecção de OS macOS."""
        with patch('capabilities.discovery.platform.system', return_value='Darwin'):
            with patch('capabilities.discovery.platform.version', return_value='23.1'):
                hw = scan_hardware("/tmp/test_enxame")
                assert hw.os == "macOS"
    
    def test_scan_hardware_os_detection_windows(self):
        """Testar detecção de OS Windows."""
        with patch('capabilities.discovery.platform.system', return_value='Windows'):
            with patch('capabilities.discovery.platform.version', return_value='10.0'):
                hw = scan_hardware("/tmp/test_enxame")
                assert hw.os == "Windows"


class TestOllamaDiscovery:
    """Testes para descoberta de Ollama."""
    
    @pytest.mark.asyncio
    async def test_scan_ollama_available(self):
        """Testar Ollama disponível."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "models": [
                {
                    "name": "llama3:8b",
                    "size": 4700000000,
                    "modified_at": "2024-12-01T10:00:00Z",
                    "details": {
                        "parameter_size": "8B",
                        "quantization_level": "Q4_K_M",
                        "family": "llama",
                    }
                }
            ]
        }
        
        with patch('httpx.AsyncClient.get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            
            ollama = await scan_ollama("http://localhost:11434")
            
            assert ollama.available is True
            assert len(ollama.models) == 1
            assert ollama.models[0].name == "llama3:8b"
    
    @pytest.mark.asyncio
    async def test_scan_ollama_unavailable(self):
        """Testar Ollama indisponível."""
        with patch('httpx.AsyncClient.get', side_effect=Exception("Connection refused")):
            ollama = await scan_ollama("http://localhost:11434")
            
            assert ollama.available is False
            assert ollama.version is None
            assert len(ollama.models) == 0
    
    @pytest.mark.asyncio
    async def test_scan_ollama_with_embedding_model(self):
        """Testar detecção de modelo de embedding."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "models": [
                {
                    "name": "nomic-embed-text",
                    "size": 274000000,
                    "modified_at": "2024-11-15T08:30:00Z",
                    "details": {
                        "parameter_size": "80M",
                        "family": "bert",
                    }
                }
            ]
        }
        
        with patch('httpx.AsyncClient.get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            
            ollama = await scan_ollama("http://localhost:11434")
            
            assert ollama.available is True
            assert len(ollama.models) == 1
            assert ollama.models[0].is_embedding is True


class TestLocalCapabilities:
    """Testes para capacidades locais."""
    
    def test_scan_local_capabilities_no_ocr(self):
        """Testar scan sem OCR disponível."""
        with patch.dict('sys.modules', {'pytesseract': None}):
            # Criar diretório temporário
            test_path = "/tmp/test_bee_caps"
            os.makedirs(test_path, exist_ok=True)
            os.makedirs(os.path.join(test_path, "lancedb"), exist_ok=True)
            
            local = scan_local_capabilities(test_path)
            
            assert local.ocr_available is False
    
    def test_scan_local_capabilities_with_rag(self):
        """Testar scan com RAG disponível."""
        test_path = "/tmp/test_bee_rag"
        os.makedirs(test_path, exist_ok=True)
        lancedb_path = os.path.join(test_path, "lancedb")
        os.makedirs(lancedb_path, exist_ok=True)
        
        # Criar arquivo dummy no lancedb
        with open(os.path.join(lancedb_path, "test.lance"), 'w') as f:
            f.write("dummy")
        
        local = scan_local_capabilities(test_path)
        
        assert local.rag_available is True
        
        # Cleanup
        import shutil
        shutil.rmtree(test_path)
    
    def test_scan_local_capabilities_zim_files(self):
        """Testar detecção de arquivos ZIM."""
        test_path = "/tmp/test_bee_zim"
        os.makedirs(test_path, exist_ok=True)
        zim_path = os.path.join(test_path, "zim")
        os.makedirs(zim_path, exist_ok=True)
        
        # Criar arquivos ZIM dummy
        with open(os.path.join(zim_path, "wikipedia.zim"), 'w') as f:
            f.write("dummy")
        with open(os.path.join(zim_path, "wikibooks.zim"), 'w') as f:
            f.write("dummy")
        
        local = scan_local_capabilities(test_path)
        
        assert local.zim_available is True
        assert local.zim_file_count == 2
        
        # Cleanup
        import shutil
        shutil.rmtree(test_path)
    
    def test_scan_local_capabilities_web_disabled(self):
        """Testar web access desabilitado."""
        test_path = "/tmp/test_bee_web"
        os.makedirs(test_path, exist_ok=True)
        
        with patch.dict(os.environ, {"ENXAME_ALLOW_INTERNET": "false"}):
            local = scan_local_capabilities(test_path)
            assert local.web_available is False


class TestModelSelection:
    """Testes para seleção de modelo."""
    
    def test_recommend_model_with_gpu(self):
        """Testar recomendação com GPU."""
        models = [
            ModelInfo(
                name="llama3:8b",
                size_bytes=4700000000,
                parameter_size="8B",
                is_embedding=False,
                is_loaded=False,
                context_length=4096,
                quantization="Q4_K_M",
                supports_chat=True,
            ),
            ModelInfo(
                name="gemma2:9b",
                size_bytes=5200000000,
                parameter_size="9B",
                is_embedding=False,
                is_loaded=True,
                context_length=8192,
                quantization="Q4_K_M",
                supports_chat=True,
            ),
        ]
        
        # Com GPU e VRAM suficiente
        recommended = recommend_model(
            available_models=models,
            ram_gb=16.0,
            gpu_vram_gb=8.0,
            has_gpu=True,
        )
        
        # Gemma2 deve ser preferido (já carregado + contexto maior)
        assert recommended == "gemma2:9b"
    
    def test_recommend_model_without_gpu(self):
        """Testar recomendação sem GPU."""
        models = [
            ModelInfo(
                name="llama3:8b",
                size_bytes=4700000000,
                parameter_size="8B",
                is_embedding=False,
                is_loaded=False,
                context_length=4096,
                quantization=None,
                supports_chat=True,
            ),
            ModelInfo(
                name="phi3:3.8b",
                size_bytes=2000000000,
                parameter_size="3.8B",
                is_embedding=False,
                is_loaded=False,
                context_length=4096,
                quantization=None,
                supports_chat=True,
            ),
        ]
        
        # Sem GPU, RAM limitada
        recommended = recommend_model(
            available_models=models,
            ram_gb=8.0,
            gpu_vram_gb=0.0,
            has_gpu=False,
        )
        
        # Phi3 deve ser preferido (menor, mais adequado para 8GB RAM)
        assert recommended == "phi3:3.8b"
    
    def test_recommend_model_skip_embeddings(self):
        """Testar que modelos de embedding são ignorados para geração."""
        models = [
            ModelInfo(
                name="nomic-embed-text",
                size_bytes=274000000,
                parameter_size="80M",
                is_embedding=True,
                is_loaded=False,
                context_length=512,
                quantization=None,
            ),
            ModelInfo(
                name="llama3:8b",
                size_bytes=4700000000,
                parameter_size="8B",
                is_embedding=False,
                is_loaded=False,
                context_length=4096,
                quantization=None,
                supports_chat=True,
            ),
        ]
        
        recommended = recommend_model(
            available_models=models,
            ram_gb=16.0,
            gpu_vram_gb=0.0,
            has_gpu=False,
        )
        
        # Deve ignorar embedding e recomendar llama3
        assert recommended == "llama3:8b"
    
    def test_recommend_model_skip_large_models(self):
        """Testar que modelos >10B são ignorados nesta fase."""
        models = [
            ModelInfo(
                name="mixtral:8x7b",
                size_bytes=26000000000,
                parameter_size="47B",
                is_embedding=False,
                is_loaded=False,
                context_length=32000,
                quantization="Q4_K_M",
                supports_chat=True,
            ),
            ModelInfo(
                name="llama3:8b",
                size_bytes=4700000000,
                parameter_size="8B",
                is_embedding=False,
                is_loaded=False,
                context_length=4096,
                quantization=None,
                supports_chat=True,
            ),
        ]
        
        recommended = recommend_model(
            available_models=models,
            ram_gb=32.0,
            gpu_vram_gb=0.0,
            has_gpu=False,
        )
        
        # Deve ignorar Mixtral (>10B) e recomendar llama3
        assert recommended == "llama3:8b"
    
    def test_recommend_model_no_models(self):
        """Testar quando não há modelos disponíveis."""
        recommended = recommend_model(
            available_models=[],
            ram_gb=16.0,
            gpu_vram_gb=8.0,
            has_gpu=True,
        )
        
        assert recommended is None
    
    def test_recommendations_table(self):
        """Testar tabela de recomendações."""
        table = get_model_recommendations_table()
        
        assert len(table) >= 4
        assert any(row["ram"] == "8GB" for row in table)
        assert any(row["ram"] == "16GB" for row in table)
    
    def test_calculate_min_requirements(self):
        """Testar cálculo de requisitos mínimos."""
        reqs = calculate_min_requirements("8B")
        
        assert reqs["min_ram_gb"] == 12.0  # 8 * 1.5
        assert reqs["recommended_ram_gb"] == 16.0  # 8 * 2.0
        assert reqs["min_vram_gb"] == 8.0


class TestProviderFactory:
    """Testes para factory de providers."""
    
    def test_create_ollama_provider(self):
        """Testar criação de Ollama provider."""
        provider = create_provider(
            ProviderType.OLLAMA,
            {"base_url": "http://localhost:11434"},
        )
        
        assert isinstance(provider, OllamaProvider)
        assert provider.provider_name == "ollama"
    
    def test_create_unknown_provider(self):
        """Testar erro para provider desconhecido."""
        with pytest.raises(ValueError, match="Provider type desconhecido"):
            create_provider("unknown_type")  # type: ignore
    
    def test_create_vllm_provider_not_implemented(self):
        """Testar que vLLM não está implementado ainda."""
        with pytest.raises(NotImplementedError, match="vLLM provider não implementado"):
            create_provider(ProviderType.VLLM)
    
    def test_create_lmstudio_provider_not_implemented(self):
        """Testar que LM Studio não está implementado ainda."""
        with pytest.raises(NotImplementedError, match="LM Studio provider não implementado"):
            create_provider(ProviderType.LMSTUDIO)


class TestManifestoIntegration:
    """Testes para integração com manifesto."""
    
    def test_bee_capabilities_to_manifesto(self):
        """Testar conversão de capabilities para formato do manifesto."""
        hardware = HardwareCapabilities(
            os="Linux",
            os_version="22.04",
            architecture="x86_64",
            cpu_cores=8,
            cpu_logical=16,
            cpu_freq_ghz=3.2,
            ram_total_gb=16.0,
            ram_available_gb=8.5,
            gpu_available=True,
            gpu_name="NVIDIA GeForce RTX 3080",
            gpu_vram_gb=10.0,
            storage_total_gb=512.0,
            storage_free_gb=256.0,
        )
        
        ollama = OllamaCapabilities(
            available=True,
            version="0.5.4",
            base_url="http://localhost:11434",
            models=[
                ModelInfo(
                    name="llama3:8b",
                    size_bytes=4700000000,
                    parameter_size="8B",
                    is_embedding=False,
                    is_loaded=True,
                    context_length=4096,
                    quantization="Q4_K_M",
                    supports_chat=True,
                ),
                ModelInfo(
                    name="nomic-embed-text",
                    size_bytes=274000000,
                    parameter_size="80M",
                    is_embedding=True,
                    is_loaded=False,
                    context_length=512,
                    quantization=None,
                ),
            ],
            loaded_models=["llama3:8b"],
        )
        
        local = LocalCapabilities(
            embeddings_available=False,
            embeddings_model=None,
            ocr_available=True,
            rag_available=True,
            zim_available=False,
            zim_file_count=0,
            web_available=False,
        )
        
        caps = BeeCapabilities(
            hardware=hardware,
            ollama=ollama,
            local=local,
        )
        
        manifesto = caps.to_manifesto_dict()
        
        # Verificar estrutura
        assert "hardware" in manifesto
        assert "capabilities" in manifesto
        assert "models" in manifesto
        assert "ollama_version" in manifesto
        
        # Verificar valores
        assert manifesto["hardware"]["os"] == "Linux"
        assert manifesto["hardware"]["architecture"] == "x86_64"
        assert manifesto["hardware"]["cpu_cores"] == 8
        assert manifesto["hardware"]["ram_gb"] == 16.0
        assert "llm_inference" in manifesto["capabilities"]
        assert "embeddings" in manifesto["capabilities"]
        assert "ocr" in manifesto["capabilities"]
        assert "rag" in manifesto["capabilities"]
        assert "llama3:8b" in manifesto["models"]
        assert manifesto["ollama_version"] == "0.5.4"
    
    def test_bee_capabilities_without_ollama(self):
        """Testar capabilities sem Ollama."""
        hardware = HardwareCapabilities(
            os="Linux",
            os_version="22.04",
            architecture="x86_64",
            cpu_cores=4,
            cpu_logical=8,
            cpu_freq_ghz=2.5,
            ram_total_gb=8.0,
            ram_available_gb=4.0,
            gpu_available=False,
            gpu_name=None,
            gpu_vram_gb=0.0,
            storage_total_gb=256.0,
            storage_free_gb=128.0,
        )
        
        ollama = OllamaCapabilities(
            available=False,
            version=None,
            base_url="http://localhost:11434",
        )
        
        local = LocalCapabilities(
            embeddings_available=True,
            embeddings_model="sentence-transformers:all-MiniLM-L6-v2",
            ocr_available=False,
            rag_available=False,
            zim_available=False,
            zim_file_count=0,
            web_available=False,
        )
        
        caps = BeeCapabilities(
            hardware=hardware,
            ollama=ollama,
            local=local,
        )
        
        manifesto = caps.to_manifesto_dict()
        
        # Sem Ollama, não deve ter llm_inference
        assert "llm_inference" not in manifesto["capabilities"]
        assert "embeddings_local" in manifesto["capabilities"]
        assert len(manifesto["models"]) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
