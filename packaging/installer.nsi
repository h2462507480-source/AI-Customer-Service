Unicode True
!include "MUI2.nsh"

!ifndef SOURCE_DIR
  !define SOURCE_DIR "..\dist"
!endif
!ifndef OUTPUT_DIR
  !define OUTPUT_DIR "..\release"
!endif
!ifndef APP_VERSION
  !define APP_VERSION "0.4.0"
!endif
!ifndef APP_VERSION_NUM
  !define APP_VERSION_NUM "0.4.0.0"
!endif

!define APP_NAME "AI客服助手"
!define APP_EXE "AI-Customer-Service.exe"
!define APP_REG_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\AI-Customer-Service"

Name "${APP_NAME}"
OutFile "${OUTPUT_DIR}\AI-Customer-Service-Setup.exe"
InstallDir "$LOCALAPPDATA\Programs\AI Customer Service"
InstallDirRegKey HKCU "${APP_REG_KEY}" "InstallLocation"
RequestExecutionLevel user
SetCompressor /SOLID lzma
VIProductVersion "${APP_VERSION_NUM}"
VIAddVersionKey /LANG=2052 "ProductName" "${APP_NAME}"
VIAddVersionKey /LANG=2052 "ProductVersion" "${APP_VERSION}"
VIAddVersionKey /LANG=2052 "FileDescription" "${APP_NAME} 安装程序"
VIAddVersionKey /LANG=2052 "FileVersion" "${APP_VERSION}"
VIAddVersionKey /LANG=2052 "LegalCopyright" "Copyright 2026 AI Customer Service"

!define MUI_ABORTWARNING
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_COMPONENTS
!insertmacro MUI_PAGE_INSTFILES
!define MUI_FINISHPAGE_RUN "$INSTDIR\${APP_EXE}"
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "SimpChinese"

Section "AI客服助手（必需）" SecCore
  SectionIn RO
  SetOutPath "$INSTDIR"
  File "${SOURCE_DIR}\${APP_EXE}"
  WriteUninstaller "$INSTDIR\Uninstall.exe"

  CreateDirectory "$SMPROGRAMS\AI客服助手"
  CreateShortcut "$SMPROGRAMS\AI客服助手\AI客服助手.lnk" "$INSTDIR\${APP_EXE}"
  CreateShortcut "$SMPROGRAMS\AI客服助手\卸载 AI客服助手.lnk" "$INSTDIR\Uninstall.exe"

  WriteRegStr HKCU "${APP_REG_KEY}" "DisplayName" "${APP_NAME}"
  WriteRegStr HKCU "${APP_REG_KEY}" "DisplayVersion" "${APP_VERSION}"
  WriteRegStr HKCU "${APP_REG_KEY}" "DisplayIcon" "$INSTDIR\${APP_EXE}"
  WriteRegStr HKCU "${APP_REG_KEY}" "InstallLocation" "$INSTDIR"
  WriteRegStr HKCU "${APP_REG_KEY}" "UninstallString" '"$INSTDIR\Uninstall.exe"'
  WriteRegDWORD HKCU "${APP_REG_KEY}" "NoModify" 1
  WriteRegDWORD HKCU "${APP_REG_KEY}" "NoRepair" 1
SectionEnd

Section /o "创建桌面快捷方式" SecDesktop
  CreateShortcut "$DESKTOP\AI客服助手.lnk" "$INSTDIR\${APP_EXE}"
SectionEnd

Section "Uninstall"
  Delete "$DESKTOP\AI客服助手.lnk"
  Delete "$SMPROGRAMS\AI客服助手\AI客服助手.lnk"
  Delete "$SMPROGRAMS\AI客服助手\卸载 AI客服助手.lnk"
  RMDir "$SMPROGRAMS\AI客服助手"
  Delete "$INSTDIR\${APP_EXE}"
  Delete "$INSTDIR\Uninstall.exe"
  RMDir "$INSTDIR"
  DeleteRegKey HKCU "${APP_REG_KEY}"
SectionEnd

LangString DESC_SecCore ${LANG_SIMPCHINESE} "安装 AI 客服桌面客户端。用户数据和备份不会在卸载时删除。"
LangString DESC_SecDesktop ${LANG_SIMPCHINESE} "在桌面创建 AI客服助手 快捷方式。"

!insertmacro MUI_FUNCTION_DESCRIPTION_BEGIN
  !insertmacro MUI_DESCRIPTION_TEXT ${SecCore} $(DESC_SecCore)
  !insertmacro MUI_DESCRIPTION_TEXT ${SecDesktop} $(DESC_SecDesktop)
!insertmacro MUI_FUNCTION_DESCRIPTION_END
