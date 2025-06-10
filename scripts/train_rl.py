"""
train_rl.py

Script to train the reinforcement learning agent that will help Benjamin decide when to
proactively intervene (e.g., remind user, suggest actions). Uses Stable-Baselines3.
"""

import os
import gym
from stable_baselines3 import PPO   # Example algorithm
from stable_baselines3.common.callbacks import CheckpointCallback

def main():
    """
    1. Define or load a custom gym.Env that simulates user-assistant interactions.
    2. Train an RL model (e.g., PPO).
    3. Save the policy under 'models/rl_policy.zip'.
    """
    # Placeholder: replace "BenjaminEnv-v0" with your actual environment
    env_id = "BenjaminEnv-v0"
    try:
        env = gym.make(env_id)
    except gym.error.Error:
        raise RuntimeError(f"Environment {env_id} not registered. Create your custom environment first.")

    model = PPO("MlpPolicy", env, verbose=1)
    checkpoint_callback = CheckpointCallback(save_freq=10000, save_path="models/",
                                             name_prefix="benjamin_rl")
    model.learn(total_timesteps=100000, callback=checkpoint_callback)
    model.save("models/rl_policy_final")
    print("RL policy training complete. Model saved at 'models/rl_policy_final.zip'.")

if __name__ == "__main__":
    main()
