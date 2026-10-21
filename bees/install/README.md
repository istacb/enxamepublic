# Instalação da Abelha

Existe **um** instalador. Ele é a implementação única e todos os outros nomes
deste diretório delegam para ele ou são ferramentas de quem empacota o projeto.

## O comando

```bash
git clone https://github.com/istacb/enxamepublic.git
cd enxamepublic

python3 install-bee-smart.py --auto
```

Windows: `py install-bee-smart.py --auto`. macOS, Debian, Ubuntu e Arch: o mesmo
comando.

Ele faz, nesta ordem:

1. Confere o Python (3.10+) e instala se faltar.
2. Confere o Ollama pela **API HTTP** e instala se faltar (winget no Windows,
   brew no macOS, apt/pacman/script oficial no Linux).
3. Detecta RAM e GPU.
4. Recomenda um modelo para esse hardware e baixa (`ollama pull`).
5. Cria o `.venv-bee` e instala as 13 dependências — incluindo `aiohttp` e
   `cryptography`, sem as quais o serviço nem importa.
6. Grava `<data-dir>/config.json` e `identity.json`, e pergunta se esta máquina
   entra no enxame quando encontra outras abelhas na rede.
7. Imprime os dois comandos para subir a abelha e a URL da interface.

Para ver o que ele faria sem alterar nada:

```bash
python3 install-bee-smart.py --dry-run
```

## Depois de instalar

```bash
cd /caminho/para/enxamepublic
.venv-bee/bin/python -m bees.service --host 0.0.0.0 --port 8765 --data-dir <data-dir>
```

Abra **http://localhost:8765/**. A abelha serve `web/` na raiz e a mesma API que
o enxame usa (`/api/session`, `/api/chat`, `/api/status`, `/api/cluster/*`,
`/api/guardian`). Para parar, `Ctrl+C`.

> `python bees/service.py` não funciona: imports relativos + `core` exigem
> executar como módulo a partir da raiz do repositório.

## Flags

| Flag | Efeito |
|------|--------|
| `--auto` | Nenhuma pergunta |
| `--dry-run` | Só detecta e mostra o plano |
| `--data-dir CAMINHO` | Dados da abelha (padrão = o mesmo que o serviço usa) |
| `--node-id NOME` | Nome da abelha, gravado de forma estável |
| `--bee-port PORTA` | Porta HTTP/UI (padrão 8765) |
| `--cluster` / `--no-cluster` | Entra ou não no enxame, sem perguntar |
| `--install-service` | Serviço do usuário: systemd `--user`, LaunchAgent, tarefa de logon |
| `--no-shortcuts` | Não cria atalho de inicialização |
| `--model NOME` / `--skip-model` | Força modelo / não baixa modelo |
| `--ollama-url URL` | Usa Ollama remoto |
| `--uninstall` | Remove o que o instalador criou |
| `--legacy-env` | Também gera `.env` para a stack antiga |

## Enxame

Rode o mesmo comando em 3+ máquinas na mesma rede local. As abelhas se descobrem
por mDNS e elegem os papéis entre si (Juiz, Bibliotecária, Guarda, Workers). O
Juiz recebe a pergunta, descobre qual abelha tem o conhecimento offline, delega e
faz a curadoria da resposta. Cada abelha mantém o próprio RAG. mDNS é link-local:
VPN e sub-redes diferentes não se descobrem.

## O que há neste diretório

**Instalador (o caminho do usuário)**

| Arquivo | Papel |
|---------|-------|
| `bee_installer.py` | **A implementação única.** 7 passos, cross-platform. |
| `cluster_setup.py` | `config.json`/`identity.json`, opt-in de enxame, descoberta mDNS. |
| `bee_setup.py` | Etapa final: comando de subida, atalhos, serviço do usuário. |
| `test_installers.py` | Testes dos três acima. |

**Atalhos que delegam para `bee_installer.py`** (existem para não quebrar quem
já usa esses nomes, e para o empacotamento)

| Arquivo | Papel |
|---------|-------|
| `../../install-bee-smart.py` | Comando documentado, na raiz do repositório. |
| `universal_installer.py` | Entry point do PyInstaller (`.app`/`.dmg`) e do AppImage. |
| `install_bee.py` | Biblioteca de helpers puros + gerador de manifesto. |
| `uninstall_bee.py` | Remoção (`install-bee-smart.py --uninstall`). |

**Empacotamento (só para quem mantém o projeto)** — veja
[`README_INSTALLERS.md`](README_INSTALLERS.md).

| Arquivo | Papel |
|---------|-------|
| `build_installer.py` | Gera `.dmg` (macOS) e AppImage (Linux). |
| `build_deb.sh`, `build_macos_pkg.sh`, `PKGBUILD` | Pacotes `.deb`, `.pkg`, Arch. |
| `enxame_installer.spec`, `version_info.txt` | Metadados do PyInstaller. |
| `install_enxame.{sh,ps1,bat,iss}`, `uninstall_enxame.{ps1,bat}` | Usados pelos pacotes acima. |
| `enxame-bee.{service,install,sysusers,tmpfiles}`, `config.json.example` | Arquivos de pacote de distro. |

## Removidos

`install-bee.sh`, `install_debian.sh`, `install_arch.sh`, `install_macos.sh`,
`install_unix.sh`, `install_windows.bat`, `install_enxame.py` e os
`uninstall_*.sh` correspondentes foram **removidos**: eram caminhos concorrentes
que instalavam coisas diferentes. Havia 22 arquivos de instalação e 5 comandos
documentados apontando para 3 stacks — era daí que vinha o "instalei e nada
funciona".

A stack antiga (`api/install/`, processos FastAPI separados na porta 7700) segue
no repositório, mas não é caminho de instalação. Veja
[`../../api/install/README.md`](../../api/install/README.md).
