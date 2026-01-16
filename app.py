import numpy as np
import pandas as pd
from flask import Flask, request, render_template, jsonify
import pickle
import json
import time
import random
import unicodedata
import re
# Scraping kütüphaneleri
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

app = Flask(__name__)

# --- MODEL YÜKLEME KISMI ---
# (Kod kalabalığı olmaması için burayı tekrar yazmıyorum, senin mevcut kodunla aynı)
try:
    print("Model ve veriler yükleniyor...")
    model = pickle.load(open('model.pkl', 'rb'))
    with open('prediction_data.pkl', 'rb') as f:
        prediction_data = pickle.load(f)
    
    dist_map = prediction_data['dist_map']
    neigh_map = prediction_data['neigh_map']
    global_mean = prediction_data['global_mean']
    location_hierarchy = prediction_data['location_hierarchy']
    districts = prediction_data['districts']
    sqrft_map = prediction_data.get('sqrft_map', {})
    global_sqrft_mean = prediction_data.get('global_sqrft_mean', 0)
    risk_map = prediction_data.get('risk_map', {})
    global_risk_mean = prediction_data.get('global_risk_mean', 0)
    
    if 'feature_columns' in prediction_data:
        feature_columns = prediction_data['feature_columns']
    else:
        # Fallback listesi...
        feature_columns = [
            'Total_Room', 'Bathroom_Count', 'Net_M2', 'Number_of_Floors', 'Floor', 'Furnished_Status',
            'Is_New_Building', 'Is_Occupied', 'Is_Swap_Available', 'In_a_Complex', 'Loan_Eligibility',
            'KonutTipi_Bina', 'KonutTipi_Daire', 'KonutTipi_Kooperatif', 'KonutTipi_Mustakil', 'KonutTipi_Yali',
            'Age_0', 'Age_1-5', 'Age_6-10', 'Age_11-20', 'Age_21-30', 'Age_31-40', 'Age_41-50', 'Age_51-70',
            'Heating_Diger-Belirsiz', 'Heating_Kombi-Bireysel Doğalgaz', 'Heating_Merkezi Sistem',
            'Heating_Soba-Geleneksel', 'Heating_Yerden Isıtma-Modern', 'Tapu_Diger/Riskli', 'Tapu_Hisseli Mülkiyet',
            'Tapu_Kat İrtifakı', 'Tapu_Tam Mülkiyet', 'Building_Type_Encoded', 
            'District_Encoded', 'Neighborhood_Encoded', 'Price_Per_Sqrft'
        ]
except FileNotFoundError as e:
    print(f"KRİTİK HATA: {e}")
    model = None

# --- EXPLORE SAYFASI İÇİN ---
try:
    with open('explore_data.pkl', 'rb') as f:
        explore_data = pickle.load(f)
    dist_map_full = explore_data['dist_map_full']
    neigh_map_full = explore_data['neigh_map_full']
    print("Explore verileri yüklendi.")
except FileNotFoundError:
    print("explore_data.pkl bulunamadı, grafikler çalışmayabilir.")
    dist_map_full = {}
    neigh_map_full = {}



# --- YARDIMCI FONKSİYONLAR (URL OLUŞTURMA) ---

def turkish_to_english_slug(text):
    """
    Türkçe karakterleri İngilizce'ye çevirir ve URL dostu hale getirir.
    Örn: "Beyoğlu" -> "beyoglu", "Cihangir Mah." -> "cihangir-mah"
    """
    text = text.lower()
    replacements = {
        'ş': 's', 'ı': 'i', 'ö': 'o', 'ç': 'c', 'ğ': 'g', 'ü': 'u',
        ' ': '-', '.': ''
    }
    for search, replace in replacements.items():
        text = text.replace(search, replace)
    
    # Sadece harf, rakam ve tire kalsın
    text = re.sub(r'[^a-z0-9-]', '', text)
    return text

