#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
from PIL import Image, ImageDraw

def create_supermarket_map():
    # --- THÔNG SỐ CẤU HÌNH ---
    resolution = 0.05  # 0.05m cho mỗi pixel
    width_m = 20.0     # Chiều dài siêu thị (X)
    height_m = 15.0    # Chiều rộng siêu thị (Y)
    
    # Tính toán kích thước pixel: 20/0.05 = 400px, 15/0.05 = 300px
    width_px = int(width_m / resolution)
    height_px = int(height_m / resolution)
    
    # Origin: Tọa độ thực (X, Y) của pixel dưới cùng bên trái bản đồ
    # Khớp với supermarket.world: X bắt đầu từ 0, Y bắt đầu từ -7.5
    origin_x = 0.0
    origin_y = -7.5

    # Tạo ảnh mới (L: 8-bit pixels, black and white)
    # 255: Trắng (Đường đi), 0: Đen (Vật cản), 205: Xám (Chưa biết)
    image = Image.new('L', (width_px, height_px), 255)
    draw = ImageDraw.Draw(image)

    def world_to_pixel(x, y):
        """Chuyển đổi tọa độ World (mét) sang tọa độ Pixel ảnh"""
        px = int((x - origin_x) / resolution)
        # Trong ảnh, y=0 là ở trên cùng, nên phải lật ngược lại
        py = height_px - int((y - origin_y) / resolution)
        return px, py

    def draw_box(center_x, center_y, size_x, size_y):
        """Vẽ một khối vật cản dựa trên tâm và kích thước"""
        x1, y1 = world_to_pixel(center_x - size_x/2, center_y + size_y/2)
        x2, y2 = world_to_pixel(center_x + size_x/2, center_y - size_y/2)
        draw.rectangle([x1, y1, x2, y2], fill=0)

    # 1. VẼ TƯỜNG BAO (Dày 0.2m)
    draw_box(10.0, 7.5, 20.0, 0.2)  # Tường Bắc
    draw_box(10.0, -7.5, 20.0, 0.2) # Tường Nam
    draw_box(20.0, 0.0, 0.2, 15.0)  # Tường Đông
    draw_box(0.0, 0.0, 0.2, 15.0)   # Tường Tây

    # 2. VẼ 6 HÀNG KỆ (4m x 0.4m)
    shelves = [
        (4.0, 5.0),   # Kệ A
        (4.0, 1.0),   # Kệ B
        (4.0, -3.0),  # Kệ C
        (10.0, 5.0),  # Kệ D
        (10.0, 1.0),  # Kệ E
        (10.0, -3.0)   # Kệ F
    ]
    for (sx, sy) in shelves:
        draw_box(sx, sy, 4.0, 0.4)

    # 3. VẼ 2 QUẦY THANH TOÁN (2m x 1m)
    draw_box(16.0, 3.0, 2.0, 1.0)
    draw_box(16.0, -1.0, 2.0, 1.0)

    # 4. VẼ KHÁCH HÀNG (Cylinders - coi như khối vuông nhỏ 0.6x0.6m)
    customers = [(7.0, 5.0), (7.0, -1.0), (13.0, 2.0)]
    for (cx, cy) in customers:
        draw_box(cx, cy, 0.6, 0.6)

    # --- LƯU FILE ---
    # Xác định đường dẫn thư mục maps
    current_dir = os.path.dirname(os.path.abspath(__file__))
    map_dir = os.path.join(os.path.dirname(current_dir), 'maps')
    if not os.path.exists(map_dir):
        os.makedirs(map_dir)

    pgm_path = os.path.join(map_dir, 'supermarket_map.pgm')
    yaml_path = os.path.join(map_dir, 'supermarket_map.yaml')

    # Lưu ảnh PGM (Binary)
    image.save(pgm_path)
    
    # Tạo file YAML
    yaml_content = f"""image: supermarket_map.pgm
mode: trinary
resolution: {resolution}
origin: [{origin_x}, {origin_y}, 0.0]
negate: 0
occupied_thresh: 0.65
free_thresh: 0.25
"""
    with open(yaml_path, 'w') as f:
        f.write(yaml_content)

    print(f"Thành công! Bản đồ đã được tạo tại: {map_dir}")

if __name__ == "__main__":
    create_supermarket_map()