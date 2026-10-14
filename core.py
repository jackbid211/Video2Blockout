import base64
import io
import json
import math
from pathlib import Path
import numpy as np
from PIL import Image
from templates import TEMPLATES, kind_for_category

MODEL = 'depth-anything/Depth-Anything-V2-Small-hf'


def png_data(array):
    image = Image.fromarray(array.astype(np.uint8))
    buffer = io.BytesIO()
    image.save(buffer, format='PNG')
    return 'data:image/png;base64,' + base64.b64encode(buffer.getvalue()).decode()


def validate_request(payload):
    frames, objects = payload.get('frames'), payload.get('objects')
    if not isinstance(frames, list) or not 2 <= len(frames) <= 120:
        raise ValueError('需要 2–120 帧')
    fps = float(payload.get('fps', 6))
    if not 1 <= fps <= 12 or not math.isfinite(fps):
        raise ValueError('采样 FPS 必须为 1–12')
    if not isinstance(objects,list) or not 0 <= len(objects) <= 8:
        raise ValueError('最多选择 8 个元素；不选择时仅生成深度')
    for obj in objects:
        if obj.get('kind') not in TEMPLATES:
            raise ValueError('未知几何体类型')
        box = obj.get('box')
        if not isinstance(box,list) or len(box)!=4 or any(not isinstance(v,(float,int)) or not math.isfinite(v) for v in box):
            raise ValueError('无效选择框')
        x,y,w,h = box
        if min(x,y)<0 or min(w,h)<.01 or x+w>1.001 or y+h>1.001:
            raise ValueError('选择框超出图片或过小')
        if not isinstance(obj.get('name'),str) or len(obj['name'])>80:
            raise ValueError('元素名称过长')
    return fps


def detection_objects(xyxy, classes, scores, names, width, height):
    """Convert detector output to bounded normalized selections."""
    objects=[]
    for coords,category_id,score in zip(xyxy,classes,scores):
        x1,y1,x2,y2=[float(v) for v in coords]
        if not all(math.isfinite(v) for v in (x1,y1,x2,y2,float(score))): continue
        x1=max(0,min(width,x1)); x2=max(0,min(width,x2))
        y1=max(0,min(height,y1)); y2=max(0,min(height,y2))
        if x2-x1<width*.01 or y2-y1<height*.01: continue
        category=names[int(category_id)]
        objects.append({'name':f'{category} {len(objects)+1}', 'category':category,
                        'kind':kind_for_category(category),'confidence':float(score),
                        'box':[x1/width,y1/height,(x2-x1)/width,(y2-y1)/height]})
        if len(objects)==8: break
    return objects


def detect(payload,directory,progress):
    from ultralytics import YOLO
    frame=decode_frames([payload['frame']])[0]
    confidence=float(payload.get('confidence',.35))
    if not math.isfinite(confidence) or not .1<=confidence<=.9:
        raise ValueError('识别置信度必须为 0.1–0.9')
    progress('加载 COCO 预训练 YOLO11；首次下载权重',.1)
    (Path(__file__).resolve().parent/'models').mkdir(exist_ok=True)
    detector=YOLO(str(Path(__file__).resolve().parent/'models'/'yolo11n.pt'))
    progress('识别第一帧中的多类别对象',.5)
    result=detector.predict(Image.fromarray(frame),conf=confidence,max_det=8,verbose=False)[0]
    boxes=result.boxes
    objects=detection_objects(boxes.xyxy.cpu().tolist(),boxes.cls.cpu().tolist(),
                              boxes.conf.cpu().tolist(),result.names,frame.shape[1],frame.shape[0])
    progress('识别完成，请修改或删除候选元素',1)
    return {'objects':objects,'detector':'yolo11n.pt','scope':'first-frame'}


def normalize_depth(depths):
    values = np.asarray(depths,dtype=np.float32)
    if not np.isfinite(values).all():
        raise ValueError('深度结果包含非有限数值')
    low,high = np.percentile(values,[2,98])
    normalized = np.clip((values-low)/max(float(high-low),1e-6),0,1)
    return normalized,float(low),float(high)


def project_box(box, near, aspect):
    x,y,w,h=box
    return {'position':[(x+w/2-.5)*6,(1-near)*4,(.5-y-h/2)*6/aspect],
            'dimensions':[w*6,max(.1,w*3),h*6/aspect]}


def decode_frames(strings):
    result=[]
    for value in strings:
        if not isinstance(value,str) or len(value)>1500000 or not value.startswith('data:image/'):
            raise ValueError('无效图像数据')
        image=Image.open(io.BytesIO(base64.b64decode(value.split(',',1)[1],validate=True)))
        if max(image.size)>640 or min(image.size)<32:
            raise ValueError('图片尺寸必须为 32–640 像素')
        result.append(np.asarray(image.convert('RGB')))
    if any(f.shape!=result[0].shape for f in result):
        raise ValueError('所有帧尺寸必须一致')
    return result


