import os
import json
from dotenv import load_dotenv
import openai
from telegram import Update
import joblib
import pandas as pd
from telegram.ext import (ApplicationBuilder, CommandHandler, MessageHandler,
                          ConversationHandler, filters, ContextTypes)
from pymongo import MongoClient
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

progress_model = joblib.load("progress_predictor_extended.pkl")
load_dotenv()


OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MONGO_DB_URI = os.getenv("MONGO_DB_URI")

(START, NAME, AGE, GENDER, WEIGHT, HEIGHT, FITNESS_GOAL, FITNESS_LEVEL, IMPROVE_REQUEST, EDIT_PLAN) = range(10)
(PREDICT_SESSIONS, PREDICT_DURATION, PREDICT_SLEEP, PREDICT_DIET, PREDICT_BREAKS, PREDICT_CONSISTENCY) = range(100, 106)


class UserProfileManager:
    import logging
    logger = logging.getLogger(__name__)

    client = MongoClient(MONGO_DB_URI)
    db = client['fitness_bot']
    collection = db['user_profiles']

    @classmethod
    def save_user_profile(cls, user_id, profile_data):
    # Убеждаемся, что user_id записан в профиль
        profile_data["user_id"] = user_id

        result = cls.collection.update_one(
            {"user_id": user_id},
            {"$set": profile_data},
            upsert=True
        )

        if result.modified_count > 0 or result.upserted_id:
            logger.info(f"[✅] Profile saved for user_id: {user_id}")
        else:
            logger.warning(f"[⚠️] Profile save attempted but no changes for user_id: {user_id}")

    @classmethod
    def get_user_profile(cls, user_id):
        return cls.collection.find_one({"user_id": user_id}, {"_id": 0, "user_id": 0})
    
    @classmethod
    def save_user_plan(cls, user_id, plan):
        logger.info(f"[🔍] About to save plan:\n{plan[:100]}...") 
        result = cls.collection.update_one(
        {"user_id": user_id},
        {"$set": {"last_plan": plan}},
            upsert=False  
        )

        if result.modified_count > 0:
            logger.info(f"[✅] Plan updated for user_id: {user_id}")
        else:
            logger.error(f"[❌] Plan NOT updated — user_id not found: {user_id}")

    @classmethod
    def delete_user_plan(cls, user_id):
        cls.collection.update_one(
            {"user_id": user_id},
            {"$unset": {"last_plan": ""}}
        )


