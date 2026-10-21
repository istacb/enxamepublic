#!/usr/bin/env python3
"""
Testes rápidos dos instaladores da Abelha

Executa validações básicas sem modificar o sistema.
"""

import os
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


class TestClusterOptIn(unittest.TestCase):
    """O instalador pergunta "Deseja ativar modo cluster?" — a resposta tem que valer.

    `cluster.enabled` era gravado por enable_cluster_mode e nunca lido pelo
    serviço, então responder "n" era decorativo: o enxame se formava do mesmo
    jeito. Estes testes travam os dois lados (aceitar e recusar).

    Os patches miram `install.cluster_setup`, que é onde a implementação única
    mora hoje. `universal_installer` reexporta os mesmos objetos (e os testes
    abaixo importam dele justamente para provar que o shim continua inteiro),
    mas fazer patch do alias não interceptaria a chamada interna.
    """

    def setUp(self):
        import tempfile
        self.tmp = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.tmp.name)
        self.config_file = self.data_dir / "config.json"

    def tearDown(self):
        self.tmp.cleanup()

    def _escrever_config(self, extra=None):
        import json
        base = {"node_id": "abelha-01", "port": 8765}
        if extra:
            base.update(extra)
        self.config_file.write_text(json.dumps(base), encoding="utf-8")
        return base

    def _ler(self):
        import json
        return json.loads(self.config_file.read_text(encoding="utf-8"))

    def test_enable_cluster_mode_grava_enabled_true(self):
        from install.universal_installer import enable_cluster_mode

        self._escrever_config()
        enable_cluster_mode(self.data_dir)

        self.assertTrue(self._ler()["cluster"]["enabled"])
        self.assertEqual(self._ler()["cluster"]["min_peers"], 3)

    def test_enable_preserva_outras_chaves(self):
        from install.universal_installer import enable_cluster_mode

        self._escrever_config()
        enable_cluster_mode(self.data_dir)

        self.assertEqual(self._ler()["node_id"], "abelha-01")
        self.assertEqual(self._ler()["port"], 8765)

    def test_disable_cluster_mode_grava_enabled_false(self):
        from install.universal_installer import disable_cluster_mode

        self._escrever_config({"cluster": {"enabled": True, "min_peers": 3}})
        disable_cluster_mode(self.data_dir)

        config = self._ler()
        self.assertFalse(config["cluster"]["enabled"])
        # min_peers não pode ser perdido no caminho
        self.assertEqual(config["cluster"]["min_peers"], 3)

    def test_disable_sem_config_json_nao_cria_arquivo(self):
        from install.universal_installer import disable_cluster_mode

        disable_cluster_mode(self.data_dir)  # não existe config.json

        self.assertFalse(self.config_file.exists())

    def test_optin_retorna_none_quando_nao_ha_peers(self):
        """Sem 2+ outras abelhas não há o que perguntar — e nada deve ser gravado."""
        from install.universal_installer import prompt_cluster_optin

        with patch("install.cluster_setup.discover_local_peers", return_value=[]):
            resposta = prompt_cluster_optin(self.data_dir, auto=False)

        self.assertIsNone(resposta)

    def test_optin_retorna_true_em_modo_auto_com_peers(self):
        from install.universal_installer import prompt_cluster_optin

        peers = [
            {"node_id": "abelha-02", "role": "bee", "host": "h", "port": 1, "capabilities": []},
            {"node_id": "abelha-03", "role": "bee", "host": "h", "port": 2, "capabilities": []},
        ]
        with patch("install.cluster_setup.discover_local_peers", return_value=peers):
            resposta = prompt_cluster_optin(self.data_dir, auto=True)

        self.assertTrue(resposta)

    def test_optin_retorna_false_quando_usuario_recusa(self):
        from install.universal_installer import prompt_cluster_optin

        peers = [
            {"node_id": "abelha-02", "role": "bee", "host": "h", "port": 1, "capabilities": []},
            {"node_id": "abelha-03", "role": "bee", "host": "h", "port": 2, "capabilities": []},
        ]
        with patch("install.cluster_setup.discover_local_peers", return_value=peers), \
             patch("builtins.input", return_value="n"):
            resposta = prompt_cluster_optin(self.data_dir, auto=False, confirmar=lambda _: "n")

        self.assertFalse(resposta)

    def test_optin_ignora_peers_que_nao_sao_abelhas(self):
        """Só conta role == "bee"; outro serviço na rede não forma enxame."""
        from install.universal_installer import prompt_cluster_optin

        peers = [
            {"node_id": "juiz-x", "role": "juiz", "host": "h", "port": 1, "capabilities": []},
            {"node_id": "impressora", "role": "printer", "host": "h", "port": 2, "capabilities": []},
        ]
        with patch("install.cluster_setup.discover_local_peers", return_value=peers):
            resposta = prompt_cluster_optin(self.data_dir, auto=True)

        self.assertIsNone(resposta)