def get_hepsiemlak_url(district, neighborhood, room_count):
    """
    Kullanıcı girdilerine göre hepsiemlak URL'i üretir.
    """
    # 1. İlçe ve Mahalle temizliği
    # Gelen veri: "Beyoğlu", "Sarıyer_Maslak Mah."
    
    # Eğer mahalle "District_Neighborhood" formatındaysa parçala
    if "_" in neighborhood:
        neighborhood = neighborhood.split('_')[1] # "Maslak Mah."
    
    district_slug = turkish_to_english_slug(district)
    neigh_slug = turkish_to_english_slug(neighborhood)
    
    # 2. Oda Sayısı Mantığı
    # 1 -> studyo, 2 -> 1-1, 3 -> 2-1, 4 -> 3-1 ...
    room_count = int(float(room_count)) # float gelebilir, int'e çevir
    
    if room_count == 1:
        room_slug = "studyo"
    else:
        # Formül: (Oda Sayısı - 1) + 1  -> Örn: 3 oda ise 2+1'dir.
        # URL formatı: "2-1"
        salon_sayisi = 1
        oda_sayisi = room_count - salon_sayisi
        room_slug = f"{oda_sayisi}-{salon_sayisi}"
    
    # URL Oluşturma: /ilce-mahalle-satilik-oda
    url = f"https://www.hepsiemlak.com/{district_slug}-{neigh_slug}-satilik-{room_slug}"
    return url

def scrape_listings_selenium(url):
    """
    Verilen URL'den ilanları çeker.
    Eğer ilk URL'de ilan listesi bulunamazsa (Timeout), otomatik olarak alternatif URL'i dener.
    """
    listings = []
    final_url = url # Başlangıçta final_url giriş URL'idir
    driver = None

    try:
        print(f"DEBUG: Tarayıcı başlatılıyor... İlk URL: {url}")
        options = uc.ChromeOptions()
        # options.add_argument("--headless") # İstersen açabilirsin
        driver = uc.Chrome(options=options, use_subprocess=True)
        
        driver.get(url)
        
        # İlk URL için kısa bir bekleme (Listeyi aramak için)
        wait = WebDriverWait(driver, 5) # 5 saniye içinde liste gelmezse 404 sayarız
        list_found = False

        try:
            # İlanların olduğu kutuyu ara
            wait.until(EC.presence_of_element_located((By.XPATH, "//ul[contains(@class, 'list-items-container')]")))
            print("DEBUG: İlk URL'de ilan listesi bulundu. Scraping başlıyor.")
            list_found = True
        except:
            print("DEBUG: İlk URL'de ilan listesi BULUNAMADI (Timeout). Alternatif linke geçiliyor...")
            list_found = False

        # --- FALLBACK (ALTERNATİF LİNK) MEKANİZMASI ---
        if not list_found:
            if "-mah-satilik" in url:
                # "-mah" ifadesini kaldır
                fallback_url = url.replace("-mah-satilik", "-satilik")
                print(f"DEBUG: Alternatif URL deneniyor: {fallback_url}")
                
                driver.get(fallback_url)
                final_url = fallback_url # Linki güncelle ki Frontend'e doğru link gitsin
                
                # Yeni linkte tekrar listeyi bekle (Bu sefer biraz daha uzun bekleyelim)
                time.sleep(3) 
                wait_long = WebDriverWait(driver, 10)
                try:
                    wait_long.until(EC.presence_of_element_located((By.XPATH, "//ul[contains(@class, 'list-items-container')]")))
                    print("DEBUG: Alternatif URL'de liste bulundu.")
                except:
                    print("HATA: Alternatif URL'de de liste bulunamadı.")
                    return [], final_url # Boş dön
            else:
                print("DEBUG: URL '-mah' içermiyor, başka alternatif yok.")
                return [], final_url

        # --- SCRAPING İŞLEMİ (Buraya geldiyse doğru sayfadayızdır) ---
        cards = driver.find_elements(By.XPATH, "//li[contains(@class, 'listing-item')]")
        print(f"DEBUG: Toplam {len(cards)} ilan bulundu.")

        count = 0
        for i, card in enumerate(cards):
            if count >= 6: break
            try:
                # Link
                link_tag = card.find_element(By.XPATH, ".//a[contains(@class, 'card-link')]")
                href = link_tag.get_attribute("href")
                full_link = "https://www.hepsiemlak.com" + href if href and not href.startswith("http") else href

                # Resim
                img_src = "https://via.placeholder.com/300x200?text=No+Image"
                try:
                    img_tags = card.find_elements(By.XPATH, ".//img")
                    if img_tags:
                        img_tag = img_tags[0]
                        possible_src = img_tag.get_attribute("data-src") or img_tag.get_attribute("src")
                        if possible_src: img_src = possible_src
                except: pass

                # Fiyat
                price = "Fiyat Yok"
                try:
                    price_tag = card.find_element(By.XPATH, ".//span[contains(@class, 'list-view-price')]")
                    price = price_tag.text.strip()
                except: pass

                # Başlık
                title = "Başlık Yok"
                try:
                    title_tag = card.find_element(By.XPATH, ".//h3 | .//h2")
                    title = title_tag.text.strip()
                except: pass

                listings.append({
                    "title": title,
                    "price": price,
                    "image": img_src,
                    "link": full_link
                })
                count += 1
            except: continue

    except Exception as e:
        print(f"Genel Hata: {e}")
    finally:
        if driver: driver.quit()

    # Hem ilanları hem de son geçerli URL'i döndür
    return listings, final_url

