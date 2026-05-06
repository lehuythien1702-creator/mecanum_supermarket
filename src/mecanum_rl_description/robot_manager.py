#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from geometry_msgs.msg import PoseStamped
from std_msgs.msg import String
from nav_msgs.msg import Odometry
from nav2_msgs.action import NavigateToPose
import json
import math
import time

class RobotState:
    IDLE = "IDLE"
    NAVIGATING = "NAVIGATING"
    AT_DESTINATION = "AT_DESTINATION"
    WAITING = "WAITING"
    RETURNING = "RETURNING"

class RobotManager(Node):
    def __init__(self):
        super().__init__('robot_manager')
        
        # --- THÔNG SỐ TRẠNG THÁI ---
        self.state = RobotState.IDLE
        self.battery = 100.0
        self.current_pos = {'x': 0.0, 'y': 0.0}
        self.current_target_name = ""
        self.eta = 0.0
        self.message = "Robot đã sẵn sàng"
        self.wait_start_time = 0.0
        
        # --- WAYPOINTS (Tọa độ) ---
        # Đã thêm offset nhỏ để robot đỗ cạnh kệ, không đâm vào kệ
        self.waypoints = {
            'A': {'x': 4.0, 'y': 6.0, 'theta': -1.57},
            'B': {'x': 4.0, 'y': 2.0, 'theta': -1.57},
            'C': {'x': 4.0, 'y': -2.0, 'theta': -1.57},
            'D': {'x': 10.0, 'y': 6.0, 'theta': -1.57},
            'E': {'x': 10.0, 'y': 2.0, 'theta': -1.57},
            'F': {'x': 10.0, 'y': -2.0, 'theta': -1.57},
            'checkout_1': {'x': 14.5, 'y': 3.0, 'theta': 0.0},
            'checkout_2': {'x': 14.5, 'y': -1.0, 'theta': 0.0},
            'home': {'x': 0.5, 'y': 0.0, 'theta': 0.0}
        }

        # --- ROS2 SETUP ---
        # Action Client cho Nav2
        self.nav_to_pose_client = ActionClient(self, NavigateToPose, 'navigate_to_pose')
        
        # Subscribers
        self.ui_sub = self.create_subscription(String, '/ui_command', self.ui_cmd_callback, 10)
        self.odom_sub = self.create_subscription(Odometry, '/odom', self.odom_callback, 10)
        
        # Publishers
        self.status_pub = self.create_publisher(String, '/robot_status', 10)
        
        # Timers
        self.create_timer(1.0, self.status_loop) # Publish status mỗi giây
        self.create_timer(0.1, self.state_machine_loop) # Xử lý logic 10Hz
        
        self.get_logger().info("🚀 Robot Manager (Nav2) đã khởi động!")

    # --- CALLBACKS ---
    def odom_callback(self, msg):
        self.current_pos['x'] = msg.pose.pose.position.x
        self.current_pos['y'] = msg.pose.pose.position.y

    def ui_cmd_callback(self, msg):
        try:
            cmd = json.loads(msg.data)
            action = cmd.get('type')
            target = cmd.get('target')

            if action == 'go_to_shelf' and target in self.waypoints:
                self.send_nav_goal(target)
            elif action == 'go_to_checkout':
                self.go_to_nearest_checkout()
            elif action == 'stop':
                self.cancel_nav_goal()
        except Exception as e:
            self.get_logger().error(f"Lỗi đọc lệnh UI: {e}")

    # --- LOGIC ĐIỀU HƯỚNG ---
    def send_nav_goal(self, target_name):
        if not self.nav_to_pose_client.wait_for_server(timeout_sec=2.0):
            self.message = "Lỗi: Nav2 Server chưa sẵn sàng!"
            return

        wp = self.waypoints[target_name]
        goal_msg = NavigateToPose.Goal()
        goal_msg.pose.header.frame_id = 'map'
        goal_msg.pose.header.stamp = self.get_clock().now().to_msg()
        goal_msg.pose.pose.position.x = wp['x']
        goal_msg.pose.pose.position.y = wp['y']
        
        # Chuyển đổi theta sang quaternion đơn giản cho trục Z
        goal_msg.pose.pose.orientation.z = math.sin(wp['theta'] / 2.0)
        goal_msg.pose.pose.orientation.w = math.cos(wp['theta'] / 2.0)

        self.current_target_name = target_name
        self.state = RobotState.NAVIGATING
        self.message = f"Đang di chuyển tới {target_name}"
        
        self._send_goal_future = self.nav_to_pose_client.send_goal_async(
            goal_msg, feedback_callback=self.nav_feedback_callback)
        self._send_goal_future.add_done_callback(self.goal_response_callback)

    def goal_response_callback(self, future):
        goal_handle = future.result()
        if not goal_handle.accepted:
            self.message = "Đường đi bị từ chối (Vật cản)!"
            self.state = RobotState.IDLE
            return

        self._get_result_future = goal_handle.get_result_async()
        self._get_result_future.add_done_callback(self.get_result_callback)

    def nav_feedback_callback(self, feedback_msg):
        feedback = feedback_msg.feedback
        self.eta = feedback.estimated_time_remaining.sec + (feedback.estimated_time_remaining.nanosec / 1e9)
        # Tốn pin khi di chuyển
        self.battery = max(0.0, self.battery - 0.05)

    def get_result_callback(self, future):
        status = future.result().status
        if status == 4: # SUCCEEDED
            self.state = RobotState.AT_DESTINATION
            self.message = f"Đã đến {self.current_target_name}. Đang đợi..."
            self.wait_start_time = time.time()
            self.eta = 0.0
        else:
            self.state = RobotState.IDLE
            self.message = "Đã hủy hoặc lỗi dẫn đường."

    def cancel_nav_goal(self):
        self.state = RobotState.IDLE
        self.message = "⛔ Đã dừng khẩn cấp!"
        self.current_target_name = ""
        self.eta = 0.0
        # Gửi request hủy tới action server (nếu đang chạy)
        # Để đơn giản, chỉ cập nhật state, Nav2 sẽ bị pre-empt nếu gửi goal mới

    def go_to_nearest_checkout(self):
        dist1 = math.hypot(self.current_pos['x'] - self.waypoints['checkout_1']['x'], 
                           self.current_pos['y'] - self.waypoints['checkout_1']['y'])
        dist2 = math.hypot(self.current_pos['x'] - self.waypoints['checkout_2']['x'], 
                           self.current_pos['y'] - self.waypoints['checkout_2']['y'])
        
        target = 'checkout_1' if dist1 < dist2 else 'checkout_2'
        self.send_nav_goal(target)

    # --- VÒNG LẶP STATE MACHINE & TRẠNG THÁI ---
    def state_machine_loop(self):
        if self.state == RobotState.AT_DESTINATION:
            # Đợi 30 giây tại kệ
            if time.time() - self.wait_start_time > 30.0:
                self.state = RobotState.WAITING
                self.message = "Đã đợi xong 30s. Quý khách muốn tiếp tục không?"

        # Tốn pin hao mòn theo thời gian
        self.battery = max(0.0, self.battery - 0.005)

    def status_loop(self):
        status_dict = {
            'state': self.state,
            'position': self.current_pos,
            'target': self.current_target_name,
            'eta': round(self.eta, 1),
            'battery': round(self.battery, 1),
            'message': self.message
        }
        msg = String()
        msg.data = json.dumps(status_dict)
        self.status_pub.publish(msg)

def main(args=None):
    rclpy.init(args=args)
    node = RobotManager()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()