class TestInstaladorUnico(unittest.TestCase):
    """Existe UM instalador. Os outros arquivos são shim ou biblioteca.

    Eram 22 arquivos de instalação e 5 comandos documentados diferentes
    apontando para 3 stacks. Este teste impede que volte a existir um segundo
    caminho: qualquer "instalador" executável precisa delegar para
    bees/install/bee_installer.py.
    """

    def setUp(self):
        self.install_dir = Path(__file__).resolve().parent
        self.repo_root = self.install_dir.parents[1]

    def test_shim_universal_reexporta_os_mesmos_objetos(self):
        from install import cluster_setup, universal_installer

        for nome in ("enable_cluster_mode", "disable_cluster_mode",
                     "prompt_cluster_optin", "discover_local_peers",
                     "write_bee_config", "set_node_id"):
            self.assertIs(
                getattr(universal_installer, nome), getattr(cluster_setup, nome),
                f"{nome} não é o mesmo objeto: existe uma segunda implementação",
            )

    def test_instalacao_raiz_delega_para_bee_installer(self):
        shim = self.repo_root / "install-bee-smart.py"
        self.assertTrue(shim.exists(), "o comando documentado sumiu da raiz")
        texto = shim.read_text(encoding="utf-8")
        self.assertIn("bees.install.bee_installer", texto)

    def test_install_bee_nao_e_segundo_caminho(self):
        texto = (self.install_dir / "install_bee.py").read_text(encoding="utf-8")
        # O __main__ precisa delegar, não rodar um fluxo próprio de instalação.
        bloco = texto.split('if __name__ == "__main__":', 1)[1]
        self.assertIn("bee_installer", bloco)

    def test_scripts_por_so_concorrentes_foram_removidos(self):
        for nome in ("install-bee.sh", "install_debian.sh", "install_arch.sh",
                     "install_macos.sh", "install_unix.sh", "install_windows.bat",
                     "install_enxame.py"):
            self.assertFalse(
                (self.install_dir / nome).exists(),
                f"{nome} voltou a existir: dois caminhos de instalação de novo",
            )


class TestDataDirCompartilhado(unittest.TestCase):
    """O instalador tem que escrever onde o serviço lê.

    Bug real: o instalador usava ~/enxame/data enquanto `load_config` lia
    <data_dir>/config.json do diretório padrão da plataforma. A configuração
    gravada nunca era lida — o mesmo padrão de "escreveu mas ninguém lê" que
    fez cluster.enabled ser decorativo.
    """

    def test_default_bate_com_bees_config(self):
        from install.cluster_setup import default_data_dir

        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        from bees.config import get_default_data_dir

        self.assertEqual(Path(default_data_dir()), Path(get_default_data_dir()))

    def test_resolve_respeita_explicito_e_env(self):
        from install.cluster_setup import resolve_data_dir

        self.assertEqual(resolve_data_dir("/tmp/abelha-x"), Path("/tmp/abelha-x"))
        with patch.dict(os.environ, {"BEE_DATA_DIR": "/tmp/abelha-env"}):
            self.assertEqual(resolve_data_dir(None), Path("/tmp/abelha-env"))
        # explícito vence a variável de ambiente, como em load_config
        with patch.dict(os.environ, {"BEE_DATA_DIR": "/tmp/abelha-env"}):
            self.assertEqual(resolve_data_dir("/tmp/abelha-cli"), Path("/tmp/abelha-cli"))


