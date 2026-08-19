#!/usr/bin/env bash
set -euo pipefail

plugin_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
omarchy_path="${OMARCHY_PATH:-/usr/share/omarchy}"
qmllint_bin="${QMLLINT:-/usr/lib/qt6/bin/qmllint}"
qmltestrunner_bin="${QMLTESTRUNNER:-/usr/lib/qt6/bin/qmltestrunner}"
import_root="$(mktemp -d)"

cleanup() {
  rm -rf -- "$import_root"
}
trap cleanup EXIT

omarchy plugin validate "$plugin_dir"
jq -e '
  .schemaVersion == 1
  and .id == "io.github.ctl0v0.normarchy"
  and (.kinds | index("service")) != null
  and (.kinds | index("bar-widget")) != null
  and (.barWidget.schema | length) == 1
' "$plugin_dir/manifest.json" >/dev/null

python3 "$plugin_dir/scripts/catalog_tool.py" \
  "$plugin_dir/catalog/norm-clips.json" --validate-only
python3 "$plugin_dir/scripts/catalog_pipeline.py" validate

jq -e '
  (.items | length) > 0
  and ([.items[].id] | unique | length) == (.items | length)
  and ([.items[] | select(.duration_seconds < 180)] | length) > 0
  and ([.items[] | select(.duration_seconds >= 180 and .duration_seconds < 900)] | length) > 0
  and ([.items[] | select(.duration_seconds >= 900)] | length) > 0
' "$plugin_dir/catalog/norm-clips.json" >/dev/null

python3 -c 'import ast, pathlib, sys; [ast.parse(pathlib.Path(p).read_text()) for p in sys.argv[1:]]' \
  "$plugin_dir/scripts/catalog_lib.py" \
  "$plugin_dir/scripts/catalog_pipeline.py" \
  "$plugin_dir/scripts/catalog_tool.py" \
  "$plugin_dir/scripts/stream_proxy.py"

python3 -m unittest discover -s "$plugin_dir/scripts/tests" -p 'test_*.py'

ln -s "$omarchy_path/shell" "$import_root/qs"
"$qmllint_bin" -I "$import_root" --missing-property disable --uncreatable-type disable \
  --signal-handler-parameters disable \
  "$plugin_dir/Panel.qml" \
  "$plugin_dir/Service.qml" \
  "$plugin_dir/NormIcon.qml" \
  "$plugin_dir/NormWordmark.qml" \
  "$plugin_dir/StickyKeyboardPanel.qml"

env -u DISPLAY -u WAYLAND_DISPLAY -u QT_QPA_PLATFORMTHEME -u GDK_BACKEND \
  QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software \
  "$qmltestrunner_bin" -input "$plugin_dir/tests" -o -,txt

printf '%s\n' 'Normarchy validation and tests passed.'
