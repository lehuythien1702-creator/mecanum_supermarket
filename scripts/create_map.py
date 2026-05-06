#!/usr/bin/env python3
import os
from PIL import Image, ImageDraw

def create_supermarket_map():
    # 1. Cấu hình thông số bản đồ
    resolution = 0.05  # 0.05 mét / 1 pixel
    width_m = 20.2     # Chiều dài siêu thị: 20m (X từ -0.1 đến 20.1)
    height_m = 15.2    # Chiều rộng siêu thị: 15m (Y từ -7.6 đến 7.6)
    
    origin_x = -0.1
    origin_y = -7.6
    
    # Tính toán kích thước ảnh (Pixels)
    img_width = int(width_m / resolution)   # 20 / 0.05 = 400 px
    img_height = int(height_m / resolution) # 15 / 0.05 = 300 px

    # Tạo ảnh trắng (254 = Không gian tự do cho robot chạy)
    # Mode 'L' là grayscale (đen trắng)
    image = Image.new('L', (img_width, img_height), color=254)
    draw = ImageDraw.Draw(image)

    # Hàm chuyển đổi tọa độ thực (m) sang tọa độ pixel trên ảnh
    def world_to_pixel(x, y):
        px_x = int((x - origin_x) / resolution)
        # Trong hệ tọa độ ảnh, Y=0 ở trên cùng, nên cần lật ngược lại
        px_y = img_height - 1 - int((y - origin_y) / resolution)
        return px_x, px_y

    # Hàm vẽ hình chữ nhật (vật cản)
    def draw_obstacle_rect(center_x, center_y, size_x, size_y):
        top_left_x = center_x - size_x / 2.0
        top_left_y = center_y + size_y / 2.0
        bottom_right_x = center_x + size_x / 2.0
        bottom_right_y = center_y - size_y / 2.0
        
        px_tl = world_to_pixel(top_left_x, top_left_y)
        px_br = world_to_pixel(bottom_right_x, bottom_right_y)
        
        # Vẽ màu đen (0 = Vật cản)
        draw.rectangle([px_tl[0], px_tl[1], px_br[0], px_br[1]], fill=0)

    # Hàm vẽ hình tròn (khách hàng)
    def draw_obstacle_circle(center_x, center_y, radius):
        px_center = world_to_pixel(center_x, center_y)
        px_radius = int(radius / resolution)
        
        bbox = [
            px_center[0] - px_radius, px_center[1] - px_radius,
            px_center[0] + px_radius, px_center[1] + px_radius
        ]
        draw.ellipse(bbox, fill=0)

    # ==========================================
    # BẮT ĐẦU VẼ BẢN ĐỒ
    # ==========================================

    # 1. Vẽ tường bao quanh (Dày 0.2m)
    draw_obstacle_rect(10.0, 7.6, 20.4, 0.2)  # Tường Bắc
    draw_obstacle_rect(10.0, -7.6, 20.4, 0.2) # Tường Nam
    draw_obstacle_rect(-0.1, 0.0, 0.2, 15.0)  # Tường Tây
    draw_obstacle_rect(20.1, 0.0, 0.2, 15.0)  # Tường Đông

    # 2. Vẽ 6 kệ hàng (4m x 0.4m)
    draw_obstacle_rect(4.0, 5.0, 4.0, 0.4)   # Kệ A
    draw_obstacle_rect(4.0, 1.0, 4.0, 0.4)   # Kệ B
    draw_obstacle_rect(4.0, -3.0, 4.0, 0.4)  # Kệ C
    draw_obstacle_rect(10.0, 5.0, 4.0, 0.4)  # Kệ D
    draw_obstacle_rect(10.0, 1.0, 4.0, 0.4)  # Kệ E
    draw_obstacle_rect(10.0, -3.0, 4.0, 0.4) # Kệ F

    # 3. Vẽ quầy thanh toán (2m x 1m)
    draw_obstacle_rect(16.0, 3.0, 2.0, 1.0)  # Quầy 1
    draw_obstacle_rect(16.0, -1.0, 2.0, 1.0) # Quầy 2

    # 4. Vẽ khách hàng tĩnh (Bán kính 0.25m)
    draw_obstacle_circle(15.0, 1.0, 0.25)
    draw_obstacle_circle(7.0, 3.0, 0.25)
    draw_obstacle_circle(10.0, -5.0, 0.25)

    # ==========================================
    # LƯU FILE
    # ==========================================
    
    # Lấy đường dẫn thư mục maps trong package
    current_dir = os.path.dirname(os.path.abspath(__file__))
    maps_dir = os.path.join(current_dir, '..', 'maps')
    os.makedirs(maps_dir, exist_ok=True)
    
    pgm_path = os.path.join(maps_dir, 'supermarket_map.pgm')
    yaml_path = os.path.join(maps_dir, 'supermarket_map.yaml')

    # Lưu ảnh PGM
    image.save(pgm_path)
    print(f"[THÀNH CÔNG] Đã tạo file bản đồ PGM: {pgm_path}")

    # Tạo nội dung file YAML
    yaml_content = f"""image: supermarket_map.pgm
mode: trinary
resolution: {resolution}
origin: [{origin_x}, {origin_y}, 0]
negate: 0
occupied_thresh: 0.65
free_thresh: 0.25
"""
    # Lưu file YAML
    with open(yaml_path, 'w') as f:
        f.write(yaml_content)
    print(f"[THÀNH CÔNG] Đã tạo file cấu hình YAML: {yaml_path}")

if __name__ == '__main__':
    create_supermarket_map()