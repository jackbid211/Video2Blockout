import unittest
import numpy as np
from core import normalize_depth,project_box,validate_request,blender_script,detection_objects
from templates import TEMPLATES,kind_for_category

class CoreTests(unittest.TestCase):
    def payload(self): return {'frames':['a','b'],'fps':6,'objects':[{'name':'人','kind':'person','box':[.1,.1,.2,.3]}]}
    def test_frame_limit(self):
        p=self.payload(); p['frames']=['a']*121
        with self.assertRaises(ValueError):validate_request(p)
    def test_depth_without_selected_objects(self):
        p=self.payload();p['objects']=[]
        self.assertEqual(validate_request(p),6)
    def test_out_of_bounds_box(self):
        p=self.payload();p['objects'][0]['box']=[.9,.1,.3,.2]
        with self.assertRaises(ValueError):validate_request(p)
    def test_nonfinite_fps(self):
        p=self.payload();p['fps']=float('nan')
        with self.assertRaises(ValueError):validate_request(p)
    def test_sequence_normalization(self):
        near,low,high=normalize_depth([np.zeros((4,4)),np.ones((4,4))*10])
        self.assertTrue(np.all(near[0]==0)); self.assertTrue(np.all(near[1]==1))
    def test_constant_depth(self):
        near,_,_=normalize_depth(np.ones((2,3,3)))
        self.assertTrue(np.isfinite(near).all())
    def test_reject_nonfinite_depth(self):
        with self.assertRaises(ValueError):normalize_depth([[[float('nan')]]])
    def test_projection_center(self):
        p=project_box([.4,.4,.2,.2],1,2)
        for value in p['position']: self.assertAlmostEqual(value,0)
        self.assertAlmostEqual(p['dimensions'][2],.6)
    def test_export_selection_and_safe_names(self):
        track=[{'position':[0,1,0],'dimensions':[1,1,2],'visible':True}]
        p={'width':640,'height':360,'fps':6,'frame_count':1,'mode':'demo','objects':[{'id':0,'name':"x');raise Exception()#",'kind':'person','track':track},{'id':1,'name':'table','kind':'box','track':track}]}
        script=blender_script(p,[0]);compile(script,'generated.py','exec')
        self.assertNotIn('"name": "table"',script)
        self.assertIn("bpy.data.scenes.new",script)
    def test_empty_selection_rejected(self):
        p={'width':640,'height':360,'fps':6,'frame_count':1,'mode':'demo','objects':[]}
        with self.assertRaises(ValueError):blender_script(p,[])

    def test_detection_clipping_and_category_mapping(self):
        objects=detection_objects([[-5,10,120,90],[20,20,20,25]], [0,1],[.9,.8],{0:'horse',1:'car'},100,100)
        self.assertEqual(len(objects),1)
        self.assertEqual(objects[0]['kind'],'horse')
        self.assertEqual(objects[0]['box'],[0,.1,1,.8])
        p=self.payload();p['objects']=objects;validate_request(p)

    def test_detection_empty_limit_and_nonfinite(self):
        self.assertEqual(detection_objects([],[],[],{},100,100),[])
        objects=detection_objects([[0,0,20,20]]*12,[0]*12,[.8]*12,{0:'car'},100,100)
        self.assertEqual(len(objects),8)
        self.assertEqual(detection_objects([[0,0,float('nan'),20]],[0],[.8],{0:'car'},100,100),[])

    def test_multiclass_and_fallback(self):
        for category,kind in [('person','person'),('horse','horse'),('truck','car'),('dog','animal'),('dining table','table'),('unknown','box')]:
            self.assertEqual(kind_for_category(category),kind)
        self.assertEqual(sum(p[0]=='wheel' for p in TEMPLATES['car']),4)
        self.assertEqual(len(TEMPLATES['horse']),7)

    def test_all_templates_export_valid_python(self):
        for kind in TEMPLATES:
            p=self.payload();p['objects'][0]['kind']=kind;validate_request(p)
            track=[{'position':[0,1,0],'dimensions':[1,1,2],'visible':True}]
            project={'width':640,'height':360,'fps':6,'frame_count':1,'mode':'demo','objects':[{'id':0,'name':kind,'kind':kind,'track':track}]}
            compile(blender_script(project,[0]),kind+'.py','exec')

if __name__=='__main__':unittest.main()
