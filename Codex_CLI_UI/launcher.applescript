set homeDir to POSIX path of (path to home folder)
set uiDir to homeDir & "Applications/Codex_CLI_UI"
set uiUrl to "http://127.0.0.1:8765"

try
	do shell script "curl -fsS " & quoted form of (uiUrl & "/api/config") & " >/dev/null 2>&1"
on error
	try
		do shell script "launchctl kickstart -k gui/$(id -u)/com.tinmanfp.codex-cli-ui >/dev/null 2>&1"
	on error
		tell application "Terminal"
			activate
			do script "cd " & quoted form of uiDir & " && /usr/bin/python3 server.py"
		end tell
	end try
	delay 1
end try

open location uiUrl
