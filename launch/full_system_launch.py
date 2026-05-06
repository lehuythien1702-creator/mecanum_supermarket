#!/usr/bin/env python3
import os
import sys
import xacro
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, TimerAction, ExecuteProcess
from launch.conditions import IfCondition, UnlessCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution, TextSubstitution
from ament_index_python.packages import get_package_share_directory

def generate_launch_description():
    pkg_share = get_package_share_directory('mecanum_rl_description')

    use_slam = LaunchConfiguration('use_slam', default='false')
    world = LaunchConfiguration('world', default='supermarket')

    xacro_file = os.path.join(pkg_share, 'urdf', 'mecanum.urdf.xacro')
    robot_description = {'robot_description': xacro.process_file(xacro_file).toxml()}

    world_file = [PathJoinSubstitution([pkg_share, 'worlds', world]), TextSubstitution(text='.world')]
    map_file = os.path.join(pkg_share, 'maps', 'supermarket_map.yaml')
    slam_params = os.path.join(pkg_share, 'config', 'slam_toolbox_params.yaml')
    nav2_params = os.path.join(pkg_share, 'config', 'nav2_params.yaml')

    gazebo = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(get_package_share_directory('gazebo_ros'), 'launch', 'gazebo.launch.py')),
        launch_arguments={'world': world_file}.items()
    )

    robot_state_publisher = Node(
        package='robot_state_publisher', executable='robot_state_publisher', output='screen',
        parameters=[robot_description, {'use_sim_time': True}]
    )

    spawn_entity = Node(
        package='gazebo_ros', executable='spawn_entity.py', output='screen',
        arguments=['-topic', 'robot_description', '-entity', 'mecanum_bot', '-z', '0.1']
    )

    joint_spawner = Node(package='controller_manager', executable='spawner', output='screen', arguments=['joint_state_broadcaster'])
    velocity_spawner = Node(package='controller_manager', executable='spawner', output='screen', arguments=['mecanum_base_controller'])

    slam_node = Node(
        package='slam_toolbox', executable='async_slam_toolbox_node', output='screen', 
        parameters=[slam_params, {'use_sim_time': True}]
    )

    nav2_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(get_package_share_directory('nav2_bringup'), 'launch', 'bringup_launch.py')),
        launch_arguments={
            'map': map_file,
            'use_sim_time': 'true',
            'params_file': nav2_params,
        }.items()
    )

    robot_manager_node = Node(package='mecanum_rl_description', executable='robot_manager.py', output='screen')
    product_detector_node = Node(package='mecanum_rl_description', executable='product_detector.py', output='screen')
    web_ui_process = ExecuteProcess(cmd=[sys.executable, os.path.join(pkg_share, 'web_ui', 'app.py')], output='screen')

    return LaunchDescription([
        DeclareLaunchArgument('use_slam', default_value='false', description='Sử dụng SLAM để vẽ map khi true'),
        DeclareLaunchArgument('world', default_value='supermarket', description='Chọn world mô phỏng'),
        
        gazebo,
        TimerAction(period=2.0, actions=[robot_state_publisher, spawn_entity]),
        TimerAction(period=5.0, actions=[joint_spawner]),
        TimerAction(period=7.0, actions=[velocity_spawner]),
        TimerAction(period=8.0, actions=[slam_node], condition=IfCondition(use_slam)),
        TimerAction(period=8.0, actions=[nav2_launch], condition=UnlessCondition(use_slam)),
        TimerAction(period=10.0, actions=[robot_manager_node, product_detector_node, web_ui_process], condition=UnlessCondition(use_slam))
    ])