class TestConfiguracaoDaAbelha(unittest.TestCase):
    """configure_bee() é o que a etapa final do instalador realmente grava."""

    def setUp(self):
        import tempfile
        self.tmp = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _ler(self, nome="config.json"):
        import json
        return json.loads((self.data_dir / nome).read_text(encoding="utf-8"))

    def _configurar(self, **kw):
        from install.bee_setup import configure_bee
        padrao = dict(
            data_dir=self.data_dir, port=8765,
            ollama_url="http://localhost:11434", model="llama3.2:3b",
            cluster=True, log_info=lambda m: None, log_warn=lambda m: None,
        )
        padrao.update(kw)
        return configure_bee(**padrao)

    def test_grava_os_campos_que_o_servico_le(self):
        self._configurar()
        config = self._ler()
        self.assertEqual(config["port"], 8765)
        self.assertEqual(config["model"], "llama3.2:3b")
        self.assertEqual(config["ollama_base_url"], "http://localhost:11434")
        self.assertTrue(config["cluster"]["enabled"])

    def test_node_id_explicito_vai_para_identity_json(self):
        """`_load_identity()` sobrescreve o nome com o de identity.json.

        Gravar só em config.json seria decorativo — o serviço usaria outro nome.
        """
        self._configurar(node_id="abelha-07")
        self.assertEqual(self._ler("identity.json")["node_id"], "abelha-07")
        self.assertEqual(self._ler()["node_id"], "abelha-07")

    def test_primeira_instalacao_fixa_nome_estavel(self):
        """Sem isto o node_id é um uuid4 NOVO a cada boot.

        Observado em instalação real: a abelha subiu como
        "bb5c32e7-7e80-4d5d-..." e, como a eleição desempata por node_id, os
        papéis do enxame mudariam a cada reinício da máquina.
        """
        resumo = self._configurar()
        self.assertFalse(resumo["node_id"].count("-") == 4,
                         "node_id voltou a ser um uuid4")
        self.assertTrue((self.data_dir / "identity.json").exists())

    def test_reinstalar_nao_troca_o_nome(self):
        primeiro = self._configurar(node_id="abelha-07")
        segundo = self._configurar()  # sem --node-id
        self.assertEqual(primeiro["node_id"], "abelha-07")
        self.assertEqual(segundo["node_id"], "abelha-07")

    def test_reinstalar_preserva_configuracao_do_usuario(self):
        self._configurar()
        import json
        config = self._ler()
        config["max_concurrent_queries"] = 9
        (self.data_dir / "config.json").write_text(json.dumps(config), encoding="utf-8")

        self._configurar(model="phi3:mini")
        novo = self._ler()
        self.assertEqual(novo["model"], "phi3:mini")
        self.assertEqual(novo["max_concurrent_queries"], 9,
                         "reinstalar apagou uma chave que o usuário ajustou")

    def test_no_cluster_grava_recusa(self):
        resumo = self._configurar(cluster=False)
        self.assertFalse(self._ler()["cluster"]["enabled"])
        self.assertIs(resumo["cluster"], False)

    def test_sem_decisao_nao_grava_nada_de_cluster(self):
        """Não ter o que perguntar não é o mesmo que recusar.

        Recusar precisa gravar cluster.enabled=false; não ter perguntado não
        pode gravar nada, porque o enxame pode se formar depois quando outras
        abelhas aparecerem na rede.
        """
        with patch("install.cluster_setup.discover_local_peers", return_value=[]):
            resumo = self._configurar(cluster=None)
        self.assertIsNone(resumo["cluster"])
        self.assertNotIn("cluster", self._ler())

    def test_dry_run_nao_grava_nada(self):
        resumo = self._configurar(dry_run=True)
        self.assertFalse((self.data_dir / "config.json").exists())
        self.assertFalse((self.data_dir / "identity.json").exists())
        self.assertEqual(resumo["port"], 8765)


