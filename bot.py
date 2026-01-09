import time
import json
import smtplib
import os
import sys
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

# Windows konsolunda Unicode karakter sorunu yasamamak icin
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from plyer import notification
import schedule

# --- AYARLAR ---
SEARCH_KEYWORD = "Yönetim Bilişim Sistemleri"
CHECK_INTERVAL_MINUTES = 60
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "seen_ads.json")
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")

def load_config():
    # Once ortam degiskenlerine bakalim (GitHub Actions icin)
    if os.environ.get("SENDER_EMAIL") and os.environ.get("SENDER_PASSWORD"):
        return {
            "email_enabled": True,
            "sender_email": os.environ.get("SENDER_EMAIL"),
            "sender_password": os.environ.get("SENDER_PASSWORD"),
            "receiver_email": os.environ.get("RECEIVER_EMAIL") or os.environ.get("SENDER_EMAIL")
        }
    
    # Yoksa dosyadan okuyalim (Local icin)
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    else:
        print("Yapilandirma dosyasi bulunamadi. Varsayilan olusturuluyor...", flush=True)
        return None

def create_default_config():
    config = {
        "email_enabled": False,
        "sender_email": "senin_emailin@gmail.com",
        "sender_password": "gmail_uygulama_sifresi",
        "receiver_email": "alici_email@gmail.com"
    }
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=4)
    print(f"{CONFIG_FILE} olusturuldu. E-posta bildirimi istiyorsaniz lutfen bu dosyayi duzenleyin.", flush=True)

def load_seen_ads():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            try:
                return set(json.load(f))
            except:
                return set()
    return set()

def save_seen_ads(seen_ads):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(list(seen_ads), f, ensure_ascii=False)

def send_desktop_notification(title, message):
    # CI ortaminda (Sunucuda) masaustu bildirimi calismaz, hatayi yutalim
    if os.environ.get("CI"):
        print(f"Masaustu Bildirimi (Atlandi): {title} - {message}", flush=True)
        return

    try:
        # Bildirim gondermeden once biraz bekleyelim ki sistem kilitlenmesin
        time.sleep(1)
        notification.notify(
            title=title,
            message=message,
            app_name='Kariyer Kapısı Bot',
            timeout=5
        )
    except Exception as e:
        print(f"Bildirim hatasi: {e}", flush=True)

def send_email(subject, body, config):
    if not config or not config.get("email_enabled"):
        print("E-posta gonderimi kapali veya ayarlar eksik.", flush=True)
        return

    sender_email = config["sender_email"]
    sender_password = config["sender_password"]
    receiver_email = config["receiver_email"]

    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = receiver_email
    msg['Subject'] = subject

    msg.attach(MIMEText(body, 'plain'))

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, sender_password)
        text = msg.as_string()
        server.sendmail(sender_email, receiver_email, text)
        server.quit()
        print("E-posta gonderildi.", flush=True)
    except Exception as e:
        print(f"E-posta gonderme hatasi: {e}", flush=True)

