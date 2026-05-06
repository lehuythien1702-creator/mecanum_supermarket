#!/usr/bin/env python3
import rclpy
from rclpy.node import Node

class ProductDetector(Node):
    def __init__(self):
        super().__init__('product_detector_node')
        self.get_logger().info("Product Detector đã khởi động.")

def main(args=None):
    rclpy.init(args=args)
    node = ProductDetector()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