class TestComandoDeSubida(unittest.TestCase):
    """O comando que o instalador ensina tem que ser o que funciona."""

    def test_usa_modulo_e_nao_caminho(self):
        from install.bee_setup import bee_start_command

        cmd = bee_start_command("/venv/bin/python", "/dados", 8765,
                                "http://localhost:11434", "llama3.2:3b", "/repo")
        self.assertIn("-m", cmd)
        self.assertIn("bees.service", cmd)
        self.assertNotIn("bees/service.py", cmd,
                         "python bees/service.py falha: imports relativos + core")
        self.assertIn("--data-dir", cmd)
        self.assertIn("/dados", cmd)

    def test_dry_run_nao_cria_atalho_nem_servico(self):
        from install.bee_setup import create_bee_shortcuts, install_bee_service
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            kw = dict(venv_py="/venv/bin/python", data_dir=tmp, port=8765,
                      ollama_url="http://localhost:11434", model="m",
                      repo_root="/repo", dry_run=True,
                      log_info=lambda m: None, log_warn=lambda m: None)
            self.assertEqual(create_bee_shortcuts(**kw), [])
            servico = install_bee_service(**kw)
            self.assertIsNone(servico["criado"])
            self.assertFalse(servico["ativo"])


class TestParseDeCapacidades(unittest.TestCase):
    """A abelha anuncia capabilities como JSON; tratar como CSV imprimia lixo."""

    def test_json_array(self):
        from install.cluster_setup import _parse_lista
        self.assertEqual(_parse_lista('["rag", "index"]'), ["rag", "index"])

    def test_csv_como_fallback(self):
        from install.cluster_setup import _parse_lista
        self.assertEqual(_parse_lista("rag,index"), ["rag", "index"])

    def test_lista_e_vazio(self):
        from install.cluster_setup import _parse_lista
        self.assertEqual(_parse_lista(["rag"]), ["rag"])
        self.assertEqual(_parse_lista(""), [])
        self.assertEqual(_parse_lista(None), [])


class TestWebUiNaRaiz(unittest.TestCase):
    """A URL que o instalador manda abrir precisa mostrar a interface.

    O add_static do aiohttp NÃO serve index.html: para diretório ele devolve a
    listagem (show_index=True) ou 403 (show_index=False). Com show_index=True —
    o que estava no código — http://localhost:8765/ mostrava "Index of /." com
    links para app.js e style.css em vez do painel. Trava-se aqui a regressão
    por inspeção do código-fonte porque reproduzir o servidor inteiro num teste
    unitário exigiria Ollama e rede.
    """

    def setUp(self):
        self.servico = Path(__file__).resolve().parents[1] / "service.py"
        self.codigo = self.servico.read_text(encoding="utf-8")

    def test_nao_habilita_listagem_de_diretorio(self):
        # O literal exato da chamada: o comentário explicativo ao lado menciona
        # "show_index=True" para dizer o que NÃO fazer, então procurar a
        # substring solta daria falso positivo.
        self.assertNotIn("add_static('/', web_dir, show_index=True)", self.codigo)
        self.assertIn("show_index=False", self.codigo)

    def test_tem_rota_explicita_para_a_raiz(self):
        self.assertIn("add_get('/', _serve_index)", self.codigo)
        self.assertIn("FileResponse(index_file)", self.codigo)

    def test_rota_da_raiz_vem_antes_do_mount_estatico(self):
        pos_rota = self.codigo.index("add_get('/', _serve_index)")
        pos_static = self.codigo.index("add_static('/', web_dir")
        self.assertLess(pos_rota, pos_static,
                        "o mount estático em '/' sombrearia a rota do index")


