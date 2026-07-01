tell application "Terminal"
	activate
	do script "cd " & quoted form of (POSIX path of (path to home folder) & "Documents/Codex") & " && /Applications/Codex.app/Contents/Resources/codex --profile local-oss --search"
end tell
