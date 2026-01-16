import flet as ft
import requests
import json

# --- AYARLAR ---
API_URL = "http://127.0.0.1:5000"

# --- GLOBAL DEĞİŞKEN ---
location_data = {} 

# --- SÖZLÜKLER ---
HEATING_MAP = {
    'Kombi-Bireysel Doğalgaz': 'Combi Boiler (Natural Gas)',
    'Merkezi Sistem': 'Central Heating',
    'Yerden Isıtma-Modern': 'Underfloor Heating',
    'Soba-Geleneksel': 'Stove',
    'Diger-Belirsiz': 'Other'
}
BUILDING_TYPE_MAP = {
    'Daire': 'Apartment Flat', 'Bina': 'Entire Building',
    'Mustakil': 'Detached House', 'Yali': 'Mansion / Yali'
}
TAPU_MAP = {
    'Tam Mülkiyet': 'Full Ownership', 'Kat İrtifakı': 'Floor Easement',
    'Hisseli Mülkiyet': 'Shared Ownership'
}
AGE_MAP = {
    '0': 'New (0)', '1-5': '1-5 Years', '6-10': '6-10 Years',
    '11-20': '11-20 Years', '21-30': '21-30 Years', '31-40': '31-40 Years',
    '41-50': '41-50 Years', '51-70': '51-70 Years'
}

