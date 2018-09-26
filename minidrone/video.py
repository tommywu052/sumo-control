import cv2
import os
import numpy as np
from PIL import Image
from io import BytesIO
from threading import Event, Thread

import tensorflow as tf
from utils import label_map_util
from utils import visualization_utils as vis_util
from sender import SumoSender, move_cmd
#from controller import SumoController


class SumoDisplay(Thread):
    """
    Displays frames received from the Jumping Sumo
    """
    

    def __init__(self, receiver ,sender):
        Thread.__init__(self, name='SumoDisplay')
        # self.setDaemon(True)
        self.host = '192.168.2.1'
        self.receiver = receiver
        self.sender = sender
        self.should_run = Event()
        self.should_run.set()

        self.window_name = 'Sumo Display'
        # cv2.namedWindow('SumoDisplay')

    def run(self):
        # sender = SumoSender(self.host, 54321)
        # What model to download.
        MODEL_NAME = 'ssd_mobilenet_v1_coco_2017_11_17'
        MODEL_FILE = MODEL_NAME + '.tar.gz'
        DOWNLOAD_BASE = 'http://download.tensorflow.org/models/object_detection/'

        # Path to frozen detection graph. This is the actual model that is used for the object detection.
        PATH_TO_CKPT = MODEL_NAME + '/frozen_inference_graph.pb'

        # List of the strings that is used to add correct label for each box.
        PATH_TO_LABELS = os.path.join('data', 'mscoco_label_map.pbtxt')

        NUM_CLASSES = 90
        #ctrl = SumoController()
        # ## Load a (frozen) Tensorflow model into memory.
        # In[ ]:
        detection_graph = tf.Graph()
        with detection_graph.as_default():
            od_graph_def = tf.GraphDef()
            with tf.gfile.GFile(PATH_TO_CKPT, 'rb') as fid:
                serialized_graph = fid.read()
                od_graph_def.ParseFromString(serialized_graph)
                tf.import_graph_def(od_graph_def, name='')
        # ## Loading label map
        # Label maps map indices to category names, so that when our convolution network predicts `5`, we know that this corresponds to `airplane`.  Here we use internal utility functions, but anything that returns a dictionary mapping integers to appropriate string labels would be fine

        # In[ ]:


        label_map = label_map_util.load_labelmap(PATH_TO_LABELS)
        categories = label_map_util.convert_label_map_to_categories(label_map, max_num_classes=NUM_CLASSES, use_display_name=True)
        category_index = label_map_util.create_category_index(categories)
        config = tf.ConfigProto()
        config.gpu_options.per_process_gpu_memory_fraction = 0.6
        with detection_graph.as_default():
            with tf.Session(graph=detection_graph,config=config) as sess:

                while self.should_run.isSet():
                    frame = self.receiver.get_frame()

                    if frame is not None:
                        byte_frame = BytesIO(frame)
                        image_np = np.array(Image.open(byte_frame))
                        #ret,image_np = cap.read()
                        # Expand dimensions since the model expects images to have shape: [1, None, None, 3]
                        image_np_expanded = np.expand_dims(image_np, axis=0)
                        image_tensor = detection_graph.get_tensor_by_name('image_tensor:0')
                        # Each box represents a part of the image where a particular object was detected.
                        boxes = detection_graph.get_tensor_by_name('detection_boxes:0')
                        # Each score represent how level of confidence for each of the objects.
                        # Score is shown on the result image, together with the class label.
                        scores = detection_graph.get_tensor_by_name('detection_scores:0')
                        classes = detection_graph.get_tensor_by_name('detection_classes:0')
                        num_detections = detection_graph.get_tensor_by_name('num_detections:0')
                        # Actual detection.
                        (boxes, scores, classes, num_detections) = sess.run(
                            [boxes, scores, classes, num_detections],
                            feed_dict={image_tensor: image_np_expanded})
                        # Visualization of the results of a detection.
                        vis_util.visualize_boxes_and_labels_on_image_array(
                            self.sender,
                            image_np,
                            np.squeeze(boxes),
                            np.squeeze(classes).astype(np.int32),
                            np.squeeze(scores),
                            category_index,
                            use_normalized_coordinates=True,
                            line_thickness=8)
                        
                        cv2.imshow(self.window_name, image_np)
                    self.sender.send(move_cmd(60, 0))
                    cv2.waitKey(25)
    def disconnect(self):
        """
        Stops the main loop and closes the display window
        """
        self.should_run.clear()
        cv2.destroyWindow(self.window_name)
