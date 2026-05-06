import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node
import xacro

def generate_launch_description():
    pkg_path = get_package_share_directory('mecanum_rl_description')
    
    # Process Xacro
    xacro_file = os.path.join(pkg_path, 'urdf', 'mecanum.urdf.xacro')
    robot_description = {'robot_description': xacro.process_file(xacro_file).toxml()}
    
    # Launch Gazebo
    world_file = os.path.join(pkg_path, 'worlds', 'supermarket.world')
    gazebo = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(get_package_share_directory('gazebo_ros'), 'launch', 'gazebo.launch.py')),
        launch_arguments={'world': world_file}.items()
    )

    # Nodes (Chỉ giữ lại State Publisher và Spawn Entity)
    node_robot_state_publisher = Node(
        package='robot_state_publisher', 
        executable='robot_state_publisher', 
        output='screen', 
        parameters=[robot_description, {"use_sim_time": True}]
    )
    
    spawn_entity = Node(
        package='gazebo_ros', 
        executable='spawn_entity.py', 
        arguments=['-topic', 'robot_description', '-entity', 'mecanum_bot'], 
        output='screen'
    )

    return LaunchDescription([
        gazebo,
        node_robot_state_publisher,
        spawn_entity
    ])