#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from std_msgs.msg import String
import json

class RobotManager(Node):
    def __init__(self):
        super().__init__('robot_manager_node')
        self.create_subscription(String, '/ui_command', self.command_callback, 10)
        self.create_subscription(String, 'ui_commands', self.command_callback, 10)
        self.status_pub = self.create_publisher(String, '/robot_status', 10)
        self.cmd_vel_pub = self.create_publisher(Twist, '/cmd_vel', 10)
        self.get_logger().info("Robot Manager Node đã khởi động.")

    def publish_status(self, msg):
        status_msg = String()
        status_msg.data = msg
        self.status_pub.publish(status_msg)
        self.get_logger().info(f"Status: {msg}")

    def command_callback(self, msg):
        try:
            command = json.loads(msg.data)
            cmd_type = command.get('type')
            target = command.get('target')

            if cmd_type in ['go_to_shelf', 'go_to_checkout']:
                self.publish_status(f"🚀 Đang tiến thẳng đến {target}...")
                move_msg = Twist()
                move_msg.linear.x = 0.5
                self.cmd_vel_pub.publish(move_msg)
            elif cmd_type == 'stop':
                self.publish_status("🚨 Đã dừng khẩn cấp!")
                self.cmd_vel_pub.publish(Twist())
        except Exception as e:
            self.get_logger().error(f"Lỗi khi giải mã lệnh: {e}")

def main(args=None):
    rclpy.init(args=args)
    node = RobotManager()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
