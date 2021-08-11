from jetbot import ObjectDetector
model = ObjectDetector('ssd_mobilenet_v2_coco.engine')

from jetbot import Camera
camera = Camera.instance(width=300, height=300)

import torch
import torchvision
import torch.nn.functional as F
import cv2
import numpy as np

mean = 255.0 * np.array([0.485, 0.456, 0.406])
stdev = 255.0 * np.array([0.229, 0.224, 0.225])

normalize = torchvision.transforms.Normalize(mean, stdev)

def preprocess(camera_value):
    global device, normalize
    x = camera_value
    #图片缩放至224,224对比224,244的避障模型
    x = cv2.resize(x, (224, 224))
    x = cv2.cvtColor(x, cv2.COLOR_BGR2RGB)
    x = x.transpose((2, 0, 1))
    x = torch.from_numpy(x).float()
    x = normalize(x)
    x = x.to(device)
    x = x[None, ...]
    return x

from jetbot import Robot
robot = Robot()

from jetbot import bgr8_to_jpeg
import ipywidgets.widgets as widgets
import time
image_widget = widgets.Image(format='jpeg', width=300, height=300)
#将下面这条语句的value值改为检测目标物体的对象值，取值范围0-99，例如跟随对象是Person(人) (index 1)，需要将value的值改为1
label_widget = widgets.IntText(value=1, description='tracked label')
speed_widget = widgets.FloatSlider(value=0.6, min=0.0, max=1.0, description='speed')
turn_gain_widget = widgets.FloatSlider(value=0.8, min=0.0, max=2.0, description='turn gain')

display(widgets.VBox([
    widgets.HBox([image_widget]),
    label_widget,
    speed_widget,
    turn_gain_widget
]))

width = int(image_widget.width)
height = int(image_widget.height)

def detection_center(detection):
    """计算对象的中心x、y坐标"""
    bbox = detection['bbox']
    center_x = (bbox[0] + bbox[2]) / 2.0 - 0.5
    center_y = (bbox[1] + bbox[3]) / 2.0 - 0.5
    return (center_x, center_y)
    
def norm(vec):
    """计算二维向量的长度"""
    return np.sqrt(vec[0]**2 + vec[1]**2)

def closest_detection(detections):
    """查找最接近图像中心的检测"""
    closest_detection = None
    for det in detections:
        center = detection_center(det)
        if closest_detection is None:
            closest_detection = det
        elif norm(detection_center(det)) < norm(detection_center(closest_detection)):
            closest_detection = det
    return closest_detection
        
def execute(change):
    image = change['new']
    # 计算所有检测到的对象
    detections = model(image)
    
    # 在图像上绘制所有检测
    for det in detections[0]:
        bbox = det['bbox']
        cv2.rectangle(image, (int(width * bbox[0]), int(height * bbox[1])), (int(width * bbox[2]), int(height * bbox[3])), (255, 0, 0), 2)
    
    # 选择匹配所选类标签的检测
    matching_detections = [d for d in detections[0] if d['label'] == int(label_widget.value)]
    
    # 让检测最接近视野中心，并绘制它
    det = closest_detection(matching_detections)
    if det is not None:
        bbox = det['bbox']
        cv2.rectangle(image, (int(width * bbox[0]), int(height * bbox[1])), (int(width * bbox[2]), int(height * bbox[3])), (0, 255, 0), 5)
    
    # 如果没有检测到目标，则停止继续前进
    if det is None:
        pass
        # robot.stop()
        # robot.forward(float(speed_widget.value))
        robot.left(0.6)
        time.sleep(1)
        robot.right(0.6)
        time.sleep(2)
        # robot.stop()
#         robot.forward(speed_widget.value)
#         time.sleep(1.2)
#         robot.stop()
    # 有的话就控制Jetbot去跟随设定的对象
    else:
        # 将机器人向前移动，并控制成比例的目标与中心的x距离
        center = detection_center(det)
        robot.set_motors(
            float(speed_widget.value + turn_gain_widget.value * center[0]),
            float(speed_widget.value - turn_gain_widget.value * center[0])
        )
    
    # 更新图像显示至小部件
    image_widget.value = bgr8_to_jpeg(image)
    
execute({'new': camera.value})

import threading
import inspect
import ctypes
'''以下为定义关闭线程函数'''
def _async_raise(tid, exctype):
  """raises the exception, performs cleanup if needed"""
  tid = ctypes.c_long(tid)
  if not inspect.isclass(exctype):
    exctype = type(exctype)
  res = ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, ctypes.py_object(exctype))
  if res == 0:
    raise ValueError("invalid thread id")
  elif res != 1:
    # """if it returns a number greater than one, you're in trouble,
    # and you should call it again with exc=NULL to revert the effect"""
    ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, None)
    raise SystemError("PyThreadState_SetAsyncExc failed")
def stop_thread(thread):
  _async_raise(thread.ident, SystemExit)
'''线程1的函数，里面不断调用检测函数'''
def test():
    while True:
        execute({'new': camera.value})        

        
thread1 = threading.Thread(target=test)
thread1.setDaemon(False)
thread1.start()