# --- API ROTASI (ESKİLERİNİ SİLİP SADECE BUNU YAPIŞTIR) ---
@app.route('/api/get-similar-listings', methods=['POST'])
def get_similar_listings():
    data = request.json
    district = data.get('district')
    neighborhood = data.get('neighborhood')
    room = data.get('room')
    
    print(f"Scraping İsteği: {district} - {neighborhood}")
    
    initial_url = get_hepsiemlak_url(district, neighborhood, room)
    
    # scrape_listings_selenium fonksiyonu artık 2 değer döndürüyor (listings ve url)
    listings, valid_url = scrape_listings_selenium(initial_url)
    
    return jsonify({
        'url': valid_url, # Frontend'e çalışan doğru linki gönderiyoruz
        'listings': listings
    })

# --- FLASK ROTALARI ---

@app.route('/')
def home():
    if not districts:
        return "Veriler yüklenemedi.", 500
    return render_template('index.html', districts=districts, location_data_json=json.dumps(location_hierarchy))

@app.route('/predict', methods=['POST'])
def predict():
    if model is None:
        return "Model yüklenemedi.", 500

    form_values = request.form
    
    # --- MODEL İÇİN VERİ HAZIRLAMA (MEVCUT KODLARIN AYNI) ---
    input_data = {
        'Total_Room': float(form_values.get('Total_Room', 0)), 
        'Bathroom_Count': float(form_values.get('Bathroom_Count', 0)),
        'Net_M2': float(form_values.get('Net_M2', 0)), 
        'Number_of_Floors': float(form_values.get('Number_of_Floors', 0)),
        'Floor': float(form_values.get('Floor', 0)), 
        'Furnished_Status': int(form_values.get('Furnished_Status', 0)),
        'Is_New_Building': int(form_values.get('Is_New_Building', 0)), 
        'In_a_Complex': int(form_values.get('In_a_Complex', 0)),
        'Is_Occupied': 0, 
        'Is_Swap_Available': 0, 
        'Loan_Eligibility': 1, 
        'Building_Type_Encoded': 1
    }

    def set_one_hot(prefix, selected_value, all_possible_cols):
        full_feature_name = prefix + str(selected_value)
        for col in all_possible_cols:
            if col.startswith(prefix): 
                input_data[col] = 1 if col == full_feature_name else 0

    set_one_hot('KonutTipi_', form_values.get('KonutTipi'), ['KonutTipi_Bina', 'KonutTipi_Daire', 'KonutTipi_Kooperatif', 'KonutTipi_Mustakil', 'KonutTipi_Yali'])
    set_one_hot('Age_', form_values.get('Age'), ['Age_0', 'Age_1-5', 'Age_6-10', 'Age_11-20', 'Age_21-30', 'Age_31-40', 'Age_41-50', 'Age_51-70'])
    set_one_hot('Heating_', form_values.get('Heating'), ['Heating_Diger-Belirsiz', 'Heating_Kombi-Bireysel Doğalgaz', 'Heating_Merkezi Sistem', 'Heating_Soba-Geleneksel', 'Heating_Yerden Isıtma-Modern'])
    set_one_hot('Tapu_', form_values.get('Tapu'), ['Tapu_Diger/Riskli', 'Tapu_Hisseli Mülkiyet', 'Tapu_Kat İrtifakı', 'Tapu_Tam Mülkiyet'])

    selected_district = form_values.get('District')
    selected_neighborhood_key = form_values.get('Neighborhood') 
    
    input_data['District_Encoded'] = dist_map.get(selected_district, global_mean)
    input_data['Neighborhood_Encoded'] = neigh_map.get(selected_neighborhood_key, global_mean)
    
    if sqrft_map:
        birim_fiyat = sqrft_map.get(selected_neighborhood_key, global_sqrft_mean)
        input_data['Price_Per_Sqrft'] = birim_fiyat
    else:
        input_data['Price_Per_Sqrft'] = 0
    
    risk_value = risk_map.get(selected_neighborhood_key, global_risk_mean)

    final_features_df = pd.DataFrame([input_data])[feature_columns]
    prediction = model.predict(final_features_df)
    output = float(prediction[0])


    # --- FİYAT ARALIĞI HESAPLAMA (%10 Alt - %10 Üst) ---
    lower_bound = output * 0.90
    upper_bound = output * 1.10
    
    # Sayıları formatla (Örn: 4,500,000 - 5,500,000 TL)
    # :.0f kullanarak kuruş hanesini sildim, emlak fiyatlarında daha temiz görünür.
    formatted_range = f"{lower_bound:,.0f} TL - {upper_bound:,.0f} TL"


    neighborhood_part = selected_neighborhood_key.split('_')[1] if '_' in selected_neighborhood_key else selected_neighborhood_key
    map_query_string = f"{neighborhood_part}, {selected_district}, Turkey"

    # --- DEĞİŞİKLİK BURADA: Input değerlerini Result sayfasına gönderiyoruz ---
    return render_template(
        'result.html',
        prediction_text=formatted_range, 
        risk_score=round(risk_value, 2),
        map_query=map_query_string,
        # Scraping için gerekli parametreleri HTML'e gömüyoruz:
        search_district=selected_district,
        search_neighborhood=selected_neighborhood_key,
        search_room=input_data['Total_Room']
    )




