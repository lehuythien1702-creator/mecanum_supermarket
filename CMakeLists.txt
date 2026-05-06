cmake_minimum_required(VERSION 3.8)
project(mecanum_rl_description)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# Tìm kiếm các package cần thiết
find_package(ament_cmake REQUIRED)
find_package(ament_cmake_python REQUIRED)
find_package(rclpy REQUIRED)
find_package(robot_state_publisher REQUIRED)
find_package(gazebo_ros REQUIRED)

# Install các module Python trong thư mục src/
ament_python_install_package(${PROJECT_NAME}
  PACKAGE_DIR src/${PROJECT_NAME}
)

# Install các script Python có thể thực thi (Executable Nodes)
install(PROGRAMS
  scripts/create_map.py
  scripts/train_ppo.py
  product_detector.py
  robot_manager.py
  web_ui/app.py
  DESTINATION lib/${PROJECT_NAME}
)

# Install các thư mục tài nguyên (Launch, config, worlds, maps, web...)
install(DIRECTORY
  launch
  config
  urdf
  worlds
  maps
  web_ui
  DESTINATION share/${PROJECT_NAME}
)

# Install file hướng dẫn
install(FILES README.md DESTINATION share/${PROJECT_NAME})

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  set(ament_cmake_copyright_FOUND TRUE)
  set(ament_cmake_cpplint_FOUND TRUE)
  ament_lint_auto_find_test_dependencies()
endif()

ament_package()