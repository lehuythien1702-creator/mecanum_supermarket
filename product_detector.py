#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Product Detector Node - Nhận diện sản phẩm trên kệ
Bước 1: Nhận diện màu kệ (OpenCV HSV)
Bước 2: YOLO integration (nếu có)
Bước 3: Xác nhận vị trí khi robot AT_DESTINATION
"""

import rclpy
import cv2
import json
import numpy as np
from rclpy.node import Node
from rclpy.executors import MultiThreadedExecutor
from sensor_msgs.msg import Image
from std_msgs.msg import String
from cv_bridge import CvBridge
from collections import deque

# ========== TRY IMPORT YOLO ==========
try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False

# ========== ĐỊNH NGHĨA MÀU KỀ ==========
SHELF_COLORS = {
    'A': {
        'name': 'Kệ A - Sữa & Nước',
        'color_name': 'Đỏ',
        'hsv_lower': (0, 100, 100),
        'hsv_upper': (10, 255, 255)
    },
    'B': {
        'name': 'Kệ B - Bánh kẹo',
        'color_name': 'Xanh lam',
        'hsv_lower': (100, 100, 100),
        'hsv_upper': (130, 255, 255)
    },
    'C': {
        'name': 'Kệ C - Rau củ',
        'color_name': 'Vàng',
        'hsv_lower': (20, 100, 100),
        'hsv_upper': (40, 255, 255)
    },
    'D': {
        'name': 'Kệ D - Thịt cá',
        'color_name': 'Tím',
        'hsv_lower': (125, 30, 30),
        'hsv_upper': (165, 255, 255)
    },
    'E': {
        'name': 'Kệ E - Đồ đông lạnh',
        'color_name': 'Cam',
        'hsv_lower': (10, 100, 100),
        'hsv_upper': (25, 255, 255)
    },
    'F': {
        'name': 'Kệ F - Hóa mỹ phẩm',
        'color_name': 'Hồng',
        'hsv_lower': (150, 50, 50),
        'hsv_upper': (180, 255, 255)
    }
}

class ProductDetector(Node):
    def __init__(self):
        super().__init__('product_detector_node')
        
        self.get_logger().info("🎥 Product Detector Node khởi động...")
        
        # ========== BRIDGE CONVERT IMAGE ==========
        self.bridge = CvBridge()
        
        # ========== SUBSCRIBERS ==========
        self.create_subscription(Image, '/camera/image_raw', self.image_callback, 10)
        self.create_subscription(String, '/robot_status', self.robot_status_callback, 10)
        
        # ========== PUBLISHERS ==========
        self.detected_products_pub = self.create_publisher(String, '/detected_products', 10)
        self.annotated_image_pub = self.create_publisher(Image, '/camera/annotated', 10)
        self.shelf_confirmed_pub = self.create_publisher(String, '/shelf_confirmed', 10)
        
        # ========== STATE ==========
        self.robot_state = "IDLE"
        self.current_target = None
        self.frame_buffer = deque(maxlen=5)  # Lưu 5 frame gần nhất
        
        # ========== YOLO ==========
        self.yolo_model = None
        if YOLO_AVAILABLE:
            try:
                # Kiểm tra file model
                model_path = "models/product_yolo.pt"
                import os
                if os.path.exists(model_path):
                    self.yolo_model = YOLO(model_path)
                    self.get_logger().info(f"✅ YOLO model loaded: {model_path}")
                else:
                    self.get_logger().warn(f"⚠️ YOLO model không tìm thấy: {model_path}")
            except Exception as e:
                self.get_logger().warn(f"⚠️ Lỗi load YOLO: {e}")
                self.yolo_model = None
        else:
            self.get_logger().info("ℹ️ YOLO không cài đặt, dùng color detection")
        
        self.get_logger().info("✅ Product Detector Node sẵn sàng!")
    
    def image_callback(self, msg):
        """Nhận ảnh từ camera"""
        try:
            # Convert ROS Image → OpenCV
            frame = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
            
            # Detect sản phẩm
            detected = self.detect_products(frame)
            
            # Nếu robot AT_DESTINATION, buffer frame để vote
            if self.robot_state == "AT_DESTINATION":
                self.frame_buffer.append({
                    'frame': frame,
                    'detection': detected
                })
                
                # Khi buffer đầy (5 frames), vote
                if len(self.frame_buffer) == 5:
                    self.vote_shelf_detection()
            
            # Publish annotated frame
            annotated = self.draw_detections(frame, detected)
            annotated_msg = self.bridge.cv2_to_imgmsg(annotated, encoding='bgr8')
            self.annotated_image_pub.publish(annotated_msg)
            
        except Exception as e:
            self.get_logger().error(f"❌ Lỗi xử lý ảnh: {e}")
    
    def robot_status_callback(self, msg):
        """Nhận trạng thái robot"""
        try:
            status = json.loads(msg.data)
            self.robot_state = status.get('state', 'IDLE')
            self.current_target = status.get('target')
        except:
            pass
    
    def detect_products(self, frame):
        """Nhận diện sản phẩm/màu kệ"""
        # Convert BGR → HSV
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        
        detections = {
            'shelf_color': None,
            'shelf_id': None,
            'confidence': 0.0,
            'yolo_products': []
        }
        
        # ========== BƯỚC 1: DETECT MÀU KỀ ==========
        best_shelf = None
        best_confidence = 0.0
        
        for shelf_id, color_info in SHELF_COLORS.items():
            lower = np.array(color_info['hsv_lower'])
            upper = np.array(color_info['hsv_upper'])
            
            # Tạo mask
            mask = cv2.inRange(hsv, lower, upper)
            
            # Tính confidence = tỉ lệ pixel phù hợp
            pixel_count = cv2.countNonZero(mask)
            total_pixels = mask.size
            confidence = pixel_count / total_pixels
            
            if confidence > best_confidence and confidence > 0.05:  # Threshold 5%
                best_confidence = confidence
                best_shelf = shelf_id
        
        if best_shelf and best_confidence > 0.1:  # Threshold 10%
            detections['shelf_color'] = SHELF_COLORS[best_shelf]['color_name']
            detections['shelf_id'] = best_shelf
            detections['confidence'] = round(best_confidence, 2)
        
        # ========== BƯỚC 2: YOLO ==========
        if self.yolo_model is not None:
            try:
                results = self.yolo_model.predict(frame, conf=0.5)
                for detection in results[0].boxes.data:
                    x1, y1, x2, y2, conf, cls = detection
                    detections['yolo_products'].append({
                        'class_id': int(cls),
                        'confidence': float(conf),
                        'bbox': [int(x1), int(y1), int(x2), int(y2)]
                    })
            except Exception as e:
                self.get_logger().debug(f"YOLO inference lỗi: {e}")
        
        # Publish detections
        self.detected_products_pub.publish(String(data=json.dumps(detections)))
        
        return detections
    
    def draw_detections(self, frame, detections):
        """Vẽ bounding box và annotation lên frame"""
        annotated = frame.copy()
        height, width = annotated.shape[:2]
        
        # Vẽ shelf detection
        if detections['shelf_id']:
            text = f"{detections['shelf_id']} ({detections['shelf_color']}) {detections['confidence']}"
            cv2.putText(annotated, text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)
            cv2.rectangle(annotated, (5, 5), (width-5, 60), (0, 255, 0), 2)
        
        # Vẽ YOLO detections
        for product in detections['yolo_products']:
            x1, y1, x2, y2 = product['bbox']
            conf = product['confidence']
            cv2.rectangle(annotated, (x1, y1), (x2, y2), (255, 0, 0), 2)
            label = f"Product {conf:.2f}"
            cv2.putText(annotated, label, (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)
        
        return annotated
    
    def vote_shelf_detection(self):
        """Vote các detections từ 5 frames gần nhất"""
        if len(self.frame_buffer) < 5:
            return
        
        # Count votes cho mỗi shelf
        votes = {}
        for item in self.frame_buffer:
            detection = item['detection']
            if detection['shelf_id']:
                shelf_id = detection['shelf_id']
                votes[shelf_id] = votes.get(shelf_id, 0) + 1
        
        if votes:
            # Shelf với vote nhiều nhất
            best_shelf = max(votes, key=votes.get)
            vote_count = votes[best_shelf]
            
            if vote_count >= 3:  # Cần ít nhất 3/5 votes
                confirmation = {
                    'shelf_id': best_shelf,
                    'confidence': vote_count / 5.0,
                    'robot_target': self.current_target
                }
                self.shelf_confirmed_pub.publish(String(data=json.dumps(confirmation)))
                self.get_logger().info(f"✅ Xác nhận kệ {best_shelf}: {vote_count}/5 votes")
        
        self.frame_buffer.clear()

def main(args=None):
    rclpy.init(args=args)
    node = ProductDetector()
    
    executor = MultiThreadedExecutor()
    rclpy.spin(node, executor=executor)
    
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
