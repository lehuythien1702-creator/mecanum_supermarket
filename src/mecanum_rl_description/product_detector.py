#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from std_msgs.msg import String
from cv_bridge import CvBridge
import cv2
import numpy as np
import json
import collections

# Kiểm tra xem YOLO (Ultralytics) đã được cài đặt chưa
try:
    from ultralytics import YOLO
    HAS_YOLO = True
except ImportError:
    HAS_YOLO = False

class ProductDetector(Node):
    def __init__(self):
        super().__init__('product_detector')
        
        # --- ROS2 SETUP ---
        self.bridge = CvBridge()
        
        # Subscriptions
        self.create_subscription(Image, '/camera/image_raw', self.image_callback, 10)
        self.create_subscription(String, '/robot_status', self.status_callback, 10)
        
        # Publishers
        self.annotated_pub = self.create_publisher(Image, '/camera/annotated', 10)
        self.detected_pub = self.create_publisher(String, '/detected_products', 10)
        self.confirmed_pub = self.create_publisher(String, '/shelf_confirmed', 10)

        # --- TRẠNG THÁI ROBOT ---
        self.robot_state = "IDLE"
        self.current_target = ""
        self.frame_buffer = [] # Lưu trữ 5 frame để vote
        self.is_voting = False

        # --- AI SETUP ---
        self.use_yolo = HAS_YOLO
        if self.use_yolo:
            try:
                # Cố gắng load model custom
                self.model = YOLO('models/product_yolo.pt')
                self.get_logger().info("✅ Đã load thành công custom YOLO model (models/product_yolo.pt)")
            except Exception as e:
                self.get_logger().warn(f"⚠️ Không tìm thấy custom model. Chuyển sang model mặc định yolov8n.pt: {e}")
                self.model = YOLO('yolov8n.pt') # Tự động tải nếu chưa có
        else:
            self.get_logger().warn("⚠️ Thư viện ultralytics chưa được cài đặt. Fallback: Sử dụng nhận diện màu OpenCV!")

        # --- CẤU HÌNH NHẬN DIỆN MÀU (Fallback) ---
        # Ánh xạ kệ hàng dựa vào màu sắc (HSV)
        self.color_ranges = {
            'A': {'name': 'Sữa & Nước (Đỏ)',   'lower': np.array([0, 120, 70]),   'upper': np.array([10, 255, 255])}, # Đỏ có 2 dải
            'A2':{'name': 'Sữa & Nước (Đỏ)',   'lower': np.array([170, 120, 70]), 'upper': np.array([180, 255, 255])},
            'B': {'name': 'Bánh kẹo (Xanh)',   'lower': np.array([100, 150, 0]),  'upper': np.array([140, 255, 255])},
            'C': {'name': 'Rau củ (Vàng)',     'lower': np.array([20, 100, 100]), 'upper': np.array([30, 255, 255])},
            'D': {'name': 'Thịt cá (Tím)',     'lower': np.array([130, 50, 50]),  'upper': np.array([160, 255, 255])},
            'E': {'name': 'Đồ đông lạnh (Cam)','lower': np.array([10, 100, 100]), 'upper': np.array([25, 255, 255])},
            'F': {'name': 'Hóa mỹ phẩm (Hồng)','lower': np.array([160, 50, 50]),  'upper': np.array([170, 255, 255])}
        }

        self.get_logger().info("👁️ Product Detector Node đã sẵn sàng!")

    def status_callback(self, msg):
        try:
            status = json.loads(msg.data)
            old_state = self.robot_state
            self.robot_state = status.get('state', 'IDLE')
            self.current_target = status.get('target', '')

            # Kích hoạt quá trình chụp 5 frame khi vừa đến nơi
            if self.robot_state == "AT_DESTINATION" and old_state != "AT_DESTINATION":
                self.is_voting = True
                self.frame_buffer.clear()
                self.get_logger().info("📸 Đã đến nơi! Bắt đầu chụp 5 frame để xác nhận kệ hàng...")

        except Exception as e:
            pass

    def image_callback(self, msg):
        try:
            # Chuyển đổi ảnh ROS sang OpenCV
            cv_image = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
            
            detected_items = []

            # --- BƯỚC 1 & 2: NHẬN DIỆN YOLO HOẶC MÀU ---
            if self.use_yolo:
                # Chạy YOLO
                results = self.model(cv_image, conf=0.5, verbose=False)
                for r in results:
                    boxes = r.boxes
                    for box in boxes:
                        b = box.xyxy[0].cpu().numpy().astype(int)
                        conf = float(box.conf[0])
                        cls_id = int(box.cls[0])
                        label = f"{self.model.names[cls_id]} {conf:.2f}"
                        detected_items.append(self.model.names[cls_id])
                        
                        # Vẽ Bbox
                        cv2.rectangle(cv_image, (b[0], b[1]), (b[2], b[3]), (0, 255, 0), 2)
                        cv2.putText(cv_image, label, (b[0], b[1] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
            else:
                # Fallback: Nhận diện màu sắc kệ hàng
                hsv_image = cv2.cvtColor(cv_image, cv2.COLOR_BGR2HSV)
                for shelf_id, hsv in self.color_ranges.items():
                    mask = cv2.inRange(hsv_image, hsv['lower'], hsv['upper'])
                    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                    
                    for contour in contours:
                        area = cv2.contourArea(contour)
                        if area > 3000: # Confidence dựa vào diện tích mảng màu > 3000px
                            real_id = shelf_id[0] # Lấy A từ A2
                            name = hsv['name']
                            detected_items.append(f"Kệ {real_id}")
                            
                            x, y, w, h = cv2.boundingRect(contour)
                            cv2.rectangle(cv_image, (x, y), (x+w, y+h), (255, 0, 0), 2)
                            cv2.putText(cv_image, name, (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)

            # Publish ảnh đã gắn nhãn (Annotated) cho Web UI xem
            annotated_msg = self.bridge.cv2_to_imgmsg(cv_image, encoding="bgr8")
            self.annotated_pub.publish(annotated_msg)

            # Publish danh sách đang thấy (Real-time)
            if detected_items:
                self.detected_pub.publish(String(data=json.dumps({"items": detected_items})))

            # --- BƯỚC 3: XÁC NHẬN VỊ TRÍ (VOTE 5 FRAME) ---
            if self.is_voting:
                # Gom kết quả của frame này (lấy item xuất hiện nhiều nhất trong frame)
                if detected_items:
                    most_common_in_frame = collections.Counter(detected_items).most_common(1)[0][0]
                    self.frame_buffer.append(most_common_in_frame)
                
                # Khi đủ 5 frame thì tiến hành kiểm phiếu
                if len(self.frame_buffer) >= 5:
                    final_vote = collections.Counter(self.frame_buffer).most_common(1)[0][0]
                    self.get_logger().info(f"✅ Xác nhận mục tiêu qua 5 frame: {final_vote}")
                    
                    # Publish kết quả chốt
                    confirm_msg = String()
                    confirm_msg.data = json.dumps({
                        "status": "CONFIRMED", 
                        "target": self.current_target,
                        "detected": final_vote
                    })
                    self.confirmed_pub.publish(confirm_msg)
                    
                    # Kết thúc quá trình vote
                    self.is_voting = False

        except Exception as e:
            self.get_logger().error(f"Lỗi xử lý ảnh: {e}")

def main(args=None):
    rclpy.init(args=args)
    node = ProductDetector()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()