import os
import xacro
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, TimerAction, ExecuteProcess
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory

def generate_launch_description():
    pkg_share = get_package_share_directory('mecanum_rl_description')
    xacro_file = os.path.join(pkg_share, 'urdf', 'mecanum.urdf.xacro')
    robot_description = {'robot_description': xacro.process_file(xacro_file).toxml()}
    
    gazebo = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(get_package_share_directory('gazebo_ros'), 'launch', 'gazebo.launch.py')),
        launch_arguments={'world': os.path.join(pkg_share, 'worlds', 'supermarket.world')}.items()
    )

    spawn_entity = Node(package='gazebo_ros', executable='spawn_entity.py', arguments=['-topic', 'robot_description', '-entity', 'mecanum_bot', '-z', '0.1'])
    robot_state_publisher = Node(package='robot_state_publisher', executable='robot_state_publisher', parameters=[robot_description, {'use_sim_time': True}])
    joint_spawner = Node(package='controller_manager', executable='spawner', arguments=['joint_state_broadcaster'])
    vel_spawner = Node(package='controller_manager', executable='spawner', arguments=['mecanum_base_controller'])
    
    slam_node = Node(package='slam_toolbox', executable='async_slam_toolbox_node', output='screen', parameters=[os.path.join(pkg_share, 'config', 'slam_toolbox_params.yaml'), {'use_sim_time': True}])
    teleop = ExecuteProcess(cmd=['gnome-terminal', '--', 'ros2', 'run', 'teleop_twist_keyboard', 'teleop_twist_keyboard'], output='screen')
    
    # Tự động mở luôn RViz2
    rviz2 = Node(package='rviz2', executable='rviz2', output='screen')

    return LaunchDescription([
        gazebo,
        TimerAction(period=2.0, actions=[robot_state_publisher, spawn_entity]),
        TimerAction(period=5.0, actions=[joint_spawner]),
        TimerAction(period=7.0, actions=[vel_spawner]),
        TimerAction(period=9.0, actions=[slam_node, teleop, rviz2])
    ])