class AIAssistant:
    def __init__(self):
        self.api_key = OPENAI_API_KEY

    def generate_fitness_plan(self, user_profile, ):
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
            FITNESS_LEVEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.collect_fitness_level)],
            },
            fallbacks=[CommandHandler('cancel', self.cancel_profile_creation)]
            )

        predict_conv = ConversationHandler(
            entry_points=[CommandHandler("predict", self.predict_entry)],
            states={
            PREDICT_SESSIONS: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.get_sessions)],
            PREDICT_DURATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.get_duration)],
            PREDICT_SLEEP: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.get_sleep)],
            PREDICT_DIET: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.get_diet)],
            PREDICT_BREAKS: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.get_breaks)],
            PREDICT_CONSISTENCY: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.get_consistency)],
            },
            fallbacks=[CommandHandler("cancel", self.cancel_profile_creation)]
        )

        improve_conv = ConversationHandler(
            entry_points=[CommandHandler("improve", self.improve_plan)],
            states={
                IMPROVE_REQUEST: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.process_improvement)]
            },
            fallbacks=[CommandHandler("cancel", self.cancel_profile_creation)]
        )

        self.application.add_handler(predict_conv)
        self.application.add_handler(improve_conv) 
        self.application.add_handler(conv_handler)
        self.application.add_handler(CommandHandler('profile', self.show_profile))
        self.application.add_handler(CommandHandler('plan', self.get_fitness_plan))
        self.application.add_handler(CommandHandler('deleteplan', self.delete_plan))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.unknown_message))


        
    async def unknown_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("❗ I didn't understand that. Please use commands like /start or /plan.")



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
        response = self.ai_assistant.generate_fitness_plan(user_profile)
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
            profile_text = "\n".join(
                f"{k.title().replace('_', ' ')}: {v}" for k, v in profile.items() if k != "last_plan"
            )
            plan = profile.get("last_plan")
            if plan:
                profile_text += f"\n\n📋 Your Plan:\n{plan}"
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
    
    async def collect_fitness_level(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        level = update.message.text.lower()
        if level in ["beginner", "intermediate", "advanced"]:
            context.user_data["fitness_level"] = level
            UserProfileManager.save_user_profile(update.effective_user.id, context.user_data)
            await update.message.reply_text(" Profile saved! Use /plan to get your personalized plan.")
            return ConversationHandler.END
        await update.message.reply_text("Please choose: Beginner, Intermediate or Advanced.")
        return FITNESS_LEVEL


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
        if "last_plan" in profile:
            await update.message.reply_text(
                "You already have a fitness plan.\nUse /improve to enhance it or /deleteplan to start over."
            )
            return
        plan = self.ai_assistant.generate_fitness_plan(profile)
        UserProfileManager.save_user_plan(update.effective_user.id, plan)
        await update.message.reply_text(f"Your Fitness Plan:\n{plan}")


    async def improve_plan(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        profile = UserProfileManager.get_user_profile(update.effective_user.id)
        if not profile or "last_plan" not in profile:
            await update.message.reply_text("You don't have a saved plan. Use /plan first.")
            return ConversationHandler.END
        await update.message.reply_text("How would you like to improve your current plan? (e.g., make it easier, add more cardio)")
        return IMPROVE_REQUEST

    async def process_improvement(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            profile = UserProfileManager.get_user_profile(update.effective_user.id)
            request = update.message.text
            prompt = (
            f"User profile: {json.dumps(profile)}\n\n"
            f"Current plan: {profile.get('last_plan', '')}\n\n"
            f"User wants to improve the plan as follows: {request}\n\n"
            "Please provide an improved version of the plan only. Keep it under 200 words."
            )

            response = openai.ChatCompletion.create(
                model="gpt-4o",
                messages=[
                 {"role": "system", "content": "You are a fitness expert."},
                    {"role": "user", "content": prompt}
                ]
            )
           

            improved_plan = response["choices"][0]["message"]["content"]
            
            UserProfileManager.save_user_plan(update.effective_user.id, improved_plan)
            logger.info(f"[DEBUG] Plan updated for user {update.effective_user.id}")
            logger.debug(f"[GPT response]: {response}")
            await update.message.reply_text(f"✅ Updated Plan:\n{improved_plan}")

        except Exception as e:
            print(f"[ERROR] GPT or DB issue: {str(e)}")
            await update.message.reply_text(f"Error improving plan: {str(e)}")
        return ConversationHandler.END

    

    async def delete_plan(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        profile = UserProfileManager.get_user_profile(update.effective_user.id)
        if not profile or "last_plan" not in profile:
            await update.message.reply_text("No saved plan found.")
            return
        UserProfileManager.delete_user_plan(update.effective_user.id)
        await update.message.reply_text("✅ Your fitness plan has been deleted. Use /plan to create a new one.")

    async def predict_entry(self, update, context):
        profile = UserProfileManager.get_user_profile(update.effective_user.id)
        if not profile:
            await update.message.reply_text("You need a profile first. Use /start.")
            return ConversationHandler.END
        context.user_data["predict_profile"] = profile
        await update.message.reply_text("How many sessions per week do you plan?")
        return PREDICT_SESSIONS
    
    async def get_sessions(self, update, context):
        context.user_data["sessions_per_week"] = int(update.message.text)
        await update.message.reply_text("How many minutes is each session?")
        return PREDICT_DURATION

    async def get_duration(self, update, context):
        context.user_data["session_duration_minutes"] = int(update.message.text)
        await update.message.reply_text("How many hours do you sleep per day?")
        return PREDICT_SLEEP

    async def get_sleep(self, update, context):
        context.user_data["sleep_hours"] = float(update.message.text)
        await update.message.reply_text("Do you follow a diet? (yes/no)")
        return PREDICT_DIET

    async def get_diet(self, update, context):
        context.user_data["diet_followed"] = update.message.text.lower() in ["yes", "y"]
        await update.message.reply_text("Did you have breaks or restrictions? (yes/no)")
        return PREDICT_BREAKS

    async def get_breaks(self, update, context):
        context.user_data["restrictions_or_breaks"] = update.message.text.lower() in ["yes", "y"]
        await update.message.reply_text("How consistent are you? (0–100%)")
        return PREDICT_CONSISTENCY

    async def get_consistency(self, update, context):
        context.user_data["consistency_percent"] = float(update.message.text)

    # Сбор профиля
        p = context.user_data["predict_profile"]
        x = pd.DataFrame([{
            "age": p["age"],
            "weight_start": p["weight"],
            "height": p["height"],
            "gender": p["gender"],
            "goal": p["fitness_goal"].strip().lower().replace(" ", "_"),
            "level": p["fitness_level"],
            "sessions_per_week": context.user_data["sessions_per_week"],
            "session_duration_minutes": context.user_data["session_duration_minutes"],
            "sleep_hours": context.user_data["sleep_hours"],
            "diet_followed": context.user_data["diet_followed"],
            "restrictions_or_breaks": context.user_data["restrictions_or_breaks"],
            "consistency_percent": context.user_data["consistency_percent"]
        }])
        print("INPUT TO MODEL:", x.to_dict(orient="records")[0])
        prediction = progress_model.predict(x)[0]
        weeks, kg = round(prediction[0], 1), round(prediction[1], 1)

        await update.message.reply_text(f"📊 Predicted time to goal: {weeks} weeks\n⚖️ Expected weight change: {kg} kg")
        return ConversationHandler.END





    


    async def finish_profile_creation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):        
        UserProfileManager.save_user_profile(update.effective_user.id, context.user_data)
        await update.message.reply_text("Profile saved! Use /plan to get a personalized fitness plan.")
        return ConversationHandler.END

    async def cancel_profile_creation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("Canceled conversation and profile creation.")
        return ConversationHandler.END

    def run(self):
        self.application.run_polling()

    def stop(self):
        self.application.stop_polling()

if __name__ == '__main__':
    telegram_token = os.getenv("TELEGRAM_API_TOKEN")
    print("Fitness Assistant Bot") 
    FitnessAssistantBot(telegram_token).run()
    
