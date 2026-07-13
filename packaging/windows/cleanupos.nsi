; CleanupOs — NSIS stub (NSIS 3.x)
;
; Skeleton only: commented directives show the intended layout.
; Prefer Inno Setup (cleanupos.iss) for the first public Windows installer
; unless NSIS is required by a downstream packager.
;
; Do NOT commit built .exe installers here.
;
; Safety reminder: never package a build that disables or externalizes the
; denylist (core/safety/denylist.py). Vital core paths must stay FORBIDDEN.

; !define PRODUCT_NAME "CleanupOs"
; !define PRODUCT_VERSION "2.0.0-dev"
; !define PRODUCT_PUBLISHER "YukaC"
; !define PRODUCT_WEB_SITE "https://github.com/YukaC/cleanupDiskW11"
; !define PRODUCT_DIR_REGKEY "Software\Microsoft\Windows\CurrentVersion\App Paths\CleanupOs.exe"
; !define PRODUCT_UNINST_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}"

; Name "${PRODUCT_NAME}"
; OutFile "dist\CleanupOs-Setup-${PRODUCT_VERSION}.exe"
; InstallDir "$PROGRAMFILES64\CleanupOs"
; RequestExecutionLevel admin
; SetCompressor /SOLID lzma

; Section "MainSection" SEC01
;   SetOutPath "$INSTDIR"
;   ; File /r "dist\CleanupOs\*.*"
;   CreateDirectory "$SMPROGRAMS\CleanupOs"
;   CreateShortCut "$SMPROGRAMS\CleanupOs\CleanupOs.lnk" "$INSTDIR\CleanupOs.exe"
; SectionEnd

; Section -Post
;   WriteUninstaller "$INSTDIR\uninst.exe"
;   WriteRegStr HKLM "${PRODUCT_DIR_REGKEY}" "" "$INSTDIR\CleanupOs.exe"
;   WriteRegStr HKLM "${PRODUCT_UNINST_KEY}" "DisplayName" "$(^Name)"
;   WriteRegStr HKLM "${PRODUCT_UNINST_KEY}" "UninstallString" "$INSTDIR\uninst.exe"
;   WriteRegStr HKLM "${PRODUCT_UNINST_KEY}" "DisplayVersion" "${PRODUCT_VERSION}"
; SectionEnd