def check_jobs():
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Kontrol basliyor...", flush=True)
    
    options = webdriver.ChromeOptions()
    
    # Eger CI ortamindaysak veya kullanici ozel olarak headless ayarladiysa
    is_ci = os.environ.get("CI") == "true"
    if is_ci:
        options.add_argument("--headless=new")
        options.add_argument("--disable-gpu") # CI icin ek onlem
        options.add_argument("--disable-extensions")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--ignore-certificate-errors")
        # Gercek bir browser gibi gorunmek icin User-Agent
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    # options.add_argument("--headless=new") # Local debug icin kapali kalsin
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080") # Daha buyuk cozunurluk
    options.add_argument("--log-level=3")
    
    # Sayfanin tamamen yuklenmesini bekleme (resimler vs. donarsa donmasin)
    options.page_load_strategy = 'eager'

    driver = None
    try:
        print("Tarayici baslatiliyor...", flush=True)
        # Service logunu kapatmak icin
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        
        # Sayfa yukleme zaman asimi (30 saniye verelim, donarsa 120 beklemesin)
        driver.set_page_load_timeout(30)
        
        print("Siteye gidiliyor...", flush=True)
        driver.get("https://isealimkariyerkapisi.cbiko.gov.tr")
        
        try:
            print("Buton kontrol ediliyor...", flush=True)
            btn = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.ID, "btn-ise-alim")))
            btn.click()
            print("Butona tiklandi.", flush=True)
        except:
            print("Buton bulunamadi veya gerekmedi.", flush=True)
            pass

        try:
            print("Popup kontrol ediliyor...", flush=True)
            close_btn = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.ID, "closePopup")))
            close_btn.click()
            print("Popup kapatildi.", flush=True)
        except:
            pass

        print("Arama yapiliyor...", flush=True)
        search_box = WebDriverWait(driver, 20).until(EC.element_to_be_clickable((By.ID, "txt_SearchMetin")))
        search_box.click() # Odaklan
        search_box.clear()
        search_box.send_keys(SEARCH_KEYWORD)
        time.sleep(1) # Yazarken biraz bekle
        search_box.send_keys(Keys.ENTER) # Enter tusuna bas
        
        # Tiklama da yapalim garanti olsun (JS ile)
        try:
            search_btn = driver.find_element(By.ID, "btn_Search")
            driver.execute_script("arguments[0].click();", search_btn)
        except:
            pass

        print("Sonuclar bekleniyor...", flush=True)
        time.sleep(5) 
        
        ilan_container = driver.find_element(By.ID, "pnlIlanlar")
        ilan_rows = ilan_container.find_elements(By.CLASS_NAME, "row")
        
        seen_ads = load_seen_ads()
        config = load_config()

        print(f"Toplam {len(ilan_rows)} ilan bulundu.", flush=True)
        
        # Sonuc sayisi uyarisi (Bilgi amacli)
        if len(ilan_rows) > 20:
             print("DIKKAT: Cok fazla sonuc dondu. Python tarafinda filtreleme uygulanacak.", flush=True)
        
        new_ilanlar = []

        for row in ilan_rows:
            try:
                link_elem = row.find_element(By.CSS_SELECTOR, 'a[href^="IlanDetay"]')
                href = link_elem.get_attribute("href")
                ilan_id = href.split("i=")[-1]
                ilan_text = row.text.replace("\n", " ")
                
                # Python tarafinda filtreleme sadece cok fazla sonuc donerse (guvenilmezse) yapilmali
                # Normalde site aramasi "Yönetim" sozcugunu icerikte bulup getiriyor, baslikta yazmasa bile.
                
                check_text = ilan_text.replace('İ', 'i').replace('I', 'ı').lower()
                
                # Eger 20'den fazla sonuc varsa filtreyi zorunlu kilalim
                if len(ilan_rows) > 20: 
                    basic_check = "yönetim bilişim".replace('İ', 'i').replace('I', 'ı').lower()
                    if basic_check not in check_text:
                         # print("Filtreye takildi.", flush=True)
                         continue

                if ilan_id not in seen_ads:
                    print(f"YENİ: {ilan_text[:50]}...")
                    seen_ads.add(ilan_id)
                    new_ilanlar.append(f"{ilan_text} - {href}")
            except Exception as e:
                print(f"Hata: {e}", flush=True)
        
        # Toplu islem ve kaydetme
        if new_ilanlar:
            save_seen_ads(seen_ads) # Hemen kaydet
            
            # Tek bir bildirim atalim (Spam onlemek icin)
            if len(new_ilanlar) == 1:
                send_desktop_notification("Yeni İş İlanı!", "1 yeni ilan bulundu.")
            else:
                send_desktop_notification("Yeni İş İlanları!", f"{len(new_ilanlar)} adet yeni ilan bulundu.")

            # E-posta detayli gitsin
            body = "\n\n".join(new_ilanlar)
            send_email(f"Kariyer Kapısı: {len(new_ilanlar)} Yeni İlan", body, config)
        else:
            print("Yeni ilan yok.", flush=True)

    except Exception as e:
        print(f"Genel Hata: {e}", flush=True)
    finally:
        if driver:
            driver.quit()

if __name__ == "__main__":
    if not os.path.exists(CONFIG_FILE) and not os.environ.get("SENDER_EMAIL"):
        create_default_config()

    # CI (GitHub Actions) kontrolu
    if os.environ.get("CI") == "true":
        print("CI ortami algilandi. Tek seferlik kontrol yapiliyor...", flush=True)
        check_jobs()
        print("Kontrol tamamlandi. Cikis yapiliyor.", flush=True)
    else:
        print(f"Bot başlatıldı. '{SEARCH_KEYWORD}' için {CHECK_INTERVAL_MINUTES} dakikada bir kontrol edilecek.", flush=True)
        print("Çıkmak için pencereyi kapatın veya Ctrl+C yapın.", flush=True)
        
        # İlk çalıştırma
        check_jobs()
        
        # Zamanlanmış görev
        schedule.every(CHECK_INTERVAL_MINUTES).minutes.do(check_jobs)
        
        while True:
            schedule.run_pending()
            time.sleep(1)