# --- EXPLORE sayfası için ---

@app.route('/explore')
def explore_page():
    # districts listesini alfabetik sıralayıp sayfaya gönderiyoruz
    return render_template('explore.html', districts=sorted(districts))

@app.route('/api/district-stats')
def district_stats():
    # Modelin map'i yerine tam veri setinden gelen map'i kullanıyoruz
    if dist_map_full:
        try:
            # Fiyata göre sırala
            sorted_districts = sorted(dist_map_full.items(), key=lambda item: item[1], reverse=True)
            
            labels = [str(item[0]) for item in sorted_districts] 
            values = [round(float(item[1]), 2) for item in sorted_districts] 
            
            return jsonify({
                'labels': labels,
                'data': values
            })
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    return jsonify({'error': 'Explore verisi yüklenemedi'}), 500

@app.route('/api/neighborhood-stats/<district>')
def neighborhood_stats(district):
    # URL'den gelen ilçe ismini unquote ile temizle (Türkçe karakterler için)
    from urllib.parse import unquote
    target_district = unquote(district).strip()
    
    # Türkçe karakter duyarlı küçük harf fonksiyonu (Eşleşme garantisi için)
    def turkish_lower(text):
        if not text: return ""
        return text.replace('İ', 'i').replace('I', 'ı').lower().strip()

    search_term = turkish_lower(target_district)

    if neigh_map_full:
        try:
            filtered_data = {}
            for k, v in neigh_map_full.items():
                if "_" in k:
                    parts = k.split("_", 1)
                    db_district = turkish_lower(parts[0])
                    
                    if db_district == search_term:
                        filtered_data[parts[1]] = v
            
            if not filtered_data:
                return jsonify({'labels': [], 'data': []})

            # Fiyata göre sırala
            sorted_neighs = sorted(filtered_data.items(), key=lambda item: item[1], reverse=True)
            
            return jsonify({
                'labels': [str(item[0]) for item in sorted_neighs],
                'data': [round(float(item[1]), 2) for item in sorted_neighs]
            })
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    return jsonify({'error': 'Veri bulunamadı'}), 404




if __name__ == "__main__":
    app.run(debug=True)