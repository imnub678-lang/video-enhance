; Video Enhance - NVIDIA Edition installer
; Build order: pyinstaller video_enhance.spec, then ISCC setup_nvidia.iss

#define MyAppName "Video Enhance (NVIDIA Edition)"
#define MyVersion "1.0.0"
#define MyPublisher "VideoEnhance"
#define MyAppId "{{14462F19-9685-4C58-85DB-89EF9F872516}}"
#define MyDirName "VideoEnhance NVIDIA"
#define MyBundle "..\dist\VideoEnhance"

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
OutputBaseFilename=VideoEnhance_NVIDIA_v{#MyVersion}_setup
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
Name: "{autoprograms}\Video Enhance (NVIDIA)"; Filename: "{app}\VideoEnhance.exe"
Name: "{autodesktop}\Video Enhance (NVIDIA)"; Filename: "{app}\VideoEnhance.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\VideoEnhance.exe"; Description: "Launch Video Enhance now"; Flags: nowait postinstall skipifsilent
