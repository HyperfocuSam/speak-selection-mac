#!/bin/bash
# One-shot installer for Speak Selection.
#  - makes the Raycast scripts executable
#  - creates your .env from the example (if missing)
#  - installs the right-click "Speak Selection" Quick Action with the correct path
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"

echo "Repo: $DIR"

# 1. Raycast scripts executable
chmod +x "$DIR"/raycast/*.sh
echo "✓ Raycast scripts are executable"

# 2. .env
if [ ! -f "$DIR/.env" ]; then
  cp "$DIR/.env.example" "$DIR/.env"
  echo "✓ Created .env — open it and add at least one API key:"
  echo "    $DIR/.env"
else
  echo "✓ .env already exists (left untouched)"
fi

# 3. Right-click Quick Action
SVC="$HOME/Library/Services/SpeakSelection.workflow"
rm -rf "$SVC"
cp -R "$DIR/workflow/SpeakSelection.workflow" "$SVC"
# bake the real repo path into the action's shell command
/usr/bin/sed -i '' "s|__REPO__|$DIR|g" "$SVC/Contents/document.wflow"
/System/Library/CoreServices/pbs -update 2>/dev/null || true
echo "✓ Installed right-click Quick Action -> ~/Library/Services/"

cat <<EOF

Next steps:
  1. Add your API key(s) to:  $DIR/.env
  2. (Optional) Raycast hotkeys:
       Raycast -> Settings -> Extensions -> Script Commands -> Add Script Directory
       Choose:  $DIR/raycast
       Then assign hotkeys to "Speak Selection", "Speak Clipboard", "Stop Speaking".
  3. Try it now:
       echo "Hello from Speak Selection" | /usr/bin/python3 "$DIR/speak_selection.py"

Done.
EOF
