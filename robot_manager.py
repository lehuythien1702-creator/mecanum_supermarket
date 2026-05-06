#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Robot Manager Node - Điều phối robot tới các kệ hàng và quầy thanh toán
Sử dụng Nav2 NavigateToPose action client để điều hướng
"""

import rclpy
import json
import math
import threading
import time
from rclpy.node import Node
from rclpy.action import ActionClient
from rclpy.executors import MultiThreadedExecutor
from geometry_msgs.msg import PoseStamped, Point
from nav2_msgs.action import NavigateToPose
from nav_msgs.msg import Odometry
from std_msgs.msg import String
from datetime import datetime

# ========== ĐỊNH NGHĨA WAYPOINTS ==========
WAYPOINTS = {
    'shelf_A': (4.0, 5.0),
    'shelf_B': (4.0, 1.0),
    'shelf_C': (4.0, -3.0),
    'shelf_D': (10.0, 5.0),
    'shelf_E': (10.0, 1.0),
    'shelf_F': (10.0, -3.0),
    'checkout_1': (16.0, 3.0),
    'checkout_2': (16.0, -1.0),
    'home': (0.5, 0.0),
}

class RobotManager(Node):
    def __init__(self):
        super().__init__('robot_manager_node')
        
        self.get_logger().info("🚀 Robot Manager Node khởi động...")
        
        # ========== STATE MACHINE ==========
        self.state = "IDLE"  # IDLE, NAVIGATING, AT_DESTINATION, WAITING, RETURNING
        self.current_target = None
        self.current_pose = None
        self.battery_level = 100.0
        self.navigation_start_time = None
        self.destination_arrival_time = None
        self.eta = 0
        
        # ========== PUBLISHERS ==========
        self.status_pub = self.create_publisher(String, '/robot_status', 10)
        
        # ========== SUBSCRIBERS ==========
        self.create_subscription(String, '/ui_command', self.ui_command_callback, 10)
        self.create_subscription(Odometry, '/odom', self.odom_callback, 10)
        
        # ========== NAV2 ACTION CLIENT ==========
        self.nav_to_pose_client = ActionClient(self, NavigateToPose, 'navigate_to_pose')
        self.current_goal_handle = None
        self.nav_goal_result = None
        
        # ========== TIMERS ==========
        self.create_timer(0.1, self.battery_timer_callback)  # Giảm battery 0.001%/0.1s = 0.01%/s
        self.create_timer(1.0, self.status_publish_callback)  # Publish status mỗi 1s
        self.create_timer(30.0, self.waiting_timeout_callback)  # Timeout chờ sau 30s
        
        self.get_logger().info("✅ Robot Manager Node sẵn sàng!")
    
    # ========== CALLBACKS ==========
    def ui_command_callback(self, msg):
        """Nhận lệnh từ Web UI"""
        try:
            command = json.loads(msg.data)
            cmd_type = command.get('type')
            target = command.get('target')
            
            if cmd_type == 'go_to_shelf':
                self.navigate_to_shelf(target)
            elif cmd_type == 'go_to_checkout':
                self.navigate_to_checkout()
            elif cmd_type == 'stop':
                self.stop_robot()
            elif cmd_type == 'continue':
                self.continue_navigation()
                
        except json.JSONDecodeError as e:
            self.get_logger().error(f"❌ Lỗi JSON: {e}")
    
    def odom_callback(self, msg):
        """Cập nhật vị trí robot từ /odom"""
        self.current_pose = {
            'x': msg.pose.pose.position.x,
            'y': msg.pose.pose.position.y,
            'theta': self.get_yaw_from_quaternion(msg.pose.pose.orientation)
        }
    
    def battery_timer_callback(self):
        """Giảm battery dần"""
        if self.state != "IDLE":
            # Giảm 0.001% cho mỗi lần gọi (0.1s)
            self.battery_level -= 0.001
            self.battery_level = max(0.0, min(100.0, self.battery_level))
    
    def status_publish_callback(self):
        """Publish trạng thái robot mỗi giây"""
        status = {
            'state': self.state,
            'position': self.current_pose if self.current_pose else {'x': 0, 'y': 0, 'theta': 0},
            'target': self.current_target,
            'eta': self.eta,
            'battery': round(self.battery_level, 2),
            'message': self.get_status_message()
        }
        msg = String()
        msg.data = json.dumps(status)
        self.status_pub.publish(msg)
    
    def waiting_timeout_callback(self):
        """Timeout khi ở AT_DESTINATION"""
        if self.state == "AT_DESTINATION":
            if self.destination_arrival_time is None:
                self.destination_arrival_time = time.time()
            elif time.time() - self.destination_arrival_time > 30:
                # Hỏi người dùng tiếp tục không
                self.get_logger().info("❓ Hỏi người dùng tiếp tục không?")
                self.destination_arrival_time = time.time()  # Reset timer
    
    # ========== NAVIGATION METHODS ==========
    def navigate_to_shelf(self, shelf_id):
        """Điều hướng tới một kệ hàng"""
        if shelf_id not in WAYPOINTS:
            self.get_logger().error(f"❌ Kệ hàng không tồn tại: {shelf_id}")
            return
        
        if self.state == "NAVIGATING":
            self.get_logger().warn("⚠️ Robot đang di chuyển, hãy chờ...")
            return
        
        self.current_target = shelf_id
        self.state = "NAVIGATING"
        self.navigation_start_time = time.time()
        
        target_pos = WAYPOINTS[shelf_id]
        self.send_nav_goal(target_pos[0], target_pos[1])
        
        self.get_logger().info(f"🚀 Điều hướng tới {shelf_id} ({target_pos[0]}, {target_pos[1]})")
    
    def navigate_to_checkout(self):
        """Điều hướng tới quầy thanh toán gần nhất"""
        if self.current_pose is None:
            self.get_logger().error("❌ Không biết vị trí robot")
            return
        
        # Tìm quầy thanh toán gần nhất
        dist_to_c1 = math.dist(
            (self.current_pose['x'], self.current_pose['y']),
            WAYPOINTS['checkout_1']
        )
        dist_to_c2 = math.dist(
            (self.current_pose['x'], self.current_pose['y']),
            WAYPOINTS['checkout_2']
        )
        
        if dist_to_c1 < dist_to_c2:
            checkout = 'checkout_1'
        else:
            checkout = 'checkout_2'
        
        self.navigate_to_shelf(checkout)
    
    def send_nav_goal(self, x, y):
        """Gửi goal tới Nav2 NavigateToPose action"""
        # Đợi action server sẵn sàng
        if not self.nav_to_pose_client.wait_for_server(timeout_sec=2.0):
            self.get_logger().error("❌ Nav2 Action Server không sẵn sàng")
            return
        
        # Tạo goal
        goal_msg = NavigateToPose.Goal()
        goal_msg.pose.header.frame_id = 'map'
        goal_msg.pose.header.stamp = self.get_clock().now().to_msg()
        goal_msg.pose.pose.position.x = float(x)
        goal_msg.pose.pose.position.y = float(y)
        goal_msg.pose.pose.orientation.w = 1.0  # Hướng mặc định
        
        # Gửi goal async
        self.nav_to_pose_client.send_goal_async(goal_msg, feedback_callback=self.nav_feedback_callback)
    
    def nav_feedback_callback(self, feedback_msg):
        """Nhận feedback từ Nav2"""
        estimated_time_remaining = feedback_msg.feedback.estimated_time_remaining.sec
        self.eta = estimated_time_remaining
    
    def stop_robot(self):
        """Dừng robot khẩn cấp"""
        self.get_logger().warn("🛑 Dừng robot khẩn cấp!")
        
        # Cancel goal hiện tại
        if self.current_goal_handle is not None:
            self.nav_to_pose_client.cancel_goal_async(self.current_goal_handle)
        
        self.state = "IDLE"
        self.current_target = None
    
    def continue_navigation(self):
        """Tiếp tục di chuyển"""
        if self.state == "AT_DESTINATION":
            # Quay về home
            self.state = "RETURNING"
            self.navigate_to_shelf('home')
    
    # ========== HELPER METHODS ==========
    def get_yaw_from_quaternion(self, quaternion):
        """Chuyển quaternion thành yaw angle"""
        import math
        x, y, z, w = quaternion.x, quaternion.y, quaternion.z, quaternion.w
        yaw = math.atan2(2.0 * (w * z + x * y), 1.0 - 2.0 * (y * y + z * z))
        return yaw
    
    def get_status_message(self):
        """Lấy tin nhắn trạng thái con người"""
        messages = {
            'IDLE': "🔋 Robot ở nhà, sẵn sàng",
            'NAVIGATING': f"🚀 Đang di chuyển tới {self.current_target}",
            'AT_DESTINATION': f"✅ Đã tới {self.current_target}",
            'WAITING': "⏸️ Đang chờ...",
            'RETURNING': "🏠 Đang quay về nhà"
        }
        return messages.get(self.state, "❓ Trạng thái không xác định")

def main(args=None):
    rclpy.init(args=args)
    node = RobotManager()
    
    # Dùng MultiThreadedExecutor để xử lý async action callbacks
    executor = MultiThreadedExecutor()
    rclpy.spin(node, executor=executor)
    
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