def process(payload, directory, progress):
    import cv2
    import torch
    from transformers import AutoImageProcessor, AutoModelForDepthEstimation
    fps=validate_request(payload)
    frames=decode_frames(payload['frames'])
    height,width=frames[0].shape[:2]
    progress('加载深度模型；首次运行会从 Hugging Face 下载权重',.02)
    device='cuda' if torch.cuda.is_available() else 'cpu'
    processor=AutoImageProcessor.from_pretrained(MODEL)
    model=AutoModelForDepthEstimation.from_pretrained(MODEL).to(device).eval()
    depths=[]
    for i,frame in enumerate(frames):
        inputs=processor(images=Image.fromarray(frame),return_tensors='pt').to(device)
        with torch.inference_mode():
            prediction=model(**inputs).predicted_depth
            prediction=torch.nn.functional.interpolate(prediction.unsqueeze(1),size=(height,width),mode='bicubic',align_corners=False)[0,0]
        depths.append(prediction.cpu().numpy())
        progress(f'深度估计 {i+1}/{len(frames)}',.05+.5*(i+1)/len(frames))
    near,low,high=normalize_depth(depths)
    objects=[]
    all_masks=[]
    for object_index,selection in enumerate(payload['objects']):
        x,y,w,h=selection['box']
        box=(int(x*width),int(y*height),max(2,int(w*width)),max(2,int(h*height)))
        box=(min(box[0],width-3),min(box[1],height-3),min(box[2],width-box[0]-1),min(box[3],height-box[1]-1))
        tracker=cv2.TrackerCSRT_create()
        tracker.init(cv2.cvtColor(frames[0],cv2.COLOR_RGB2BGR),box)
        track=[]; masks=[]; last_near=None
        for i,frame in enumerate(frames):
            success=True
            if i:
                success,newbox=tracker.update(cv2.cvtColor(frame,cv2.COLOR_RGB2BGR))
                if success: box=tuple(int(v) for v in newbox)
            x,y,w,h=box
            x=max(0,min(x,width-3)); y=max(0,min(y,height-3))
            w=max(2,min(w,width-x-1)); h=max(2,min(h,height-y-1))
            mask=np.zeros((height,width),np.uint8)
            segmented=False
            if success:
                try:
                    cv2.grabCut(frame,mask,(x,y,w,h),np.zeros((1,65),np.float64),np.zeros((1,65),np.float64),2,cv2.GC_INIT_WITH_RECT)
                    mask=np.isin(mask,(cv2.GC_FGD,cv2.GC_PR_FGD)).astype(np.uint8)
                    segmented=bool(mask.sum()>10)
                except cv2.error:
                    pass
                if not segmented:
                    mask[:]=0; mask[y:y+h,x:x+w]=1
            normalized_box=[x/width,y/height,w/width,h/height]
            measured=float(np.median(near[i][mask.astype(bool)])) if mask.any() else (last_near if last_near is not None else .5)
            smoothed=measured if last_near is None else .7*last_near+.3*measured
            last_near=smoothed
            track.append({'box':normalized_box,'near':smoothed,'visible':bool(success),'segmented':segmented,
                          **project_box(normalized_box,smoothed,width/height)})
            masks.append(mask)
        objects.append({'id':object_index,'name':selection['name'],'kind':selection['kind'],
                        'category':selection.get('category','manual'),'track':track})
        all_masks.append(masks)
        progress(f'追踪和分割 {object_index+1}/{len(payload["objects"])}',.55+.35*(object_index+1)/len(payload['objects']))
    np.savez_compressed(directory/'depth-and-masks.npz',depth=np.asarray(depths,dtype=np.float32),near=near,masks=np.asarray(all_masks,dtype=np.uint8),fps=fps)
    result={'version':1,'mode':'model','width':width,'height':height,'fps':fps,'frame_count':len(frames),
            'model':MODEL,'normalization':{'p2':low,'p98':high},'objects':objects,
            'depth_frames':[png_data(d*255) for d in near],
            'warnings':['相对逆深度：亮色较近，不是米制距离。','固定机位假设；追踪失败帧自动隐藏，GrabCut 失败会使用矩形遮罩。','跨帧深度比例可能漂移；这里只平滑物体深度，未做完整场景重建。']}
    colors=[(77,182,255),(255,144,94),(121,219,165),(220,149,255)]
    overlays=[]
    for i,frame in enumerate(frames):
        overlay=frame.astype(float).copy()
        for j,masks in enumerate(all_masks):
            mask=masks[i].astype(bool)
            overlay[mask]=overlay[mask]*.4+np.array(colors[j%len(colors)])*.6
        overlays.append(png_data(overlay))
    result['mask_frames']=overlays
    (directory/'project.json').write_text(json.dumps(result,ensure_ascii=False),encoding='utf-8')
    progress('处理完成',1)
    return result


