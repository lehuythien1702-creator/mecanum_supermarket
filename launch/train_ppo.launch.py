import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, TimerAction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node

def generate_launch_description():
    pkg_path = get_package_share_directory('mecanum_rl_description')
    
    # Include Gazebo launch
    gazebo_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(pkg_path, 'launch', 'mecanum_gazebo.launch.py'))
    )

    # Train Node (Chờ 5 giây để Gazebo load xong world và model)
    train_node = TimerAction(
        period=5.0,
        actions=[Node(package='mecanum_rl_description', executable='train_ppo.py', output='screen')]
    )

    return LaunchDescription([
        gazebo_launch,
        train_node
    ])