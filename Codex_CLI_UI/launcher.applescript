set homeDir to POSIX path of (path to home folder)
set uiDir to homeDir & "Applications/Codex_CLI_UI"
set uiUrl to "http://127.0.0.1:8765"
set nativeApp to uiDir & "/build/Codex CLI UI.app"

try
	do shell script "curl -fsS " & quoted form of (uiUrl & "/api/config") & " >/dev/null 2>&1"
on error
	tell application "Terminal"
		activate
		do script "cd " & quoted form of uiDir & " && python3 server.py"
	end tell
	delay 1
end try

try
	tell application "Finder" to open POSIX file nativeApp
on error
	display dialog "Codex CLI UI is running at " & uiUrl & ". The native app bundle was not found at " & nativeApp buttons {"OK"} default button "OK"
end try