class TestOllamaVerificado(unittest.TestCase):
    """Instalar o Ollama não é o mesmo que ele estar atendendo.

    Antes desta correção, todos os ramos de instalação (winget no Windows,
    Homebrew no macOS, curl no Debian, pacman no Arch) devolviam a URL fixa
    "http://localhost:11434" com a lista de modelos VAZIA, sem nunca conferir se
    a API HTTP respondia. main() só testava `if not ollama_url`, que é verdade
    para uma string não vazia — então o instalador seguia para o PASSO 4,
    terminava com "Abelha instalada e configurada!" e o usuário ficava com uma
    abelha sem modelo nenhum. Estes testes travam os dois lados do contrato.
    """

    def test_wait_retorna_true_assim_que_responde(self):
        from install.bee_installer import wait_ollama_ready

        with patch("install.bee_installer.is_ollama_running", return_value=True):
            self.assertTrue(wait_ollama_ready(timeout=5))

    def test_wait_retorna_false_quando_nunca_responde(self):
        from install.bee_installer import wait_ollama_ready

        with patch("install.bee_installer.is_ollama_running", return_value=False), \
             patch("install.bee_installer.time.sleep", lambda *_: None):
            self.assertFalse(wait_ollama_ready(timeout=1))

    def test_ollama_verificado_eh_honesto_quando_nao_responde(self):
        """O contrato que importa: sem resposta, devolve (None, []) — nunca uma
        URL de mentirinha que faria main() seguir em frente."""
        from install.bee_installer import ollama_verificado

        with patch("install.bee_installer.wait_ollama_ready", return_value=False):
            url, modelos = ollama_verificado()

        self.assertIsNone(url, "URL não verificada vazaria como sucesso")
        self.assertEqual(modelos, [])

    def test_ollama_verificado_redetecta_os_modelos_reais(self):
        """Quando responde, precisa devolver os modelos DE VERDADE — o ramo de
        instalação tinha [] em mãos, e o PASSO 4 usa essa lista para não baixar
        um modelo que já existe."""
        from install.bee_installer import ollama_verificado

        deteccao = {"url": "http://localhost:11434",
                    "models": ["llama3.2:3b", "qwen2.5:0.5b"]}
        with patch("install.bee_installer.wait_ollama_ready", return_value=True), \
             patch("install.bee_installer.detect_ollama", return_value=deteccao):
            url, modelos = ollama_verificado()

        self.assertEqual(url, "http://localhost:11434")
        self.assertEqual(modelos, ["llama3.2:3b", "qwen2.5:0.5b"])

    def test_nenhum_ramo_devolve_url_fixa_sem_verificar(self):
        """Trava a regressão no código-fonte: o padrão de falso sucesso não pode
        voltar em nenhum dos quatro ramos de instalação."""
        codigo = (Path(__file__).parent / "bee_installer.py").read_text(encoding="utf-8")
        self.assertNotIn('return "http://localhost:11434", []', codigo,
                         "ramo de instalação devolvendo URL sem verificar")
        self.assertNotIn("return url, []", codigo,
                         "ramo de instalação devolvendo URL sem verificar")

    def test_main_trata_none_como_falha(self):
        """O que torna a honestidade efetiva: main() encerra quando vem None."""
        codigo = (Path(__file__).parent / "bee_installer.py").read_text(encoding="utf-8")
        self.assertIn("ollama_url, existing_models = install_ollama_if_needed()", codigo)
        self.assertIn("if not ollama_url:", codigo)
        pos_saida = codigo.index("Não foi possível instalar/verificar o Ollama")
        self.assertGreater(pos_saida, codigo.index("if not ollama_url:"))



