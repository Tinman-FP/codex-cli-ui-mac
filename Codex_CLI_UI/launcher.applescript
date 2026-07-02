set uiDir to POSIX path of (path to home folder) & "Applications/Codex_CLI_UI"
set uiUrl to "http://127.0.0.1:8765"

try
	do shell script "curl -fsS " & quoted form of (uiUrl & "/api/config") & " >/dev/null 2>&1"
on error
	tell application "Terminal"
		activate
		do script "cd " & quoted form of uiDir & " && python3 server.py"
	end tell
	delay 1
end try

open location uiUrl
