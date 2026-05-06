#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import threading
import base64
import cv2
import rclpy
from flask import Flask, jsonify, request, render_template
from flask_socketio import SocketIO, emit
from rclpy.node import Node
from std_msgs.msg import String
from sensor_msgs.msg import Image
from cv_bridge import CvBridge
from ament_index_python.packages import get_package_share_directory

# ==========================================
# 1. DANH MỤC SẢN PHẨM
# ==========================================
PRODUCT_CATALOG = {
    'A': [
        {'id': 'a1', 'emoji': '🥛', 'name': 'Sữa Vinamilk 500ml', 'price': 15000},
        {'id': 'a2', 'emoji': '🥛', 'name': 'TH True Milk', 'price': 18000},
        {'id': 'a3', 'emoji': '🥛', 'name': 'Sữa tươi Ba Vì', 'price': 12000}
    ],
    'B': [
        {'id': 'b1', 'emoji': '🍪', 'name': 'Bánh Oreo', 'price': 25000},
        {'id': 'b2', 'emoji': '🥮', 'name': 'Kinh Đô', 'price': 30000},
        {'id': 'b3', 'emoji': '🍘', 'name': 'Cosy', 'price': 20000}
    ],
    'C': [
        {'id': 'c1', 'emoji': '🥕', 'name': 'Cà rốt', 'price': 8000},
        {'id': 'c2', 'emoji': '🥔', 'name': 'Khoai tây', 'price': 10000},
        {'id': 'c3', 'emoji': '🥬', 'name': 'Bắp cải', 'price': 12000}
    ],
    'D': [
        {'id': 'd1', 'emoji': '🥩', 'name': 'Thịt heo', 'price': 85000},
        {'id': 'd2', 'emoji': '🐟', 'name': 'Cá hồi', 'price': 120000},
        {'id': 'd3', 'emoji': '🦐', 'name': 'Tôm', 'price': 95000}
    ],
    'E': [
        {'id': 'e1', 'emoji': '🍦', 'name': 'Kem Wall\'s', 'price': 35000},
        {'id': 'e2', 'emoji': '🌯', 'name': 'Chả giò', 'price': 45000},
        {'id': 'e3', 'emoji': '🥟', 'name': 'Há cảo', 'price': 50000}
    ],
    'F': [
        {'id': 'f1', 'emoji': '🧴', 'name': 'Dầu gội Clear', 'price': 65000},
        {'id': 'f2', 'emoji': '🧼', 'name': 'Sữa tắm Dove', 'price': 75000},
        {'id': 'f3', 'emoji': '🪥', 'name': 'Kem đánh răng', 'price': 30000}
    ]
}

# ==========================================
# 2. CẤU HÌNH FLASK & PATH
# ==========================================
try:
    pkg_share = get_package_share_directory('mecanum_rl_description')
    template_dir = os.path.join(pkg_share, 'web_ui', 'templates')
except:
    template_dir = os.path.join(os.path.dirname(__file__), 'templates')

app = Flask(__name__, template_folder=template_dir)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# ==========================================
# 3. LỚP BRIDGE KẾT NỐI ROS 2
# ==========================================
class WebUIBridge(Node):
    def __init__(self):
        super().__init__('web_ui_bridge')
        self.bridge = CvBridge()
        self.robot_status = {"status": "Sẵn sàng", "battery": 100, "state": "IDLE"}
        self.cart = []
        
        # Publishers
        self.cmd_pub = self.create_publisher(String, '/ui_command', 10)
        
        # Subscribers
        self.create_subscription(String, '/robot_status', self.status_callback, 10)
        self.create_subscription(Image, '/camera/annotated', self.camera_callback, 10)
        self.create_subscription(String, '/detected_products', self.detected_callback, 10)
        
        self.get_logger().info("✅ Web UI Bridge Online!")

    def status_callback(self, msg):
        try:
            self.robot_status = json.loads(msg.data)
            socketio.emit('robot_status', self.robot_status)
        except: pass

    def camera_callback(self, msg):
        try:
            cv_img = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
            # Nén ảnh để giảm lag màn hình đen
            _, buffer = cv2.imencode('.jpg', cv_img, [cv2.IMWRITE_JPEG_QUALITY, 40])
            jpg_as_text = base64.b64encode(buffer).decode('utf-8')
            socketio.emit('camera_frame', {'image': 'data:image/jpeg;base64,' + jpg_as_text})
        except: pass

    def detected_callback(self, msg):
        try:
            data = json.loads(msg.data)
            socketio.emit('detected_products', data)
        except: pass

    def send_command(self, cmd_type, target=None):
        msg = String()
        msg.data = json.dumps({'type': cmd_type, 'target': target})
        self.cmd_pub.publish(msg)

ros_node = None

# ==========================================
# 4. REST API ROUTES
# ==========================================
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/products')
def get_products():
    return jsonify(PRODUCT_CATALOG)

@app.route('/api/robot/status')
def get_status():
    return jsonify(ros_node.robot_status if ros_node else {})

@app.route('/api/robot/navigate', methods=['POST'])
def nav_to_shelf():
    data = request.json
    if ros_node:
        ros_node.send_command('go_to_shelf', data.get('shelf'))
        return jsonify({'status': 'success'})
    return jsonify({'status': 'error'}), 500

@app.route('/api/robot/stop', methods=['POST'])
def stop_robot():
    if ros_node:
        ros_node.send_command('stop')
        return jsonify({'status': 'success'})
    return jsonify({'status': 'error'}), 500

@app.route('/api/cart', methods=['GET'])
def get_cart():
    return jsonify(ros_node.cart if ros_node else [])

@app.route('/api/cart/add', methods=['POST'])
def add_to_cart():
    if ros_node:
        item = request.json
        ros_node.cart.append(item)
        socketio.emit('cart_updated', ros_node.cart)
        return jsonify({'status': 'success', 'cart': ros_node.cart})
    return jsonify({'status': 'error'}), 500

@app.route('/api/cart/clear', methods=['POST'])
def clear_cart():
    if ros_node:
        ros_node.cart.clear()
        socketio.emit('cart_updated', [])
        return jsonify({'status': 'success'})
    return jsonify({'status': 'error'}), 500

# ==========================================
# 5. SOCKET.IO EVENTS (FIX TYPEERROR)
# ==========================================
@socketio.on('connect')
def handle_connect():
    print("🔌 Client connected")
    if ros_node:
        emit('robot_status', ros_node.robot_status)

@socketio.on('navigate_to_shelf')
def handle_nav(data):
    if ros_node and data:
        ros_node.send_command('go_to_shelf', data.get('shelf'))

@socketio.on('emergency_stop')
def handle_stop(data=None): # Thêm data=None để sửa lỗi TypeError
    if ros_node:
        print("🚨 EMERGENCY STOP!")
        ros_node.send_command('stop')

# ==========================================
# 6. KHỞI CHẠY
# ==========================================
def main():
    global ros_node
    rclpy.init()
    ros_node = WebUIBridge()
    threading.Thread(target=lambda: rclpy.spin(ros_node), daemon=True).start()
    socketio.run(app, host='0.0.0.0', port=5000, debug=False, use_reloader=False, allow_unsafe_werkzeug=True)

if __name__ == '__main__':
    main()