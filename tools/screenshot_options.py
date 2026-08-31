r"""Render each tab of the options window to a PNG, to check the layout.

    QT_QPA_PLATFORM=offscreen \
    ~/Library/Application\ Support/AnkiProgramFiles/.venv/bin/python \
    tools/screenshot_options.py [output directory]
"""
import os, sys

sys.argv = [sys.argv[0]]
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# reuse the set-up of the smoke script: fake main window, temporary user_files
src = open(os.path.join(ROOT, "tools", "qt_smoke.py")).read()
src = src.split("dlg = addon.SenAddDialog()")[0]
exec(compile(src, "qt_smoke_prefix", "exec"))

dlg = addon.SenAddDialog(["Simplified", "Traditional", "Pinyin", "Sentence"])
dlg.wordColor.setColor("#c0392b")
dlg.senLenSpin.setValue(30)
dlg.senMinLenSpin.setValue(0)
dlg.show()
dlg.resize(560, 470)
app.processEvents()
out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "dist")
if not os.path.exists(out):
    os.makedirs(out)
for i in range(dlg.tabs.count()):
    dlg.tabs.setCurrentIndex(i)
    app.processEvents()
    path = os.path.join(out, "options_%s.png" % dlg.tabs.tabText(i).lower())
    dlg.grab().save(path)
    print("wrote", path)
