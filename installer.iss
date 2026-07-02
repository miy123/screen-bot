; Inno Setup 腳本
; 安裝 Inno Setup 後對此檔案按右鍵 > Compile 即可產生安裝檔
; 下載：https://jrsoftware.org/isdl.php

#define AppName "ScreenBot"
#define AppVersion "1.0"

[Setup]
AppName={#AppName}
AppVersion={#AppVersion}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
OutputDir=installer_output
OutputBaseFilename=ScreenBot_Setup
Compression=lzma
SolidCompression=yes
; 要求管理員權限（keyboard 套件需要）
PrivilegesRequired=admin

[Files]
; exe 和相關 dll（PyInstaller 產生的整個資料夾）
Source: "dist\ScreenBot\*"; DestDir: "{app}"; Flags: recursesubdirs

; config 和圖片放在安裝目錄（使用者可編輯）
Source: "config.py";  DestDir: "{app}"; Flags: onlyifdoesntexist
Source: "images\*";   DestDir: "{app}\images"; Flags: recursesubdirs onlyifdoesntexist

[Icons]
; 開始選單
Name: "{group}\{#AppName}";        Filename: "{app}\ScreenBot.exe"
Name: "{group}\卸載 {#AppName}";   Filename: "{uninstallexe}"
; 桌面捷徑
Name: "{autodesktop}\{#AppName}";  Filename: "{app}\ScreenBot.exe"

[Run]
; 安裝完成後可選擇直接執行
Filename: "{app}\ScreenBot.exe"; \
    Description: "立即執行 {#AppName}"; \
    Flags: nowait postinstall skipifsilent runascurrentuser
