#!/usr/bin/env python3
import rclpy
import threading
from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import CheckpointCallback
from mecanum_rl_description.environment import SupermarketEnv

def spin_ros(node):
    rclpy.spin(node)

def main():
    rclpy.init()
    env = SupermarketEnv()
    
    # Chạy ROS2 spin trong thread riêng để không block Gym
    spin_thread = threading.Thread(target=spin_ros, args=(env,))
    spin_thread.start()

    checkpoint_callback = CheckpointCallback(save_freq=10000, save_path='./models/', name_prefix='mecanum_ppo')

    model = PPO("MlpPolicy", env, verbose=1, tensorboard_log="./tensorboard/")
    print("Bắt đầu huấn luyện PPO trong siêu thị...")
    
    try:
        model.learn(total_timesteps=100000, callback=checkpoint_callback)
        model.save("models/mecanum_ppo_final")
    except KeyboardInterrupt:
        print("Đã dừng huấn luyện.")
    finally:
        env.destroy_node()
        rclpy.shutdown()
        spin_thread.join()

if __name__ == '__main__':
    main()