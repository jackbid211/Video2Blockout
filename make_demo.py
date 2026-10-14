"""Generate synthetic fixture data. No model inference or tracking is performed."""
import json
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
from core import png_data,project_box,blender_script

root=Path(__file__).resolve().parent/'examples'; root.mkdir(exist_ok=True)
sources=[]; depths=[]; masks=[]; objects=[{'id':0,'name':'人物','kind':'person','track':[]},{'id':1,'name':'桌子','kind':'table','track':[]},{'id':2,'name':'马匹','kind':'horse','track':[]},{'id':3,'name':'汽车','kind':'car','track':[]}]
for i in range(36):
    image=Image.new('RGB',(640,360),'#253b4c'); draw=ImageDraw.Draw(image)
    draw.rectangle((0,260,640,360),fill='#435665')
    x=35+i*2
    draw.ellipse((x+12,80,x+48,116),fill='#ecc9a4')
    draw.rectangle((x+5,117,x+55,220),fill='#da756b')
    draw.line((x+15,220,x+5,275),fill='#aec4d4',width=14)
    draw.line((x+45,220,x+55,275),fill='#aec4d4',width=14)
    draw.rectangle((440,190,570,210),fill='#bba98a')
    draw.rectangle((450,210,460,280),fill='#bba98a'); draw.rectangle((550,210,560,280),fill='#bba98a')
    hx=190+i
    draw.rectangle((hx,130,hx+90,170),fill='#a47e5a')
    draw.rectangle((hx+73,100,hx+90,145),fill='#a47e5a')
    draw.rectangle((hx+77,95,hx+105,110),fill='#b18a65')
    for lx in (hx+10,hx+65): draw.rectangle((lx,170,lx+10,215),fill='#a47e5a')
    cx=330+i*2
    draw.rectangle((cx,75,cx+120,110),fill='#7899bb')
    draw.rectangle((cx+30,50,cx+85,75),fill='#a9c7df')
    for wx in (cx+18,cx+85): draw.ellipse((wx,98,wx+24,122),fill='#1a222d')
    draw.text((15,15),'SYNTHETIC DEMO / NOT AI INFERENCE',fill='#ffdf9e')
    source=np.asarray(image); sources.append(png_data(source))
    depth=np.full((360,640),40,np.uint8); depth[260:]=65
    person=[x/640,80/360,60/640,195/360]; table=[440/640,190/360,130/640,90/360]
    horse=[hx/640,95/360,105/640,120/360]; car=[cx/640,50/360,120/640,72/360]
    depth[80:275,x:x+60]=220; depth[190:280,440:570]=120
    depth[95:215,hx:hx+105]=160; depth[50:122,cx:cx+120]=85
    depths.append(png_data(depth))
    overlay=source.copy(); overlay[80:275,x:x+60]=(100,180,240); overlay[190:280,440:570]=(220,150,100)
    overlay[95:215,hx:hx+105]=(121,219,165); overlay[50:122,cx:cx+120]=(220,149,255); masks.append(png_data(overlay))
    for obj,box,near in zip(objects,[person,table,horse,car],[.86,.47,.63,.33]):
        obj['track'].append({'box':box,'near':near,'visible':True,'segmented':False,**project_box(box,near,640/360)})
project={'version':1,'mode':'demo','width':640,'height':360,'fps':6,'frame_count':36,'objects':objects,'source_frames':sources,'depth_frames':depths,'mask_frames':masks,'warnings':['离线预设演示：图片、深度和轨迹均为程序构造，未运行 AI 模型。','仅用于验证保留选择、白模预览、导出流程。']}
(root/'demo.json').write_text(json.dumps(project,ensure_ascii=False),encoding='utf-8')
(root/'build_demo_blockout.py').write_text(blender_script(project,[0,1,2,3]),encoding='utf-8')
Image.open(__import__('io').BytesIO(__import__('base64').b64decode(sources[0].split(',')[1]))).save(root/'demo-first-frame.png')
print('Synthetic demonstration generated')
