#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from geometry_msgs.msg import PoseStamped
from std_msgs.msg import String
from nav2_msgs.action import NavigateToPose
import json
import math
import threading
import time

class RobotManager(Node):
    def __init__(self):
        super().__init__('robot_manager')
        
        # =======================================================
        # 1. ĐỊNH NGHĨA TỌA ĐỘ CÁC KỆ HÀNG (Khớp với World/Map)
        # =======================================================
        self.waypoints = {
            'A': {'x': 4.0, 'y': 5.0, 'yaw': 0.0},     # Mặt hướng về x+
            'B': {'x': 4.0, 'y': 1.0, 'yaw': 0.0},
            'C': {'x': 4.0, 'y': -3.0, 'yaw': 0.0},
            'D': {'x': 10.0, 'y': 5.0, 'yaw': 3.1415}, # Mặt hướng về x- (xoay lưng lại)
            'E': {'x': 10.0, 'y': 1.0, 'yaw': 3.1415},
            'F': {'x': 10.0, 'y': -3.0, 'yaw': 3.1415},
            'checkout_1': {'x': 16.0, 'y': 3.0, 'yaw': 0.0},
            'checkout_2': {'x': 16.0, 'y': -1.0, 'yaw': 0.0},
            'home': {'x': 0.5, 'y': 0.0, 'yaw': 0.0}
        }

        # =======================================================
        # 2. STATE MACHINE (Trạng thái hệ thống)
        # =======================================================
        self.state = "IDLE"
        self.current_target = None
        self.battery = 100.0
        self.message = "Robot đang chờ lệnh"
        self._action_client_future = None
        self._goal_handle = None
        
        # =======================================================
        # 3. ROS 2 INTERFACES
        # =======================================================
        # Action Client: Gửi lệnh cho Nav2
        self.nav_client = ActionClient(self, NavigateToPose, 'navigate_to_pose')
        
        # Subscriber: Nhận lệnh từ Web UI
        self.create_subscription(String, '/ui_command', self.ui_cmd_callback, 10)
        
        # Publisher: Cập nhật trạng thái liên tục lên Web UI
        self.status_pub = self.create_publisher(String, '/robot_status', 10)
        
        # Timers
        self.status_timer = self.create_timer(1.0, self.publish_status) # 1Hz
        self.battery_timer = self.create_timer(5.0, self.drain_battery)

        self.get_logger().info("🤖 Robot Manager (Nav2 Version) đã khởi động!")

    # Hàm toán học: Chuyển đổi góc Yaw (Radian) sang Quaternion (định dạng Nav2 cần)
    def get_quaternion_from_euler(self, roll, pitch, yaw):
        qx = math.sin(roll/2) * math.cos(pitch/2) * math.cos(yaw/2) - math.cos(roll/2) * math.sin(pitch/2) * math.sin(yaw/2)
        qy = math.cos(roll/2) * math.sin(pitch/2) * math.cos(yaw/2) + math.sin(roll/2) * math.cos(pitch/2) * math.sin(yaw/2)
        qz = math.cos(roll/2) * math.cos(pitch/2) * math.sin(yaw/2) - math.sin(roll/2) * math.sin(pitch/2) * math.cos(yaw/2)
        qw = math.cos(roll/2) * math.cos(pitch/2) * math.cos(yaw/2) + math.sin(roll/2) * math.sin(pitch/2) * math.sin(yaw/2)
        return [qx, qy, qz, qw]

    def drain_battery(self):
        if self.state == "NAVIGATING" and self.battery > 0:
            self.battery -= 0.2
        elif self.battery > 0:
            self.battery -= 0.05
            
    def publish_status(self):
        status_data = {
            'state': self.state,
            'target': self.current_target if self.current_target else "None",
            'battery': round(self.battery, 1),
            'message': self.message
        }
        msg = String()
        msg.data = json.dumps(status_data)
        self.status_pub.publish(msg)

    # Xử lý lệnh từ Web UI gửi xuống
    def ui_cmd_callback(self, msg):
        try:
            cmd = json.loads(msg.data)
            cmd_type = cmd.get('type')
            target = cmd.get('target')

            if cmd_type == 'go_to_shelf':
                if target in self.waypoints:
                    self.send_nav_goal(target)
                else:
                    self.message = f"Lỗi: Kệ {target} không tồn tại!"
            elif cmd_type == 'stop':
                self.cancel_nav()
        except Exception as e:
            self.get_logger().error(f"Lỗi parse lệnh UI: {e}")

    # Gửi tọa độ cho Nav2
    def send_nav_goal(self, target_name):
        if not self.nav_client.wait_for_server(timeout_sec=3.0):
            self.get_logger().error('LỖI: Nav2 Action Server không phản hồi. Bạn đã chạy Nav2 chưa?')
            self.message = "Lỗi: Nav2 chưa sẵn sàng"
            return
            
        goal_msg = NavigateToPose.Goal()
        goal_msg.pose.header.frame_id = 'map'
        goal_msg.pose.header.stamp = self.get_clock().now().to_msg()
        
        # Lấy tọa độ tương ứng với Kệ
        wp = self.waypoints[target_name]
        goal_msg.pose.pose.position.x = wp['x']
        goal_msg.pose.pose.position.y = wp['y']
        
        q = self.get_quaternion_from_euler(0, 0, wp['yaw'])
        goal_msg.pose.pose.orientation.x = q[0]
        goal_msg.pose.pose.orientation.y = q[1]
        goal_msg.pose.pose.orientation.z = q[2]
        goal_msg.pose.pose.orientation.w = q[3]

        self.get_logger().info(f"🗺️ Giao việc cho Nav2: Đi đến kệ {target_name}")
        self.state = "NAVIGATING"
        self.current_target = target_name
        self.message = f"Đang dò đường đến kệ {target_name}..."
        
        # Gửi Goal Asynchronous
        self._action_client_future = self.nav_client.send_goal_async(
            goal_msg, feedback_callback=self.feedback_callback)
        self._action_client_future.add_done_callback(self.goal_response_callback)

    # Cập nhật quãng đường còn lại từ Nav2
    def feedback_callback(self, feedback_msg):
        dist_left = feedback_msg.feedback.distance_remaining
        self.message = f"Đang đến kệ {self.current_target} (Còn {dist_left:.1f}m)"

    # Nhận phản hồi từ Nav2 xem có đồng ý đi không
    def goal_response_callback(self, future):
        self._goal_handle = future.result()
        if not self._goal_handle.accepted:
            self.get_logger().warn('Nav2 đã TỪ CHỐI đường đi này (có thể do kẹt vật cản).')
            self.state = "IDLE"
            self.message = "Lỗi: Điểm đến bị kẹt!"
            return

        self.get_logger().info('Nav2 ĐÃ CHẤP NHẬN. Bắt đầu lăn bánh!')
        self._get_result_future = self._goal_handle.get_result_async()
        self._get_result_future.add_done_callback(self.get_result_callback)

    # Khi Nav2 đi đến đích (hoặc bị hủy giữa chừng)
    def get_result_callback(self, future):
        status = future.result().status
        # Status = 4 là SUCCEEDED
        if status == 4:
            self.state = "AT_DESTINATION"
            self.message = f"✅ Đã đến kệ {self.current_target}!"
            self.get_logger().info(self.message)
            
            # Khởi động luồng phụ đếm ngược 30s chờ khách lấy hàng
            threading.Thread(target=self.wait_at_destination).start()
        else:
            self.state = "IDLE"
            self.message = "Đã hủy lệnh di chuyển."
            self.get_logger().info(self.message)

    def wait_at_destination(self):
        self.get_logger().info("⏳ Đang đợi lấy hàng (30 giây)...")
        time.sleep(30.0)
        if self.state == "AT_DESTINATION":
            self.state = "IDLE"
            self.message = "Hoàn tất lấy hàng. Chờ lệnh mới."
            self.current_target = None

    def cancel_nav(self):
        if self._goal_handle is not None and self.state == "NAVIGATING":
            self.get_logger().warn("⛔ DỪNG KHẨN CẤP: Đang hủy lệnh Nav2...")
            self._goal_handle.cancel_goal_async()
        
        self.state = "IDLE"
        self.message = "Đã dừng khẩn cấp!"

def main(args=None):
    rclpy.init(args=args)
    node = RobotManager()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()