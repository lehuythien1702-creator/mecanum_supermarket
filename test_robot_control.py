#!/usr/bin/env python3
"""Test script để verify Robot Manager nhận lệnh từ Web UI"""
import rclpy
from std_msgs.msg import String
import json
import time

def test_send_command():
    rclpy.init()
    node = rclpy.create_node('test_robot_control')
    
    # Tạo publisher để gửi lệnh (giả lập Web UI)
    pub = node.create_publisher(String, '/ui_command', 10)
    
    # Tạo subscriber để lắng nghe trạng thái robot
    status_received = []
    def status_callback(msg):
        status_received.append(msg.data)
        print(f"✓ Robot Status: {msg.data}")
    
    sub = node.create_subscription(String, '/robot_status', status_callback, 10)
    
    time.sleep(1)  # Chờ subscriber sẵn sàng
    
    # Test 1: Gửi lệnh đi tới Kệ A
    print("\n=== TEST 1: Gửi lệnh đi tới Kệ A ===")
    cmd = json.dumps({"type": "go_to_shelf", "target": "A"})
    msg = String()
    msg.data = cmd
    pub.publish(msg)
    print(f"Sent: {cmd}")
    
    # Chờ nhận response
    time.sleep(3)
    
    if status_received:
        print(f"✓ Robot Manager nhận được lệnh!\n")
    else:
        print(f"✗ Không nhận response từ Robot Manager\n")
    
    # Test 2: Gửi lệnh dừng
    print("\n=== TEST 2: Gửi lệnh dừng ===")
    cmd = json.dumps({"type": "stop", "target": "all"})
    msg = String()
    msg.data = cmd
    pub.publish(msg)
    print(f"Sent: {cmd}")
    
    time.sleep(2)
    
    rclpy.shutdown()
    print("\n✓ Test hoàn thành!")

if __name__ == '__main__':
    test_send_command()
