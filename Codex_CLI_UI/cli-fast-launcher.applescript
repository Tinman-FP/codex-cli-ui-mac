tell application "Terminal"
	activate
	do script "mkdir -p ~/Documents/Codex && cd ~/Documents/Codex && /Applications/Codex.app/Contents/Resources/codex --profile local-fast --search"
end tell
