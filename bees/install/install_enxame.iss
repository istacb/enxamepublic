; ENXAME Bee - Windows Installer (Inno Setup)
; Compile with: iscc install_enxame.iss
; Requires Inno Setup 6+

#define MyAppName "ENXAME Bee"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Enxame Project"
#define MyAppURL "https://github.com/enxame/enxamepublic"
#define MyAppExeName "bee.exe"

[Setup]
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\ENXAME Bee
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
LicenseFile=LICENSE.txt
OutputDir=..\dist
OutputBaseFilename=enxame-bee-setup-{#MyAppVersion}
SetupIconFile=bee.ico
Compression=lzma
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64
ArchitecturesAllowed=x64
PrivilegesRequired=admin
RestartIfNeededByRun=always

[Languages]
Name: "portuguese"; MessagesFile: "compiler:Languages\Portuguese.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "startollama"; Description: "Iniciar Ollama automaticamente"; GroupDescription: "Ollama"; Flags: checkedonce
Name: "autostart"; Description: "Iniciar Abelha no boot do Windows"; GroupDescription: "Inicialização"; Flags: unchecked

[Files]
Source: "..\..\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "*.pyc;__pycache__;*.git*;dist;build;*.iss;*.md;LICENSE*"
Source: "bee.ico"; DestDir: "{app}"; Flags: ignoreversion
Source: "LICENSE.txt"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\bee.exe"; WorkingDir: "{app}"
Name: "{commondesktop}\{#MyAppName}"; Filename: "{app}\bee.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\install_ollama.bat"; Description: "Instalar Ollama"; Flags: runhidden waituntilterminated; StatusMsg: "Instalando Ollama..."; Check: not IsOllamaInstalled()
Filename: "{app}\start_ollama.bat"; Description: "Iniciar Ollama"; Flags: runhidden waituntilterminated; StatusMsg: "Iniciando Ollama..."; Check: IsOllamaInstalled() and not IsOllamaRunning() and IsTaskSelected('startollama')
Filename: "{app}\bee.exe"; Parameters: "start"; Description: "Iniciar Abelha agora"; Flags: postinstall nowait shellexec; Check: IsOllamaRunning()

[UninstallDelete]
Type: filesandordirs; Name: "{app}"

[Code]
var
  OllamaPath: String;

function IsOllamaInstalled(): Boolean;
begin
  Result := FileExists(ExpandConstant('{pf}\Ollama\ollama.exe')) or 
            FileExists(ExpandConstant('{localappdata}\Programs\Ollama\ollama.exe'));
end;

function IsOllamaRunning(): Boolean;
var
  ResultCode: Integer;
begin
  Result := Exec('cmd.exe', '/c ollama list', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Result := Result and (ResultCode = 0);
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  if CurPageID = wpReady then
  begin
    { Verificar se Ollama está instalado antes de prosseguir }
    if not IsOllamaInstalled() then
    begin
      if MsgBox('Ollama não foi detectado. Deseja instalar agora?', mbConfirmation, MB_YESNO) = IDYES then
      begin
        { Instalar Ollama silenciosamente }
        Exec('cmd.exe', '/c curl -fsSL https://ollama.com/install.sh | sh', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
      end
      else
      begin
        Result := False; { Cancelar instalação }
        Exit;
      end;
    end;
  end;
  Result := True;
end;

procedure InitializeWizard();
begin
  { Verificar Python }
  if not FileExists(ExpandConstant('{pf}\Python312\python.exe')) and
     not FileExists(ExpandConstant('{pf}\Python311\python.exe')) and
     not FileExists(ExpandConstant('{pf}\Python310\python.exe')) then
  begin
    MsgBox('Python 3.10+ não encontrado. Por favor, instale Python de python.org antes de continuar.', mbError, MB_OK);
  end;
end;