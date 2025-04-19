# 🏋️ Fitness Assistant Bot

A Telegram bot that provides personalized fitness plans using GPT and machine learning models.

## 🚀 Features

- `/start`: Create your fitness profile
- `/plan`: Generate a 7-day personalized workout plan (GPT-powered)
- `/improve`: Ask GPT to improve your current plan
- `/predict`: Predict time to goal and weight change using ML
- `/profile`: Show your saved profile and current plan
- `/deleteplan`: Remove your current plan

## 🧠 ML Model

- Trained on a synthetic dataset with 450 examples
- Predicts:
  - `weeks_to_goal`
  - `kg_change`
- Model: `MultiOutputRegressor(RandomForestRegressor(n_estimators=200))`
- Stored in: `progress_predictor_extended.pkl`

## 💾 MongoDB

Stores:
- `user_profiles` (user info + last_plan)

## 📦 Files

- `main.py`: Bot logic
- `progress_predictor_extended.pkl`: Trained ML model
- `train_progress_model.py`: Script to train model
- `explore_model.py`: Script to analyze model
- `progress_dataset_extended.csv`: Training dataset

## ✅ Requirements

- `python-telegram-bot`
- `openai`
- `pymongo`
- `scikit-learn`
- `pandas`
- `joblib`
- `python-dotenv`

## ✨ How to Run

1. Set `.env` with your API keys
2. Run `main.py`
3. Interact with bot via Telegram

Made with ❤️ by Dias
