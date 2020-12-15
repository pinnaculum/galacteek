!include "MUI2.nsh"
!include "LogicLib.nsh"
!include "nsDialogs.nsh"

!define MUI_ICON "share/icons/galacteek.ico"

CRCCheck on
OutFile "Galacteek-Installer.exe"
RequestExecutionLevel admin

!define APPNAME "Galacteek"
!define GROUPNAME "Galacteek"
!define /date NOW "%Y%m%d"

!define VERSIONMAJOR 0
!define VERSIONMINOR 4
!define VERSIONBUILD 42

Name "${APPNAME}"
Icon "share/icons/galacteek.ico"

var GFILESDIR
var SHORTCUTDIR
var DESKTOPDIR
var IS_ADMIN
var USERNAME
var PREVIOUS_INSTALLDIR
Var REINSTALL_UNINSTALL
Var REINSTALL_UNINSTALLBUTTON

# Check for administrative rights
!macro VerifyUserIsAdmin
    UserInfo::GetAccountType
    pop $0
    ${If} $0 != "admin"
        messageBox mb_iconstop "Administrator rights required!"
        setErrorLevel 740 ;ERROR_ELEVATION_REQUIRED
        quit
    ${EndIf}
!macroend

Function GetUserInfo
  ClearErrors
  UserInfo::GetName
  ${If} ${Errors}
    StrCpy $IS_ADMIN 1
    Return
  ${EndIf}

  Pop $USERNAME
  UserInfo::GetAccountType
  Pop $R0
  ${Switch} $R0
    ${Case} "Admin"
    ${Case} "Power"
      StrCpy $IS_ADMIN 1
      ${Break}
    ${Default}
      StrCpy $IS_ADMIN 0
      ${Break}
  ${EndSwitch}

FunctionEnd

Function CheckPrevInstallDirExists
  ${If} $PREVIOUS_INSTALLDIR != ""
    ; Make sure directory is valid
    Push $R0
    Push $R1
    StrCpy $R0 "$PREVIOUS_INSTALLDIR" "" -1
    ${If} $R0 == '\'
    ${OrIf} $R0 == '/'
      StrCpy $R0 $PREVIOUS_INSTALLDIR*.*
    ${Else}
      StrCpy $R0 $PREVIOUS_INSTALLDIR\*.*
    ${EndIf}
    ${IfNot} ${FileExists} $R0
      StrCpy $PREVIOUS_INSTALLDIR ""
    ${EndIf}
    Pop $R1
    Pop $R0

  ${EndIf}
FunctionEnd

Function RunUninstaller
  ReadRegStr $R1 HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" "UninstallString"
  ${If} $R1 == ""
    Return
  ${EndIf}

  ClearErrors
  ExecWait '$R1 /S _?=$INSTDIR'
FunctionEnd

function .onInit
    !insertmacro VerifyUserIsAdmin
    StrCpy $GFILESDIR "$PROGRAMFILES64\${APPNAME}"
    StrCpy $INSTDIR "$GFILESDIR"
    StrCpy $SHORTCUTDIR "$SMPROGRAMS\${APPNAME}"
    StrCpy $DESKTOPDIR "$DESKTOP"
functionEnd

Function PageLeaveFinish
    Quit
FunctionEnd

Function PageFinish
    nsDialogs::Create /NOUNLOAD 1018
    Pop $0

    !insertmacro MUI_HEADER_TEXT "Already Installed" "Upgrade."
    nsDialogs::CreateItem /NOUNLOAD STATIC ${WS_VISIBLE}|${WS_CHILD}|${WS_CLIPSIBLINGS} 0 0 0 100% 40 "Installation success! Enjoy your experience on the dweb"
    Pop $R0
FunctionEnd

Function PageLeaveReinstall
  ${If} $REINSTALL_UNINSTALL == 1
    Call RunUninstaller
  ${EndIf}
FunctionEnd

Function PageReinstall
    ReadRegStr $0  HKCU "Software\${APPNAME}" 'Version'
    StrCpy $R2 $0

    ${If} $R2 != ""
      nsDialogs::Create /NOUNLOAD 1018
      Pop $0

      !insertmacro MUI_HEADER_TEXT "Already Installed" "Upgrade."
      nsDialogs::CreateItem /NOUNLOAD STATIC ${WS_VISIBLE}|${WS_CHILD}|${WS_CLIPSIBLINGS} 0 0 0 100% 40 "Galacteek version $R2 is already installed on your system, click Next to uninstall the previous version"
      Pop $R0
      StrCpy $REINSTALL_UNINSTALL 1

      nsDialogs::Show $0
    ${Else}
      StrCpy $REINSTALL_UNINSTALL 0
    ${EndIf}

