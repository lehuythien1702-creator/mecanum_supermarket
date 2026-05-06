#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Web UI Flask Server - Giao diện Siêu thị cho Robot
Cung cấp REST API + SocketIO real-time
"""

import os
import json
import threading
import base64
import cv2
import rclpy
from flask import Flask, jsonify, request, render_template, session
from flask_socketio import SocketIO, emit, join_room, leave_room
from rclpy.node import Node
from std_msgs.msg import String
from sensor_msgs.msg import Image
from cv_bridge import CvBridge
from ament_index_python.packages import get_package_share_directory

# ========== DANH MỤC SẢN PHẨM ==========
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

# ========== CẤU HÌNH FLASK & SOCKETIO ==========
try:
    pkg_share = get_package_share_directory('mecanum_rl_description')
    template_dir = os.path.join(pkg_share, 'web_ui', 'templates')
except:
    template_dir = os.path.join(os.path.dirname(__file__), 'templates')

app = Flask(__name__, template_folder=template_dir)
app.secret_key = 'sieuthi-robot-secret'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading', ping_timeout=60)

# ========== BRIDGE KẾT NỐI ROS2 ==========
class WebUIBridge(Node):
    def __init__(self):
        super().__init__('web_ui_node')
        
        self.bridge = CvBridge()
        self.robot_status = {
            "state": "IDLE",
            "position": {"x": 0.5, "y": 0},
            "target": None,
            "eta": 0,
            "battery": 100.0,
            "message": "🔋 Robot ở nhà, sẵn sàng"
        }
        self.cart = []
        self.detected_products = {}
        self.last_frame = None
        
        # Publishers
        self.cmd_pub = self.create_publisher(String, '/ui_command', 10)
        
        # Subscribers
        self.create_subscription(String, '/robot_status', self.status_callback, 10)
        self.create_subscription(Image, '/camera/annotated', self.camera_callback, 10)
        self.create_subscription(String, '/detected_products', self.detected_callback, 10)
        
        self.get_logger().info("✅ Web UI Bridge Online!")

    def status_callback(self, msg):
        """Nhận robot status từ robot_manager"""
        try:
            self.robot_status = json.loads(msg.data)
            socketio.emit('robot_status', self.robot_status, namespace='/')
        except Exception as e:
            self.get_logger().error(f"Status callback error: {e}")

    def camera_callback(self, msg):
        """Nhận camera frame từ product_detector"""
        try:
            cv_img = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
            self.last_frame = cv_img
            
            # Nén ảnh JPEG quality 40 để giảm bandwidth
            _, buffer = cv2.imencode('.jpg', cv_img, [cv2.IMWRITE_JPEG_QUALITY, 40])
            jpg_as_text = base64.b64encode(buffer).decode('utf-8')
            socketio.emit('camera_frame', {
                'image': 'data:image/jpeg;base64,' + jpg_as_text
            }, namespace='/')
        except Exception as e:
            self.get_logger().debug(f"Camera callback error: {e}")

    def detected_callback(self, msg):
        """Nhận detected products từ product_detector"""
        try:
            self.detected_products = json.loads(msg.data)
            socketio.emit('detected_products', self.detected_products, namespace='/')
        except:
            pass

    def send_command(self, cmd_type, target=None):
        """Gửi lệnh tới robot_manager"""
        msg = String()
        msg.data = json.dumps({'type': cmd_type, 'target': target})
        self.cmd_pub.publish(msg)

ros_node = None

# ========== REST API ENDPOINTS ==========
@app.route('/')
def index():
    """Trang chủ"""
    return render_template('index.html')

@app.route('/api/products', methods=['GET'])
def api_get_products():
    """Lấy danh sách sản phẩm"""
    return jsonify(PRODUCT_CATALOG)

@app.route('/api/robot/status', methods=['GET'])
def api_get_status():
    """Lấy trạng thái robot"""
    if ros_node:
        return jsonify(ros_node.robot_status)
    return jsonify({}), 500

@app.route('/api/robot/navigate', methods=['POST'])
def api_navigate_to_shelf():
    """Lệnh điều hướng tới kệ"""
    data = request.get_json()
    shelf = data.get('shelf') if data else None
    
    if ros_node and shelf:
        ros_node.send_command('go_to_shelf', shelf)
        return jsonify({'status': 'success', 'message': f'Điều hướng tới {shelf}'})
    
    return jsonify({'status': 'error', 'message': 'Invalid request'}), 400

@app.route('/api/robot/checkout', methods=['POST'])
def api_navigate_to_checkout():
    """Lệnh điều hướng tới quầy thanh toán"""
    if ros_node:
        ros_node.send_command('go_to_checkout')
        return jsonify({'status': 'success', 'message': 'Điều hướng tới quầy thanh toán'})
    
    return jsonify({'status': 'error'}), 500

@app.route('/api/robot/stop', methods=['POST'])
def api_stop_robot():
    """Dừng khẩn cấp"""
    if ros_node:
        ros_node.send_command('stop')
        return jsonify({'status': 'success', 'message': 'Dừng khẩn cấp!'})
    
    return jsonify({'status': 'error'}), 500

@app.route('/api/cart', methods=['GET'])
def api_get_cart():
    """Lấy giỏ hàng"""
    if ros_node:
        total_price = sum(item.get('price', 0) * item.get('quantity', 1) for item in ros_node.cart)
        return jsonify({
            'items': ros_node.cart,
            'total': total_price,
            'count': len(ros_node.cart)
        })
    return jsonify({'items': [], 'total': 0, 'count': 0})

@app.route('/api/cart/add', methods=['POST'])
def api_add_to_cart():
    """Thêm sản phẩm vào giỏ"""
    data = request.get_json()
    if ros_node and data:
        item = {
            'id': data.get('id'),
            'name': data.get('name'),
            'price': data.get('price'),
            'quantity': data.get('quantity', 1),
            'emoji': data.get('emoji')
        }
        ros_node.cart.append(item)
        socketio.emit('cart_updated', {'items': ros_node.cart}, namespace='/')
        return jsonify({'status': 'success', 'cart': ros_node.cart})
    
    return jsonify({'status': 'error'}), 400

@app.route('/api/cart/clear', methods=['POST'])
def api_clear_cart():
    """Xóa giỏ hàng"""
    if ros_node:
        ros_node.cart.clear()
        socketio.emit('cart_updated', {'items': []}, namespace='/')
        return jsonify({'status': 'success'})
    
    return jsonify({'status': 'error'}), 500

# ========== SOCKETIO EVENTS ==========
@socketio.on('connect', namespace='/')
def on_connect():
    """Khi client kết nối"""
    print("🔌 Client connected")
    if ros_node:
        emit('robot_status', ros_node.robot_status)
        emit('cart_updated', {'items': ros_node.cart})

@socketio.on('disconnect', namespace='/')
def on_disconnect():
    """Khi client ngắt kết nối"""
    print("🔌 Client disconnected")

@socketio.on('navigate_to_shelf', namespace='/')
def on_navigate_shelf(data):
    """SocketIO: Điều hướng tới kệ"""
    if ros_node:
        shelf = data.get('shelf') if isinstance(data, dict) else data
        ros_node.send_command('go_to_shelf', shelf)

@socketio.on('emergency_stop', namespace='/')
def on_emergency_stop(data=None):
    """SocketIO: Dừng khẩn cấp"""
    if ros_node:
        print("🚨 EMERGENCY STOP from WebUI!")
        ros_node.send_command('stop')

@socketio.on('add_to_cart', namespace='/')
def on_add_to_cart(data):
    """SocketIO: Thêm vào giỏ"""
    if ros_node and isinstance(data, dict):
        item = {
            'id': data.get('id'),
            'name': data.get('name'),
            'price': data.get('price'),
            'quantity': data.get('quantity', 1),
            'emoji': data.get('emoji')
        }
        ros_node.cart.append(item)
        emit('cart_updated', {'items': ros_node.cart}, broadcast=True)

# ========== KHỞI CHẠY ==========
def run_ros_spin():
    """Thread chạy rclpy.spin()"""
    rclpy.spin(ros_node)

def main():
    global ros_node
    
    print("🚀 Khởi động Web UI Server...")
    
    try:
        rclpy.init()
        ros_node = WebUIBridge()
        
        # Chạy ROS2 spin trong thread riêng
        ros_thread = threading.Thread(target=run_ros_spin, daemon=True)
        ros_thread.start()
        
        print("🌐 Flask Server chạy tại http://0.0.0.0:5000")
        print("📡 SocketIO ready for real-time updates")
        
        socketio.run(
            app,
            host='0.0.0.0',
            port=5000,
            debug=False,
            use_reloader=False,
            allow_unsafe_werkzeug=True
        )
    except KeyboardInterrupt:
        print("⛔ Shutdown Web UI Server")
        ros_node.destroy_node()
        rclpy.shutdown()
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == '__main__':
    main()
