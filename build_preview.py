"""Rebuild standalone preview after regenerating examples with make_demo.py."""
import json,re
from pathlib import Path
from core import blender_script
root=Path(__file__).resolve().parent
project=json.loads((root/'examples/demo.json').read_text(encoding='utf-8'))
script=blender_script(project,[o['id'] for o in project['objects']])
# Replace only the serialized project, preserving the shared template table.
script=re.sub(r'^P=json.loads\(.*\)$','P=json.loads(__PROJECT_JSON__)',script,count=1,flags=re.M)
# Escape literal HTML terminators in data rather than the closing script tag.
data='window.V2B_DEMO='+json.dumps(project,ensure_ascii=False)+';window.V2B_SCRIPT='+json.dumps(script,ensure_ascii=False)+';'
embedded='<script>'+data.replace('</','<\\/')+'</script>'
html=(root/'index.html').read_text(encoding='utf-8').replace('<script>',embedded+'\n<script>',1)
html=html.replace('<script src="/video-loader.js"></script>','<script>'+(root/'video-loader.js').read_text(encoding='utf-8')+'</script>')
(root/'demo-preview.html').write_text(html,encoding='utf-8')
print('Standalone preview rebuilt')
