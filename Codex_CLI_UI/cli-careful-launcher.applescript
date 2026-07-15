tell application "Terminal"
	activate
	do script "cd $HOME/Documents/Codex && /Applications/Codex.app/Contents/Resources/codex --profile local-oss --search"
end tell
