
import joblib
import pandas as pd
import matplotlib.pyplot as plt

# Загрузка модели
model = joblib.load("progress_predictor_extended.pkl")


print("\n===== Pipeline Structure =====")
print(model)


regressor = model.named_steps["regressor"].estimators_[0]  # для weeks_to_goal
feature_names = []

# Извлечение имён признаков после трансформации
preprocessor = model.named_steps["preprocessor"]
num_features = preprocessor.transformers_[0][2]
cat_features_raw = preprocessor.transformers_[1][2]
cat_encoder = preprocessor.transformers_[1][1].named_steps["onehot"]
cat_encoded = cat_encoder.get_feature_names_out(cat_features_raw)


feature_names = list(num_features) + list(cat_encoded)

# Важность признаков
importances = regressor.feature_importances_
feature_importance_df = pd.DataFrame({
    "Feature": feature_names,
    "Importance": importances
}).sort_values(by="Importance", ascending=False)

# Печать важности
print("\n===== Feature Importances (weeks_to_goal) =====")
print(feature_importance_df)

# Визуализация важности
plt.figure(figsize=(10, 6))
plt.barh(feature_importance_df["Feature"][:10][::-1], feature_importance_df["Importance"][:10][::-1])
plt.title("Top 10 Feature Importances (weeks_to_goal)")
plt.xlabel("Importance")
plt.tight_layout()
plt.show()




from sklearn.metrics import r2_score
from sklearn.model_selection import train_test_split

# Загрузка датасета, который использовался для обучения
df = pd.read_csv("progress_dataset_extended.csv")
X = df.drop(columns=["weeks_to_goal", "kg_change"])
y = df[["weeks_to_goal", "kg_change"]]


X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# Предсказание
y_pred = model.predict(X_test)
score = r2_score(y_test, y_pred, multioutput='uniform_average')

print("\\n===== Model Accuracy (R²) on test data =====")
print(f"R² Score: {score:.3f}")