def blender_script(project,selected):
    selected={int(i) for i in selected}
    cleaned={k:project[k] for k in ('width','height','fps','frame_count','mode')}
    cleaned['objects']=[o for o in project['objects'] if o['id'] in selected]
    if not cleaned['objects']: raise ValueError('至少保留一个元素')
    literal=repr(json.dumps(cleaned,ensure_ascii=False))
    return '''# Generated by Video2Blockout. Run in Blender's Text Editor or --background --python.
# Creates a NEW scene; existing scenes are kept. Relative depth, fixed original view.
import bpy, bmesh, json, math
from pathlib import Path
P=json.loads('''+literal+''')
TEMPLATES=json.loads('''+repr(json.dumps(TEMPLATES))+''')
scene=bpy.data.scenes.new('Video2Blockout')
if bpy.context.window: bpy.context.window.scene=scene
scene.render.resolution_x=P['width']; scene.render.resolution_y=P['height']
scene.render.resolution_percentage=100
scene.render.fps=round(P['fps']); scene.render.fps_base=round(P['fps'])/P['fps']
scene.frame_start=1; scene.frame_end=P['frame_count']
scene.render.engine='BLENDER_WORKBENCH'
scene.display.shading.light='STUDIO'; scene.display.shading.color_type='SINGLE'
scene.display.shading.single_color=(.85,.85,.85)
scene.display.shading.show_shadows=True; scene.display.shading.show_cavity=True
scene.display.shading.background_type='WORLD'
scene.world=bpy.data.worlds.new('BlockoutWorld'); scene.world.color=(.08,.08,.08)
camera_data=bpy.data.cameras.new('OriginalView'); camera=bpy.data.objects.new('OriginalView',camera_data)
scene.collection.objects.link(camera); scene.camera=camera
camera.location=(0,-10,0); camera.rotation_euler=(math.pi/2,0,0)
camera_data.type='ORTHO'; camera_data.ortho_scale=6; camera_data.sensor_fit='HORIZONTAL'

def mesh(name,kind,position,dimensions,parent):
    geometry=bmesh.new()
    if kind=='sphere': bmesh.ops.create_uvsphere(geometry,u_segments=16,v_segments=8,radius=1)
    elif kind in ('cylinder','wheel'): bmesh.ops.create_cone(geometry,cap_ends=True,cap_tris=False,segments=16,radius1=1,radius2=1,depth=2)
    else: bmesh.ops.create_cube(geometry,size=2)
    data=bpy.data.meshes.new(name); geometry.to_mesh(data); geometry.free()
    obj=bpy.data.objects.new(name,data); scene.collection.objects.link(obj); obj.parent=parent
    obj.location=position; obj.scale=[v/2 for v in dimensions]
    if kind=='wheel': obj.rotation_euler.x=math.pi/2
    return obj

for item in P['objects']:
    root=bpy.data.objects.new(item['name'],None); scene.collection.objects.link(root)
    first=item['track'][0]['dimensions']; w,d,h=first
    children=[]
    for part,(kind,center,size) in enumerate(TEMPLATES.get(item['kind'],TEMPLATES['box'])):
        dimensions=[a*b for a,b in zip(size,(w,d,h))]
        if kind=='sphere' and item['kind']=='person': dimensions=[min(w,h*.3)]*3
        if kind=='wheel': dimensions=[w*size[0],h*size[2],d*size[1]]
        children.append(mesh(item['name']+'_'+str(part),kind,[a*b for a,b in zip(center,(w,d,h))],dimensions,root))
    for i,sample in enumerate(item['track'],1):
        root.location=sample['position']
        root.scale=tuple(a/b for a,b in zip(sample['dimensions'],(w,d,h)))
        root.keyframe_insert(data_path='location',frame=i); root.keyframe_insert(data_path='scale',frame=i)
        for obj in children:
            obj.hide_render=not sample['visible']; obj.hide_viewport=not sample['visible']
            obj.keyframe_insert(data_path='hide_render',frame=i); obj.keyframe_insert(data_path='hide_viewport',frame=i)
    owners=[root]+children
    for owner in owners:
        action=owner.animation_data.action
        curves=[]
        if hasattr(action,'layers') and len(action.layers):
            for layer in action.layers:
                for strip in layer.strips:
                    for bag in getattr(strip,'channelbags',[]): curves.extend(bag.fcurves)
        else: curves=list(getattr(action,'fcurves',[]))
        for curve in curves:
            for key in curve.keyframe_points: key.interpolation='CONSTANT' if curve.data_path.startswith('hide_') else 'LINEAR'
scene['video2blockout_mode']=P['mode']; scene['video2blockout_note']='Approximate relative depth, fixed view, not metric reconstruction'
scene.frame_set(1)
output=Path(__file__).resolve().parent if '__file__' in globals() else Path(bpy.path.abspath('//'))
bpy.ops.wm.save_as_mainfile(filepath=str(output/'Video2Blockout.blend'))
print('Saved Video2Blockout.blend. Render animation as image sequence using this scene.')
'''
