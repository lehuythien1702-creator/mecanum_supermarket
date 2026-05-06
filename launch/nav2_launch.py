#!/usr/bin/env python3
import os
from launch import LaunchDescription
from launch.actions import TimerAction
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory

def generate_launch_description():
    pkg_dir = get_package_share_directory('mecanum_rl_description')
    nav2_config = os.path.join(pkg_dir, 'config', 'nav2_params.yaml')
    map_yaml_file = os.path.join(pkg_dir, 'maps', 'supermarket_map.yaml')
    
    # Map Server - Publish static map
    map_server = Node(
        package='nav2_map_server',
        executable='map_server',
        name='map_server',
        parameters=[{'yaml_filename': map_yaml_file, 'use_sim_time': True}],
        output='screen'
    )
    
    # AMCL Node - Localization (chủ yếu dùng lidar)
    amcl_node = Node(
        package='nav2_amcl',
        executable='amcl',
        name='amcl',
        output='screen',
        parameters=[nav2_config, {'use_sim_time': True}]
    )
    
    # Planner Server - Tìm đường
    planner_server = Node(
        package='nav2_planner',
        executable='planner_server',
        name='planner_server',
        output='screen',
        parameters=[nav2_config, {'use_sim_time': True}]
    )
    
    # Controller Server - Điều khiển robot
    controller_server = Node(
        package='nav2_controller',
        executable='controller_server',
        name='controller_server',
        output='screen',
        parameters=[nav2_config, {'use_sim_time': True}]
    )
    
    # Behavior Tree Navigator
    bt_navigator = Node(
        package='nav2_bt_navigator',
        executable='bt_navigator',
        name='bt_navigator',
        output='screen',
        parameters=[nav2_config, {'use_sim_time': True}]
    )
    
    # Lifecycle Manager (quản lý các node nav2)
    lifecycle_mgr = Node(
        package='nav2_lifecycle_manager',
        executable='lifecycle_manager',
        name='lifecycle_manager_navigation',
        output='screen',
        parameters=[
            {'use_sim_time': True},
            {'autostart': True},
            {'node_names': [
                'map_server',
                'planner_server',
                'controller_server',
                'bt_navigator',
                'amcl'
            ]}
        ]
    )
    
    # Khởi chạy tất cả nav2 nodes sau 5s để Gazebo sẵn sàng
    nav2_launch = TimerAction(
        period=5.0,
        actions=[map_server, amcl_node, planner_server, controller_server, bt_navigator, lifecycle_mgr]
    )
    
    return LaunchDescription([nav2_launch])
