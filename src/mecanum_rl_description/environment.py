import rclpy
from rclpy.node import Node
import gymnasium as gym
from gymnasium import spaces
import numpy as np
from sensor_msgs.msg import LaserScan
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
import math
import time

class SupermarketEnv(gym.Env, Node):
    def __init__(self):
        super().__init__('rl_environment_node')
        gym.Env.__init__(self)
        
        # ROS2 Setup - Update topics for Planar Move
        self.cmd_vel_pub = self.create_publisher(Twist, '/cmd_vel', 10)
        self.scan_sub = self.create_subscription(LaserScan, '/scan', self.scan_callback, 10)
        self.odom_sub = self.create_subscription(Odometry, '/odom', self.odom_callback, 10)
        
        self.scan_data = np.ones(360) * 6.0
        self.robot_pose = [0.0, 0.0]
        
        # Multi-goal (1: Kệ hàng, 2: Quầy thanh toán)
        self.goals = [[-2.0, 1.0], [3.0, -1.0]]
        self.current_goal_idx = 0
        
        # Gymnasium Spaces (360 lidar + 2 coords goal + 1 phase = 363)
        self.observation_space = spaces.Box(low=-np.inf, high=np.inf, shape=(363,), dtype=np.float32)
        # Action: vx, vy, omega
        self.action_space = spaces.Box(low=np.array([-0.5, -0.5, -1.0]), high=np.array([0.5, 0.5, 1.0]), dtype=np.float32)

    def scan_callback(self, msg):
        ranges = np.array(msg.ranges)
        ranges[np.isinf(ranges)] = 6.0
        self.scan_data = ranges

    def odom_callback(self, msg):
        self.robot_pose[0] = msg.pose.pose.position.x
        self.robot_pose[1] = msg.pose.pose.position.y

    def get_observation(self):
        goal = self.goals[self.current_goal_idx]
        obs = np.concatenate((self.scan_data, goal, [self.current_goal_idx])).astype(np.float32)
        return obs

    def step(self, action):
        # Publish action
        twist = Twist()
        twist.linear.x = float(action[0])
        twist.linear.y = float(action[1]) # Mecanum strafing
        twist.angular.z = float(action[2])
        self.cmd_vel_pub.publish(twist)
        
        # Wait a bit for physics simulation
        rclpy.spin_once(self, timeout_sec=0.1)
        
        # Calculate Reward
        goal = self.goals[self.current_goal_idx]
        dist_to_goal = math.hypot(goal[0] - self.robot_pose[0], goal[1] - self.robot_pose[1])
        
        reward = -0.01 # Time penalty
        done = False
        truncated = False
        
        min_lidar = np.min(self.scan_data)
        
        if min_lidar < 0.18: # Va chạm
            reward -= 100.0
            done = True
        elif min_lidar < 0.5: # Social Penalty (Đi quá gần khách)
            reward -= 0.5
            
        if dist_to_goal < 0.5: # Đạt mục tiêu
            reward += 100.0
            if self.current_goal_idx < len(self.goals) - 1:
                self.current_goal_idx += 1 # Đổi sang goal tiếp theo
            else:
                done = True # Xong kịch bản
                
        return self.get_observation(), reward, done, truncated, {}

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self.current_goal_idx = 0
        twist = Twist()
        self.cmd_vel_pub.publish(twist) # Stop robot
        time.sleep(0.5)
        rclpy.spin_once(self, timeout_sec=0.1)
        return self.get_observation(), {}