def main(page: ft.Page):
    # --- MOBİL AYARLAR ---
    page.window_width = 390
    page.window_height = 844
    page.window_resizable = False
    page.title = "House Price AI"
    # theme_mode'u string vererek hatayı önlüyoruz (veya varsayılan bırakıyoruz)
    page.theme_mode = "light" 
    page.scroll = "adaptive"
    page.padding = 15
    page.bgcolor = "#F2F2F7" # iOS Grisi
    
    # --- UI ELEMANLARI ---
    
    # Header - İkonu string olarak ("home_work") veriyoruz
    header = ft.Container(
        content=ft.Row([
            ft.Icon(name="home_work", color="purple", size=30),
            ft.Column([
                ft.Text("PricePredictor", size=22, weight="bold", color="#1c1c1e"),
                ft.Text("AI Powered Valuation", size=12, color="grey")
            ], spacing=0)
        ]),
        padding=ft.padding.only(bottom=15, top=10)
    )

    # Sonuç
    lbl_result = ft.Text(value="0.00 TL", size=28, weight="bold", color="purple")
    lbl_risk_text = ft.Text("Risk Score: -", size=12, weight="bold")
    # bgcolor string "transparent"
    risk_container = ft.Container(content=lbl_risk_text, padding=8, border_radius=8, bgcolor="transparent")

    # İlan Listesi
    listings_column = ft.Column(spacing=15)

    # Form Elemanları
    dd_district = ft.Dropdown(label="District", bgcolor="white", border_radius=8, text_size=14, width=350)
    dd_neighbor = ft.Dropdown(label="Neighborhood", bgcolor="white", border_radius=8, text_size=14, width=350, disabled=True)

    # String input type ("number")
    txt_m2 = ft.TextField(label="Net M2", bgcolor="white", border_radius=8, text_size=14, expand=True, keyboard_type="number")
    txt_room = ft.TextField(label="Rooms", bgcolor="white", border_radius=8, text_size=14, expand=True, keyboard_type="number")
    txt_bath = ft.TextField(label="Bathrooms", bgcolor="white", border_radius=8, text_size=14, expand=True, keyboard_type="number")
    txt_floor_total = ft.TextField(label="Total Floors", bgcolor="white", border_radius=8, text_size=14, expand=True, keyboard_type="number")
    txt_floor = ft.TextField(label="Floor No", bgcolor="white", border_radius=8, text_size=14, expand=True, keyboard_type="number")

    dd_age = ft.Dropdown(label="Building Age", bgcolor="white", border_radius=8, text_size=14, width=350)
    dd_heating = ft.Dropdown(label="Heating Type", bgcolor="white", border_radius=8, text_size=14, width=350)
    dd_type = ft.Dropdown(label="Building Type", bgcolor="white", border_radius=8, text_size=14, width=350)
    dd_tapu = ft.Dropdown(label="Title Deed Status", bgcolor="white", border_radius=8, text_size=14, width=350)

    chk_furnished = ft.Checkbox(label="Furnished", value=False)
    chk_new = ft.Checkbox(label="New Building", value=False)
    chk_site = ft.Checkbox(label="In Complex", value=False)

    # --- FONKSİYONLAR ---

    def load_metadata():
        try:
            print("Sunucuya bağlanılıyor...")
            res = requests.get(f"{API_URL}/api/metadata")
            if res.status_code == 200:
                data = res.json()
                global location_data
                location_data = data['neighborhoods']
                
                print(f"BAŞARILI: {len(data['districts'])} ilçe yüklendi.")

                for dist in data['districts']:
                    dd_district.options.append(ft.dropdown.Option(dist))

                for age in data['ages']: dd_age.options.append(ft.dropdown.Option(key=age, text=AGE_MAP.get(age, age)))
                for h in data['heatings']: dd_heating.options.append(ft.dropdown.Option(key=h, text=HEATING_MAP.get(h, h)))
                for t in data['building_types']: dd_type.options.append(ft.dropdown.Option(key=t, text=BUILDING_TYPE_MAP.get(t, t)))
                for tapu in data['taps']: dd_tapu.options.append(ft.dropdown.Option(key=tapu, text=TAPU_MAP.get(tapu, tapu)))

                page.update()
            else:
                lbl_result.value = "Sunucu Hatası!"
                page.update()
        except Exception as e:
            lbl_result.value = "Bağlantı Hatası"
            print(f"HATA DETAYI: {e}")
            page.update()

    def on_district_change(e):
        selected_dist = dd_district.value
        print(f"SEÇİLEN İLÇE: {selected_dist}") 
        
        dd_neighbor.options.clear()
        dd_neighbor.value = None
        
        global location_data
        
        # Veri kontrolü
        if location_data:
            if selected_dist in location_data:
                neighborhoods = location_data[selected_dist]
                print(f"-> {len(neighborhoods)} mahalle bulundu.")
                dd_neighbor.disabled = False
                
                for neigh in neighborhoods:
                    display_text = neigh.split('_')[1] if '_' in neigh else neigh
                    dd_neighbor.options.append(ft.dropdown.Option(key=neigh, text=display_text))
            else:
                print(f"-> HATA: {selected_dist} anahtarı veride yok!")
                dd_neighbor.disabled = True
        else:
            print("-> HATA: İlçe verileri (location_data) boş!")
            dd_neighbor.disabled = True

        dd_neighbor.update()
        page.update()

    def get_listings(search_params):
        listings_column.controls.clear()
        listings_column.controls.append(ft.ProgressBar(width=150, color="purple", bgcolor="#eee"))
        listings_column.controls.append(ft.Text("Searching market...", size=12, color="grey"))
        page.update()

        try:
            res = requests.post(f"{API_URL}/api/get-similar-listings", json=search_params)
            listings_column.controls.clear()

            if res.status_code == 200:
                data = res.json()
                listings = data.get('listings', [])
                url = data.get('url', '#')

                if listings:
                    listings_column.controls.append(ft.Text("Market Listings:", size=16, weight="bold"))
                    for item in listings:
                        card = ft.Container(
                            content=ft.Column([
                                # fit="cover" string olarak
                                ft.Image(src=item['image'], height=120, width=320, fit="cover", border_radius=ft.border_radius.vertical(top=8)),
                                ft.Container(
                                    content=ft.Column([
                                        ft.Text(item['price'], weight="bold", size=16, color="purple"),
                                        ft.Text(item['title'], size=12, max_lines=2, overflow="ellipsis"),
                                        ft.ElevatedButton("View", url=item['link'], height=30, width=300)
                                    ]),
                                    padding=10
                                )
                            ]),
                            width=340,
                            bgcolor="white",
                            border_radius=8,
                            shadow=ft.BoxShadow(blur_radius=5, color="grey")
                        )
                        listings_column.controls.append(card)
                    listings_column.controls.append(ft.TextButton("See All on Web ->", url=url))
                else:
                    listings_column.controls.append(ft.Text("No listings found.", color="red"))
            else:
                listings_column.controls.append(ft.Text("Failed to fetch listings."))

        except Exception:
            listings_column.controls.clear()
            listings_column.controls.append(ft.Text("Network Error"))

        page.update()

    def predict_price(e):
        lbl_result.value = "Calculating..."
        lbl_risk_text.value = "Analyzing..."
        risk_container.bgcolor = "transparent"
        listings_column.controls.clear()
        page.update()

        payload = {
            "District": dd_district.value,
            "Neighborhood": dd_neighbor.value,
            "Net_M2": txt_m2.value,
            "Total_Room": txt_room.value,
            "Bathroom_Count": txt_bath.value,
            "Number_of_Floors": txt_floor_total.value,
            "Floor": txt_floor.value,
            "Age": dd_age.value,
            "Heating": dd_heating.value,
            "KonutTipi": dd_type.value,
            "Tapu": dd_tapu.value,
            "Furnished_Status": 1 if chk_furnished.value else 0,
            "Is_New_Building": 1 if chk_new.value else 0,
            "In_a_Complex": 1 if chk_site.value else 0
        }

        try:
            res = requests.post(f"{API_URL}/api/predict-mobile", json=payload)
            if res.status_code == 200:
                result = res.json()
                lbl_result.value = f"{result['prediction']} TL"
                
                risk = result['risk_score']
                risk_color = "#E8F5E9" if risk < 0.35 else ("#FFF3E0" if risk < 0.65 else "#FFEBEE")
                text_color = "green" if risk < 0.35 else ("orange" if risk < 0.65 else "red")
                label = "Low" if risk < 0.35 else ("Medium" if risk < 0.65 else "High")

                risk_container.bgcolor = risk_color
                lbl_risk_text.value = f"Risk Score: {risk} ({label})"
                lbl_risk_text.color = text_color

                page.update()
                get_listings(result['search_params'])
            else:
                lbl_result.value = "Error!"
        except Exception as ex:
            lbl_result.value = "Connection Error"
            print(ex)
        page.update()

    dd_district.on_change = on_district_change

    page.add(
        header,
        ft.Container(
            content=ft.Column([
                dd_district,
                dd_neighbor,
                ft.Row([txt_m2, txt_room], spacing=10),
                ft.Row([txt_bath, txt_floor], spacing=10),
                txt_floor_total,
                dd_age,
                dd_heating,
                dd_type,
                dd_tapu,
                ft.Row([chk_furnished, chk_new, chk_site], alignment="spaceBetween"),
                ft.Container(height=10),
                ft.ElevatedButton(
                    "Predict Price", 
                    on_click=predict_price, 
                    bgcolor="purple", 
                    color="white", 
                    width=350, 
                    height=50,
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10))
                ),
            ]),
            padding=15,
            bgcolor="white",
            border_radius=15,
            shadow=ft.BoxShadow(blur_radius=10, color="#d1d1d1")
        ),
        ft.Container(height=15),
        ft.Container(
            content=ft.Column([
                ft.Text("Estimated Value", size=12, color="grey"),
                lbl_result,
                risk_container
            ], horizontal_alignment="center"),
            alignment=ft.alignment.center
        ),
        ft.Divider(),
        listings_column
    )

    load_metadata()

ft.app(target=main)