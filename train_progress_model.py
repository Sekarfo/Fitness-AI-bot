
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.ensemble import RandomForestRegressor
from sklearn.multioutput import MultiOutputRegressor
from sklearn.impute import SimpleImputer
import joblib

# Загрузка CSV
df = pd.read_csv("progress_dataset_extended.csv")

# Подготовка X и y
X = df.drop(columns=["weeks_to_goal", "kg_change"])
y = df[["weeks_to_goal", "kg_change"]]

# Признаки
categorical_features = ["gender", "goal", "level"]
numerical_features = [col for col in X.columns if col not in categorical_features]

# Препроцессинг
numeric_transformer = Pipeline([
    ("imputer", SimpleImputer(strategy="median")),
    ("scaler", StandardScaler())
])

categorical_transformer = Pipeline([
    ("imputer", SimpleImputer(strategy="constant", fill_value="missing")),
    ("onehot", OneHotEncoder(handle_unknown="ignore"))
])

preprocessor = ColumnTransformer([
    ("num", numeric_transformer, numerical_features),
    ("cat", categorical_transformer, categorical_features)
])

# Модель
regressor = MultiOutputRegressor(RandomForestRegressor(n_estimators=200, random_state=42))
pipeline = Pipeline([
    ("preprocessor", preprocessor),
    ("regressor", regressor)
])

# Обучение
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
pipeline.fit(X_train, y_train)

# Сохранение модели
joblib.dump(pipeline, "progress_predictor_extended.pkl")
print("✅ Model saved to progress_predictor_extended.pkl")
