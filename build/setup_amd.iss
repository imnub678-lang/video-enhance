; Video Enhance - AMD Edition installer
; Build order: build the ROCm torch bundle into dist\VideoEnhance-AMD, then ISCC setup_amd.iss
; The NVIDIA and AMD bundles must NOT share an install directory or AppId.

#define MyAppName "Video Enhance (AMD Edition)"
#define MyVersion "1.0.0"
#define MyPublisher "VideoEnhance"
#define MyAppId "{{4EDC1202-931A-4646-A848-064C114C1FE2}}"
#define MyDirName "VideoEnhance AMD"
#define MyBundle "..\dist\VideoEnhance-AMD"

[Setup]
AppId={#MyAppId}
AppName={#MyAppName}
AppVersion={#MyVersion}
AppPublisher={#MyPublisher}
AppPublisherURL=https://github.com/xinntao/Real-ESRGAN
DefaultDirName={userpf}\{#MyDirName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
UninstallDisplayName={#MyAppName}
OutputDir=..\dist\installers
OutputBaseFilename=VideoEnhance_AMD_v{#MyVersion}_setup
SetupIconFile=..\build\app.ico
Compression=lzma2/fast
SolidCompression=yes
WizardStyle=modern
MinVersion=10.0

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Files]
Source: "{#MyBundle}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Video Enhance (AMD)"; Filename: "{app}\VideoEnhance.exe"
Name: "{autodesktop}\Video Enhance (AMD)"; Filename: "{app}\VideoEnhance.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\VideoEnhance.exe"; Description: "Launch Video Enhance now"; Flags: nowait postinstall skipifsilent
