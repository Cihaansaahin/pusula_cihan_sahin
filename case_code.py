# ==============================================================
# PUSULA / Talent_Academy_Case_DT_2025 - E2E (Eksikler Eklenmiş)
# - Veri yükleme
# - Sayısal dönüşümler
# - Eksik veri görselleştirme (savefig)
# - Multi-label One-Hot (get_dummies, hızlı)
# - Eksik değer doldurma (kategorik=mod, sayısal=median)
# - Kategorik dağılım grafikleri (savefig)
# - Temiz veri kaydı (csv/xlsx)
# - Baseline model (RF) + Feature Importance grafiği (savefig)
# ==============================================================

import os, sys, re
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error
from sklearn.ensemble import RandomForestRegressor

# --------------------------------------------------------------
# Klasörler
# --------------------------------------------------------------
BASE_DIR = os.path.abspath(".")
DATA_DIR = os.path.join(BASE_DIR, "data")
OUT_DIR  = os.path.join(BASE_DIR, "outputs")
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(OUT_DIR, exist_ok=True)

# --------------------------------------------------------------
# (Opsiyonel) Windows UTF-8 ve font
# --------------------------------------------------------------
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass
try:
    os.system("chcp 65001 >NUL")
except Exception:
    pass
plt.rcParams["font.family"] = "DejaVu Sans"



file_in_repo = os.path.join(DATA_DIR, "Talent_Academy_Case_DT_2025.xlsx")
if os.path.exists(file_in_repo):
    df = pd.read_excel(file_in_repo)
else:
    # Alternatif: mutlak yol ile oku
    abs_path = r"C:\Users\cihan\OneDrive\Masaüstü\pusula_cihan_şahin\Talent_Academy_Case_DT_2025.xlsx"
    if os.path.exists(abs_path):
        df = pd.read_excel(abs_path)
    else:
        raise FileNotFoundError("Veri dosyası bulunamadı. data/ klasörüne veya belirtilen absolute path'e kopyalayın.")


print("İlk 5 satır:")
print(df.head())
print("\nInfo:")
print(df.info())
print("\nEksik sayıları:")
print(df.isnull().sum())

# --------------------------------------------------------------
# 2) Sayısal Dönüşümler
# --------------------------------------------------------------
df["TedaviSuresi_num"]   = pd.to_numeric(df["TedaviSuresi"].astype(str).str.extract(r"(\d+)")[0], errors="coerce")
df["UygulamaSuresi_num"] = pd.to_numeric(df["UygulamaSuresi"].astype(str).str.extract(r"(\d+)")[0], errors="coerce")

print("\nDönüşüm kontrolü (ilk 5):")
print(df[["TedaviSuresi","TedaviSuresi_num","UygulamaSuresi","UygulamaSuresi_num"]].head())

# --------------------------------------------------------------
# 3) Eksik Veri Görselleştirme (kaydet)
# --------------------------------------------------------------
plt.figure(figsize=(12,6))
sns.heatmap(df.isnull(), cbar=False, cmap="YlOrRd")
plt.title("Eksik Veri Haritası")
plt.tight_layout()
plt.savefig(os.path.join(OUT_DIR, "eksik_veri_haritasi.png"), dpi=150)
plt.close()

# --------------------------------------------------------------
# 4) Sayısal Değişken Dağılımları (kaydet)
# --------------------------------------------------------------
numeric_columns = ["Yas", "TedaviSuresi_num", "UygulamaSuresi_num"]
plt.figure(figsize=(15,4))
for i, col in enumerate(numeric_columns):
    plt.subplot(1, 3, i+1)
    sns.histplot(df[col], bins=20, kde=True)
    plt.title(f"{col} Dağılımı")
    plt.xlabel(col)
plt.tight_layout()
plt.savefig(os.path.join(OUT_DIR, "sayisal_dagilim.png"), dpi=150)
plt.close()

# --------------------------------------------------------------
# 5) Çoklu Kategorikler İçin Hızlı One-Hot
# --------------------------------------------------------------
def sanitize(name: str) -> str:
    name = name.strip()
    name = re.sub(r"\s+", "_", name)
    name = re.sub(r"[^0-9A-Za-zÇçĞğİıÖöŞşÜü_]+", "_", name)
    name = re.sub(r"_+", "_", name).strip("_")
    return name

def fast_multilabel_ohe(frame: pd.DataFrame, col: str, prefix: str, top_k: int | None = None) -> pd.DataFrame:
    s = (frame[col]
         .fillna("")
         .astype(str)
         .str.replace(r"\s*,\s*", ",", regex=True)
         .str.strip(","))
    if top_k is not None and top_k > 0:
        vc = s.str.get_dummies(sep=",").sum().sort_values(ascending=False)
        keep = set(vc.head(top_k).index)
        s = s.apply(lambda x: ",".join([t for t in x.split(",") if t and t in keep]))
    dummies = s.str.get_dummies(sep=",")
    if "" in dummies.columns:
        dummies = dummies.drop(columns=[""])
    dummies.columns = [f"{prefix}_{sanitize(c)}" for c in dummies.columns]
    # dummies = dummies.astype("Int8")  # bellek için istersen aç
    return dummies

