# mecanum_rl_description

ROS2 Humble package mô phỏng robot mecanum trong siêu thị với Gazebo Classic 11, SLAM, Nav2 và Web UI.

## Yêu cầu
- ROS2 Humble
- Python 3.10
- Gazebo Classic 11
- `ros-humble-nav2-bringup`, `ros-humble-slam-toolbox`, `ros-humble-cv-bridge`, `ros-humble-image-transport`, `ros-humble-teleop-twist-keyboard`
- `pip install ultralytics flask flask-socketio python-socketio pillow`

## Cài đặt
```bash
cd ~/amr_ws
source /opt/ros/humble/setup.bash
rosdep install --from-paths src --ignore-src -r -y
colcon build --packages-select mecanum_rl_description
source install/setup.bash
```

## Tạo bản đồ từ world
```bash
ros2 run mecanum_rl_description create_map.py
```
Bản đồ sẽ được lưu tại `maps/supermarket_map.pgm` và `maps/supermarket_map.yaml`.

## Chạy hệ thống đầy đủ
```bash
ros2 launch mecanum_rl_description full_system_launch.py use_slam:=false world:=supermarket
```
Sau khi khởi động, mở Web UI tại http://localhost:5000

## Chạy SLAM để tạo bản đồ
```bash
ros2 launch mecanum_rl_description mapping_launch.py
```
Sau khi lái robot đi khắp siêu thị bằng `teleop_twist_keyboard`, lưu bản đồ:
```bash
ros2 run nav2_map_server map_saver_cli -f maps/supermarket_map
```

## Web UI
- Tab `Mua Hàng`: thêm giỏ, tìm kiếm, điều hướng tới kệ.
- Tab `Theo Dõi Robot`: bản đồ SVG, trạng thái, camera feed, log, nút dừng khẩn cấp.
- Tab `Thanh Toán`: hiển thị giỏ hàng, quầy thanh toán, QR code giả lập.

## Tùy chọn YOLO
Nếu cài `ultralytics` và đặt model tại `models/product_yolo.pt`, `product_detector.py` sẽ dùng YOLOv8n.
Nếu không có YOLO, node sẽ fallback sang nhận diện màu kệ bằng OpenCV.

## Ghi chú
- Tất cả coordinate trong `worlds/supermarket.world` khớp với waypoints trong `robot_manager.py`.
- `use_slam:=false` sẽ dùng bản đồ tĩnh trong `maps/supermarket_map.yaml`.
- `use_slam:=true` sẽ chạy SLAM online với `slam_toolbox`.
