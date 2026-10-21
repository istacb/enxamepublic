# Empacotamento do instalador (manutenção)

⚠️ **Esta página não é o guia de instalação do usuário.** Ela descreve como
*quem mantém o projeto* gera pacotes distribuíveis (`.dmg`, AppImage, `.deb`,
`.pkg`, pacote Arch, `.exe` do Windows).

Para instalar o ENXAME numa máquina, veja [`README.md`](README.md) — é um
comando só:

```bash
python3 install-bee-smart.py --auto
```

## Por que existe esta página

Todos os pacotes abaixo empacotam **o mesmo** instalador único
(`bee_installer.py`, através do entry point `universal_installer.py`). Antes
havia instaladores de sistema operacional separados e independentes
(`install_debian.sh`, `install_arch.sh`, `install_macos.sh`, `install_unix.sh`,
`install_windows.bat`, `install-bee.sh`, `install_enxame.py`), cada um com a sua
própria ideia do que instalar. Eles foram **removidos**: era daí que vinha o
"instalei e nada funciona", porque o resultado dependia de qual comando a pessoa
tinha seguido.

## Entry point empacotado

`universal_installer.py` é o script que o PyInstaller e o AppImage executam. Ele
não tem lógica própria: reexporta os helpers de `cluster_setup.py`/`bee_setup.py`
e delega o `main()` para `bee_installer.py`. Portanto qualquer pacote gerado aqui
roda exatamente o mesmo fluxo dos 7 passos, e uma correção vale para todos.

## Ferramentas

| Arquivo | O que faz | Onde roda |
|---------|-----------|-----------|
| `build_installer.py` | Orquestrador: chama PyInstaller/AppImage e monta os pacotes | macOS (`.dmg`), Linux (AppImage), Windows (`.exe`) |
| `enxame_installer.spec` | Spec do PyInstaller (Windows `.exe`) | Windows |
| `build_macos_pkg.sh` | Gera `.pkg` assinável para macOS | macOS |
| `build_deb.sh` | Gera `.deb` para Debian/Ubuntu | Debian/Ubuntu |
| `PKGBUILD` | Pacote Arch (AUR/makepkg) | Arch |
| `version_info.txt` | Metadados de versão do `.exe` (PyInstaller) | Windows |
| `enxame.icns` | Ícone do `.app` | macOS |

### Arquivos consumidos pelos pacotes

| Arquivo | Consumido por |
|---------|---------------|
| `install_enxame.sh` | `build_installer.py`; por dentro chama `python3 -m bees.install.install_bee`, que delega ao instalador único |
| `install_enxame.ps1` | `build_installer.py` (Windows); chama `install_enxame.bat` |
| `install_enxame.bat` | `install_enxame.ps1` |
| `install_enxame.iss` | Inno Setup (instalador Windows com assistente) |
| `uninstall_enxame.ps1` / `uninstall_enxame.bat` | Remoção do pacote Windows |
| `enxame-bee.service` | Pacote de distro: unidade systemd **de sistema** |
| `enxame-bee.install`, `enxame-bee.sysusers`, `enxame-bee.tmpfiles` | Pacote Arch |
| `config.json.example` | Modelo de `<data-dir>/config.json` |

> A unidade de sistema acima é diferente do que `--install-service` cria. O
> instalador grava uma unidade **de usuário** (`~/.config/systemd/user/`), com
> `WorkingDirectory` apontando para o repositório, porque `-m bees.service` só
> importa com o repo como diretório de trabalho.

## Como gerar

```bash
cd bees/install

python3 build_installer.py            # detecta o SO e gera o pacote possível aqui
bash build_deb.sh                     # .deb   (só em Debian/Ubuntu)
bash build_macos_pkg.sh               # .pkg   (só em macOS)
makepkg -f PKGBUILD                   # Arch   (só em Arch)
```

Saída em `bees/install/dist/` (gitignored).

Requisitos: PyInstaller (`pip install pyinstaller`) para Windows/macOS, e
`appimagetool` para o AppImage — `build_installer.py` baixa este último
automaticamente.

## Estado de verificação

Os pacotes desta página **não foram gerados nem testados** no trabalho que
unificou o instalador. O que foi verificado de ponta a ponta, em execução real:

- `python3 install-bee-smart.py --dry-run` — detecta e mostra o plano sem gravar.
- `python3 install-bee-smart.py --auto` — criou `.venv-bee`, instalou as 13
  dependências, gravou `config.json`/`identity.json`, detectou abelhas na rede e
  imprimiu os comandos finais.
- O comando impresso subiu a abelha, que serviu `web/` em `/`, respondeu à API do
  UI e entrou num enxame existente com papéis eleitos.
- `--install-service` gerou a unidade systemd correta e **reportou a falha** de
  ativação em ambiente sem bus de usuário, em vez de fingir sucesso.

Se você gerar um pacote e ele quebrar, o lugar para corrigir é
`bee_installer.py` — não uma cópia por sistema operacional.