# Tanı sayısı fazla olabilir; top_k ile sınırlamak istersen değer ver (örn 100). İstemiyorsan None bırak.
alerji_ohe  = fast_multilabel_ohe(df, "Alerji",           "Alerji")
tani_ohe    = fast_multilabel_ohe(df, "Tanilar",          "Tani", top_k=100)
uyg_ohe     = fast_multilabel_ohe(df, "UygulamaYerleri",  "Uygulama")
kronik_ohe  = fast_multilabel_ohe(df, "KronikHastalik",   "Hastalik")

df_encoded = pd.concat([df, alerji_ohe, tani_ohe, uyg_ohe, kronik_ohe], axis=1)
print("\nYeni OHE sütun sayısı:",
      alerji_ohe.shape[1] + tani_ohe.shape[1] + uyg_ohe.shape[1] + kronik_ohe.shape[1])


# 6) Eksik Değer Doldurma (kategorik=mod, sayısal=median)

for col in ["Cinsiyet", "KanGrubu", "Bolum"]:
    if col in df_encoded.columns and df_encoded[col].isna().any():
        mode_val = df_encoded[col].mode(dropna=True)
        df_encoded[col] = df_encoded[col].fillna(mode_val.iloc[0] if not mode_val.empty else "Bilinmiyor")

for col in ["Yas", "TedaviSuresi_num", "UygulamaSuresi_num"]:
    if col in df_encoded.columns and df_encoded[col].isna().any():
        df_encoded[col] = df_encoded[col].fillna(df_encoded[col].median())


# 7) Basit Tutarlılık (clip)

df_encoded["Yas"] = df_encoded["Yas"].clip(lower=0, upper=100)
df_encoded["TedaviSuresi_num"]   = df_encoded["TedaviSuresi_num"].clip(lower=1, upper=120)
df_encoded["UygulamaSuresi_num"] = df_encoded["UygulamaSuresi_num"].clip(lower=1, upper=180)


# 8) Kategorik Dağılım Grafikleri (kaydet)

cat_cols = [c for c in ["Cinsiyet", "KanGrubu", "Uyruk", "Bolum"] if c in df_encoded.columns]
if cat_cols:
    rows = int(np.ceil(len(cat_cols)/2))
    plt.figure(figsize=(18, 3.5*rows))
    for i, col in enumerate(cat_cols, start=1):
        plt.subplot(rows, 2, i)
        order = df_encoded[col].value_counts(dropna=False).index
        sns.countplot(data=df_encoded, x=col, order=order)
        plt.title(f"{col} Dağılımı")
        plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    plt.savefig(os.path.join(OUT_DIR, "kategorik_dagilim.png"), dpi=150)
    plt.close()


# 9) Temiz Veriyi Kaydet (csv/xlsx)

clean_csv  = os.path.join(DATA_DIR, "clean_pusula_dataset.csv")
clean_xlsx = os.path.join(DATA_DIR, "clean_pusula_dataset.xlsx")
df_encoded.to_csv(clean_csv, index=False, encoding="utf-8")
with pd.ExcelWriter(clean_xlsx, engine="xlsxwriter") as writer:
    df_encoded.to_excel(writer, index=False)

print("\nTemiz veri kaydedildi:")
print(clean_csv)
print(clean_xlsx)


# 10) Baseline Model (RandomForest) + Feature Importance (kaydet)



# Hedef
if "TedaviSuresi_num" not in df_encoded.columns:
    raise ValueError("Hedef değişken 'TedaviSuresi_num' bulunamadı.")

y = df_encoded["TedaviSuresi_num"]

# Özellik seti: sayısallar + oluşturulan OHE kolonları
feature_cols = []
feature_cols += ["Yas", "UygulamaSuresi_num"]
feature_cols += [c for c in df_encoded.columns if c.startswith(("Alerji_", "Tani_", "Uygulama_", "Hastalik_"))]
X = df_encoded[feature_cols].fillna(0)

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.20, random_state=42
)

model = RandomForestRegressor(
    n_estimators=300,
    max_depth=None,
    random_state=42,
    n_jobs=-1
)
model.fit(X_train, y_train)

y_pred = model.predict(X_test)
mae = mean_absolute_error(y_test, y_pred)
print("\nBaseline RandomForest -> MAE:", mae)

# Feature importance grafiği
importances = pd.Series(model.feature_importances_, index=feature_cols).sort_values(ascending=False).head(20)
plt.figure(figsize=(8,6))
importances.iloc[::-1].plot(kind="barh")
plt.title("Özellik Önemleri (Top 20)")
plt.tight_layout()
plt.savefig(os.path.join(OUT_DIR, "feature_importances_top20.png"), dpi=150)
plt.close()

print("\nGrafikler kaydedildi:")
print(os.path.join(OUT_DIR, "eksik_veri_haritasi.png"))
print(os.path.join(OUT_DIR, "sayisal_dagilim.png"))
if cat_cols:
    print(os.path.join(OUT_DIR, "kategorik_dagilim.png"))
print(os.path.join(OUT_DIR, "feature_importances_top20.png"))

print("\nTamamlandı.")
