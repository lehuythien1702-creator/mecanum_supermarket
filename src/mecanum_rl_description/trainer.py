#!/usr/bin/env python3
"""Train PPO for supermarket mecanum navigation."""

import argparse
import os

from stable_baselines3 import PPO
from stable_baselines3.common.env_checker import check_env
from stable_baselines3.common.callbacks import CheckpointCallback

from mecanum_rl_description.environment import SupermarketMecanumEnv


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--timesteps', type=int,  default=200_000)
    parser.add_argument('--save-dir',  type=str,
                        default=os.path.join(os.getcwd(), 'models'))
    parser.add_argument('--tensorboard', type=str,
                        default=os.path.join(os.getcwd(), 'tensorboard'))
    args = parser.parse_args()

    env = SupermarketMecanumEnv()
    check_env(env, warn=True)

    os.makedirs(args.save_dir,    exist_ok=True)
    os.makedirs(args.tensorboard, exist_ok=True)

    checkpoint_cb = CheckpointCallback(
        save_freq=10_000,
        save_path=args.save_dir,
        name_prefix='mecanum_ppo',
        verbose=1,
    )

    model = PPO(
        'MlpPolicy',
        env,
        verbose=1,
        tensorboard_log=args.tensorboard,
        n_steps=512,
        batch_size=64,
        n_epochs=10,
        gamma=0.99,
        gae_lambda=0.95,
        clip_range=0.2,
        ent_coef=0.005,
        learning_rate=3e-4,
    )

    model.learn(total_timesteps=args.timesteps, callback=checkpoint_cb)

    out = os.path.join(args.save_dir, 'mecanum_supermarket_ppo_final')
    model.save(out)
    print(f'✓ Model saved → {out}')
    env.close()


if __name__ == '__main__':
    main()