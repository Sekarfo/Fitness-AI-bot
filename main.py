import os
import json
from dotenv import load_dotenv
import openai
from telegram import Update
from telegram.ext import (ApplicationBuilder, CommandHandler, MessageHandler,
                          ConversationHandler, filters, ContextTypes)
from pymongo import MongoClient
import signal
import asyncio
import threading

load_dotenv()

# Настройки OpenAI GPT
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MONGO_DB_URI = os.getenv("MONGO_DB_URI")

# Этапы диалога
(START, NAME, AGE, GENDER, WEIGHT, HEIGHT, FITNESS_GOAL, FITNESS_LEVEL) = range(8)

class UserProfileManager:
    client = MongoClient(MONGO_DB_URI)
    db = client['fitness_bot']
    collection = db['user_profiles']

    @classmethod
    def save_user_profile(cls, user_id, profile_data):
        cls.collection.update_one(
            {"user_id": user_id},
            {"$set": profile_data},
            upsert=True
        )

    @classmethod
    def get_user_profile(cls, user_id):
        return cls.collection.find_one({"user_id": user_id}, {"_id": 0, "user_id": 0})

class AIAssistant:
    def __init__(self):
        self.api_key = OPENAI_API_KEY

    def generate_fitness_plan(self, user_profile):
        prompt = (
            f"User Profile: {json.dumps(user_profile)}\n\n"
             "Generate a personalized workout plan based on the user's profile, fitness goal, and fitness level. for next 7 days only PLAN nothing else. and dont exceed limit  answer more than 200 words."
        )
        try:
            response = openai.ChatCompletion.create(
                model="gpt-4o",
                messages=[{"role": "system", "content": "You are a fitness expert."},
                          {"role": "user", "content": prompt}]
            )
            return response["choices"][0]["message"]["content"]
        except Exception as e:
            return f"Error: {str(e)}"

class FitnessAssistantBot:
    def __init__(self, telegram_token):
        self.application = ApplicationBuilder().token(telegram_token).build()
        self.ai_assistant = AIAssistant()
        self.setup_handlers()

    def setup_handlers(self):
        conv_handler = ConversationHandler(
            entry_points=[CommandHandler('start', self.start_profile_creation)],
            states={
                NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.collect_name)],
                AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.collect_age)],
                GENDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.collect_gender)],
                WEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.collect_weight)],
                HEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.collect_height)],
                FITNESS_GOAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.collect_fitness_goal)],
                FITNESS_LEVEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.finish_profile_creation)]
            },
            fallbacks=[CommandHandler('cancel', self.cancel_profile_creation)]
        )
        self.application.add_handler(conv_handler)
        self.application.add_handler(CommandHandler('profile', self.show_profile))
        self.application.add_handler(CommandHandler('plan', self.get_fitness_plan))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_ai_query))

    async def start_profile_creation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("Welcome! What is your name?")
        return NAME

    async def collect_name(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        context.user_data['name'] = update.message.text
        await update.message.reply_text("How old are you?")
        return AGE

    async def handle_ai_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_profile = UserProfileManager.get_user_profile(update.effective_user.id)
        if not user_profile:
            await update.message.reply_text("Create a profile first using /start.")
            return
        response = self.ai_assistant.generate_fitness_plan(user_profile, update.message.text)
        await update.message.reply_text(response)

    async def collect_age(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            age = int(update.message.text)
            if 13 <= age <= 100:
                context.user_data['age'] = age
                await update.message.reply_text("What is your gender? (Male/Female/Other)")
                return GENDER
        except ValueError:
            pass
        await update.message.reply_text("Enter a valid age between 13 and 100.")
        return AGE

    async def show_profile(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        profile = UserProfileManager.get_user_profile(update.effective_user.id)
        if profile:
            profile_text = "\n".join(f"{k.title()}: {v}" for k, v in profile.items())
            await update.message.reply_text(f"Your Profile:\n{profile_text}")
        else:
            await update.message.reply_text("No profile found. Use /start to create one.")

    async def collect_gender(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        gender = update.message.text.lower()
        if gender in ['male', 'female', 'other']:
            context.user_data['gender'] = gender
            await update.message.reply_text("What is your weight in kg?")
            return WEIGHT
        await update.message.reply_text("Enter Male, Female, or Other.")
        return GENDER

    async def collect_weight(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            weight = float(update.message.text)
            if 30 <= weight <= 300:
                context.user_data['weight'] = weight
                await update.message.reply_text("What is your height in cm?")
                return HEIGHT
        except ValueError:
            pass
        await update.message.reply_text("Enter a valid weight (30-300 kg).")
        return WEIGHT

    async def collect_height(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            height = float(update.message.text)
            if 100 <= height <= 250:
                context.user_data['height'] = height
                await update.message.reply_text("What is your fitness goal? (Weight Loss/Muscle Gain/Endurance)")
                return FITNESS_GOAL
        except ValueError:
            pass
        await update.message.reply_text("Enter a valid height (100-250 cm).")
        return HEIGHT

    async def collect_fitness_goal(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        goal = update.message.text.lower()
        if goal in ['weight loss', 'muscle gain', 'endurance']:
            context.user_data['fitness_goal'] = goal
            await update.message.reply_text("What is your fitness level? (Beginner/Intermediate/Advanced)")
            return FITNESS_LEVEL
        await update.message.reply_text("Choose: Weight Loss, Muscle Gain, or Endurance.")
        return FITNESS_GOAL

    async def get_fitness_plan(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        profile = UserProfileManager.get_user_profile(update.effective_user.id)
        if not profile:
            await update.message.reply_text("No profile found. Use /start to create one.")
            return
        plan = self.ai_assistant.generate_fitness_plan(profile)
        await update.message.reply_text(f"Your Fitness Plan:\n{plan}")

    async def finish_profile_creation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):        
        UserProfileManager.save_user_profile(update.effective_user.id, context.user_data)
        await update.message.reply_text("Profile saved! Use /plan to get a personalized fitness plan.")
        return ConversationHandler.END

    async def cancel_profile_creation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("Профиль не был сохранён. Введите /start, чтобы начать заново.")
        return ConversationHandler.END

    def run(self):
        self.application.run_polling()

    def stop(self):
        self.application.stop_polling()

if __name__ == '__main__':
    telegram_token = os.getenv("TELEGRAM_API_TOKEN")
    print("Fitness Assistant Bot") 
    FitnessAssistantBot(telegram_token).run()
    