FunctionEnd

PageEx license
    LicenseData LICENSE
PageExEnd

Page custom PageReinstall PageLeaveReinstall

PageEx directory
    DirText "Please select the installation directory"
    DirVar $GFILESDIR
PageExEnd

Page instfiles

UninstPage uninstConfirm
UninstPage instfiles

ShowInstDetails show
ShowUninstDetails show

Section "Visual Studio Runtime"
  SetOutPath $GFILESDIR
  File "vc_redist.x64.exe"
  ExecWait "$INSTDIR\vc_redist.x64.exe /quiet"
SectionEnd

Section

SetOutPath $GFILESDIR

File /r "dist\galacteek\*"

SectionEnd

Section G
    WriteUninstaller "$GFILESDIR\uninstall.exe"

    createDirectory "$SHORTCUTDIR"
    createShortCut "$SHORTCUTDIR\${APPNAME}.lnk" "$GFILESDIR\galacteek.exe"
    createShortCut "$SHORTCUTDIR\${APPNAME} (Debug).lnk" "$GFILESDIR\galacteek.exe" '-d'
    createShortCut "$SHORTCUTDIR\Uninstall.lnk" "$GFILESDIR\uninstall.exe"
    createShortCut "$DESKTOPDIR\${APPNAME}.lnk" "$GFILESDIR\galacteek.exe"

    ExecWait 'netsh advfirewall firewall add rule name=g_ipfs_in dir=in action=allow program="$GFILESDIR\ipfs.exe" enable=yes profile=public,private'
    ExecWait 'netsh advfirewall firewall add rule name=g_ipfs_out dir=out action=allow program="$GFILESDIR\ipfs.exe" enable=yes profile=public,private'

    # Registry
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" "DisplayName" "${APPNAME}"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" "UninstallString" '"$GFILESDIR\uninstall.exe"'
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" "QuietUninstallString" "$\"$INSTDIR\uninstall.exe$\" /S"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" "InstallLocation" '"$GFILESDIR"'
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" "InstallDate" "${NOW}"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" "Publisher" "${GROUPNAME}"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" "DisplayVersion" "${VERSIONMAJOR}.${VERSIONMINOR}.${VERSIONBUILD}"
    WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" "VersionMajor" ${VERSIONMAJOR}
    WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" "VersionMinor" ${VERSIONMINOR}
    WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" "VersionBuild" ${VERSIONBUILD}
    WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" "NoModify" 1
    WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" "NoRepair" 1

    WriteRegStr HKCU "Software\${APPNAME}" "DESKTOPDIR" "$DESKTOPDIR"
    WriteRegStr HKCU "Software\${APPNAME}" "Version" "${VERSIONMAJOR}.${VERSIONMINOR}.${VERSIONBUILD}"
SectionEnd

Page custom PageFinish PageLeaveFinish

function un.onInstSuccess
    ExecShell "open" "$SHORTCUTDIR"
functionEnd

function un.onInit
    SetShellVarContext all

    MessageBox MB_OKCANCEL "Uninstall ${APPNAME} ?" IDOK next
        Abort
    next:
    !insertmacro VerifyUserIsAdmin
functionEnd

Section "uninstall"
    ReadRegStr $0  HKCU "Software\${APPNAME}" 'DESKTOPDIR'
    StrCpy $DESKTOPDIR $0

    delete "$SMPROGRAMS\${APPNAME}\${APPNAME}.lnk"
    delete "$SMPROGRAMS\${APPNAME}\${APPNAME} (Debug).lnk"
    delete "$DESKTOPDIR\${APPNAME}.lnk"

    rmDir /r "$SMPROGRAMS\${APPNAME}"
    rmDir /r "$instdir"

    ExecWait 'netsh advfirewall firewall delete rule name=g_ipfs_in'
    ExecWait 'netsh advfirewall firewall delete rule name=g_ipfs_out'

    DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}"
    DeleteRegKey HKCU "Software\${APPNAME}"
SectionEnd
