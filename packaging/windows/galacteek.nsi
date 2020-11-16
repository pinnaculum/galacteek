!include "MUI2.nsh"

!define MUI_ICON "share/icons/galacteek.ico"

CRCCheck on
OutFile "Galacteek-Installer.exe"
RequestExecutionLevel admin

!define APPNAME "Galacteek"
!define GROUPNAME "Galacteek"
!define /date NOW "%Y%m%d"

!define VERSIONMAJOR 0
!define VERSIONMINOR 4
!define VERSIONBUILD 39

Name "${APPNAME}"
Icon "share/icons/galacteek.ico"

var GFILESDIR
var SHORTCUTDIR
var DESKTOPDIR

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

function .onInit
    !insertmacro VerifyUserIsAdmin
    StrCpy $GFILESDIR "$PROGRAMFILES64\${APPNAME}"
    StrCpy $SHORTCUTDIR "$SMPROGRAMS\${APPNAME}"
    StrCpy $DESKTOPDIR "$DESKTOP"
functionEnd

PageEx license
    LicenseData LICENSE
PageExEnd

PageEx directory
    DirText "Please select the installation directory"
    DirVar $GFILESDIR
PageExEnd

Page instfiles

UninstPage uninstConfirm
UninstPage instfiles

ShowInstDetails show
ShowUninstDetails show

Section

SetOutPath $GFILESDIR

File /r "dist\galacteek\*"

SectionEnd

Section G
    WriteUninstaller "$GFILESDIR\uninstall.exe"

    createDirectory "$SHORTCUTDIR"
    createShortCut "$SHORTCUTDIR\${APPNAME}.lnk" "$GFILESDIR\galacteek.exe"
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
    # WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" "NoModify" 1
    WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" "NoRepair" 1

    WriteRegStr HKCU "Software\${APPNAME}" "DESKTOPDIR" "$DESKTOPDIR"
SectionEnd

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
    delete "$DESKTOPDIR\${APPNAME}.lnk"

    rmDir /r "$SMPROGRAMS\${APPNAME}"
    rmDir /r "$instdir"

    ExecWait 'netsh advfirewall firewall delete rule name=g_ipfs_in'
    ExecWait 'netsh advfirewall firewall delete rule name=g_ipfs_out'

    DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}"
    DeleteRegKey HKCU "Software\${APPNAME}"
SectionEnd