class TestModelAvailability(unittest.TestCase):
    """`ollama pull` sair 0 não é prova de que o modelo ficou disponível.

    pull_model() devolvia True assim que o subprocesso terminava sem erro, e
    main() fazia `if pull_model(...)` SEM else — então um download fracassado
    (disco cheio, tag inexistente, daemon que caiu no meio) seguia em silêncio
    até o PASSO 7, que imprimia "Abelha instalada e configurada!" com o nome do
    modelo. A abelha subia sem LLM e não respondia nada: o relato original de
    "instalei e nada funciona".
    """

    def test_reconhece_com_e_sem_tag(self):
        from install.bee_installer import model_available

        self.assertTrue(model_available("llama3.2:3b", ["llama3.2:3b"]))
        self.assertTrue(model_available("llama3.2", ["llama3.2:3b"]),
                        "config pode guardar o nome sem a tag")
        self.assertTrue(model_available("LLAMA3.2:3B", ["llama3.2:3b"]))

    def test_modelo_desconhecido_retorna_false(self):
        from install.bee_installer import model_available

        self.assertFalse(model_available("phi3:2.7b", ["llama3.2:3b"]))
        self.assertFalse(model_available("", []))
        self.assertFalse(model_available("x", None))

    def test_pull_ja_presente_nao_baixa_de_novo(self):
        from install.bee_installer import pull_model

        def explodir(*a, **k):
            raise AssertionError("não deveria chamar subprocesso com o modelo já presente")

        with patch("install.bee_installer.subprocess.run", explodir):
            self.assertTrue(pull_model("llama3.2:3b", ["llama3.2:3b"]))

    def test_pull_que_sai_zero_sem_modelo_eh_falha(self):
        """O caso que passava como sucesso: returncode 0, modelo ausente."""
        from install.bee_installer import pull_model

        falso_sucesso = MagicMock(returncode=0)
        with patch("install.bee_installer.subprocess.run", return_value=falso_sucesso), \
             patch("install.bee_installer.detect_ollama", return_value={"models": []}):
            self.assertFalse(pull_model("phi3:2.7b", []),
                             "pull saiu 0 mas o modelo não está em 'ollama list'")

    def test_pull_confirmado_na_lista_eh_sucesso(self):
        from install.bee_installer import pull_model

        ok = MagicMock(returncode=0)
        with patch("install.bee_installer.subprocess.run", return_value=ok), \
             patch("install.bee_installer.detect_ollama",
                   return_value={"models": ["phi3:2.7b"]}):
            self.assertTrue(pull_model("phi3:2.7b", []))

    def test_passo_7_diz_a_verdade_sobre_o_modelo(self):
        """O resumo final tem que refletir o estado real, não o nome escolhido."""
        codigo = (Path(__file__).parent / "bee_installer.py").read_text(encoding="utf-8")
        self.assertIn("if modelo_ok:", codigo)
        self.assertIn("NÃO disponível no Ollama", codigo)
        self.assertIn("Abelha instalada, mas INCOMPLETA", codigo)

    def test_falha_de_download_sai_com_codigo_1(self):
        """Download TENTADO e fracassado = instalação incompleta = exit 1.
        --skip-model é escolha de quem chamou, então permanece aviso/exit 0."""
        codigo = (Path(__file__).parent / "bee_installer.py").read_text(encoding="utf-8")
        self.assertIn("if not modelo_ok and not args.skip_model:", codigo)
        pos_erro = codigo.index("Instalação INCOMPLETA: o modelo não foi baixado")
        pos_saida = codigo.index("sys.exit(1)", pos_erro)
        self.assertGreater(pos_saida, pos_erro)



if __name__ == '__main__':
    print("="*60)
    print("🐝 TESTES DOS INSTALADORES DA ABELHA")
    print("="*60)
    print()
    
    # Executar testes
    unittest.main(verbosity=2)
