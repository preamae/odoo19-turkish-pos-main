# Kurulum Rehberi / Installation Guide

## 🇹🇷 TÜRKÇE

### Hangi Dosyaları Yüklemeliyim?

Sadece **`turkish_pos_abstract_payment`** klasörünü yüklemelisiniz.

```
odoo19-turkish-pos-main/
├── turkish_pos_abstract_payment/    ← BU KLASÖRÜ YÜKLE!
│   ├── __init__.py
│   ├── __manifest__.py
│   ├── models/
│   ├── controllers/
│   ├── views/
│   ├── data/
│   ├── security/
│   └── ...
├── models/                           ← Bu klasör ana turkish_pos modülü için
├── controllers/                      ← Bu klasör ana turkish_pos modülü için
└── ...                              ← Diğer dosyalar ana turkish_pos modülü için
```

### Adım Adım Kurulum

#### 1. Ön Koşul: Turkish POS Modülü

**ÖNEMLİ:** `turkish_pos_abstract_payment` modülü, `turkish_pos` modülüne bağlıdır.

**Seçenek A:** Eğer `turkish_pos` zaten yüklüyse:
- Direkt adım 2'ye geç

**Seçenek B:** Eğer `turkish_pos` yüklü değilse:
- Önce tüm repository'yi (`odoo19-turkish-pos-main`) Odoo addons klasörüne kopyala
- `turkish_pos` modülünü Odoo'da yükle
- Sonra `turkish_pos_abstract_payment` modülünü yükle

#### 2. turkish_pos_abstract_payment Klasörünü Kopyala

```bash
# Repository'yi klonla (eğer klonlamadıysan)
git clone https://github.com/preamae/odoo19-turkish-pos-main.git

# Sadece turkish_pos_abstract_payment klasörünü kopyala
cd odoo19-turkish-pos-main
cp -r turkish_pos_abstract_payment /opt/odoo/addons/

# Veya Windows'ta:
# xcopy turkish_pos_abstract_payment C:\odoo\addons\turkish_pos_abstract_payment /E /I
```

#### 3. Odoo'yu Yeniden Başlat

```bash
sudo systemctl restart odoo

# Veya Docker kullanıyorsan:
docker-compose restart odoo
```

#### 4. Modülü Yükle

1. Odoo'ya giriş yap
2. **Apps** menüsüne git
3. **Update Apps List** tıkla
4. Arama kutusuna `Turkish POS Abstract Payment` yaz
5. Modülü bul ve **Install** tıkla
6. ✅ Başarıyla yüklenecek!

#### 5. Doğrulama

Modülün doğru yüklendiğini kontrol et:

1. **Abstract Payment** menüsünü göreceksin (üst menüde)
2. **Abstract Payment > Payment Methods** git
3. 3 ödeme metodu görmelisin:
   - Nakit Ödeme
   - Kredi Kartı
   - Banka Havalesi / EFT

### Sorun Giderme

#### Hata: "turkish.pos.bank model bulunamadı"
**Çözüm:** `turkish_pos` modülünü önce yükle

#### Hata: "Many2many fields use the same table"
**Çözüm:** Bu hata düzeltildi. En son kodu çek:
```bash
cd odoo19-turkish-pos-main
git pull origin copilot/add-turkish-pos-abstract-payment
```

#### Hata: "Module not found"
**Çözüm:** Doğru klasörü kopyaladığından emin ol. 
`turkish_pos_abstract_payment` klasörünü `/opt/odoo/addons/` altına kopyala.

---

## 🇬🇧 ENGLISH

### Which Files Should I Install?

You only need to install the **`turkish_pos_abstract_payment`** folder.

```
odoo19-turkish-pos-main/
├── turkish_pos_abstract_payment/    ← INSTALL THIS FOLDER!
│   ├── __init__.py
│   ├── __manifest__.py
│   ├── models/
│   ├── controllers/
│   ├── views/
│   ├── data/
│   ├── security/
│   └── ...
├── models/                           ← This folder is for main turkish_pos module
├── controllers/                      ← This folder is for main turkish_pos module
└── ...                              ← Other files are for main turkish_pos module
```

### Step by Step Installation

#### 1. Prerequisite: Turkish POS Module

**IMPORTANT:** `turkish_pos_abstract_payment` module depends on `turkish_pos` module.

**Option A:** If `turkish_pos` is already installed:
- Go directly to step 2

**Option B:** If `turkish_pos` is not installed:
- First copy entire repository (`odoo19-turkish-pos-main`) to Odoo addons folder
- Install `turkish_pos` module in Odoo
- Then install `turkish_pos_abstract_payment` module

#### 2. Copy turkish_pos_abstract_payment Folder

```bash
# Clone repository (if you haven't)
git clone https://github.com/preamae/odoo19-turkish-pos-main.git

# Copy only turkish_pos_abstract_payment folder
cd odoo19-turkish-pos-main
cp -r turkish_pos_abstract_payment /opt/odoo/addons/

# Or on Windows:
# xcopy turkish_pos_abstract_payment C:\odoo\addons\turkish_pos_abstract_payment /E /I
```

#### 3. Restart Odoo

```bash
sudo systemctl restart odoo

# Or if using Docker:
docker-compose restart odoo
```

#### 4. Install Module

1. Login to Odoo
2. Go to **Apps** menu
3. Click **Update Apps List**
4. Search for `Turkish POS Abstract Payment`
5. Find the module and click **Install**
6. ✅ Will install successfully!

#### 5. Verification

Check that module is installed correctly:

1. You'll see **Abstract Payment** menu (top menu)
2. Go to **Abstract Payment > Payment Methods**
3. You should see 3 payment methods:
   - Nakit Ödeme (Cash)
   - Kredi Kartı (Credit Card)
   - Banka Havalesi / EFT (Bank Transfer)

### Troubleshooting

#### Error: "turkish.pos.bank model not found"
**Solution:** Install `turkish_pos` module first

#### Error: "Many2many fields use the same table"
**Solution:** This error is fixed. Pull latest code:
```bash
cd odoo19-turkish-pos-main
git pull origin copilot/add-turkish-pos-abstract-payment
```

#### Error: "Module not found"
**Solution:** Make sure you copied correct folder. 
Copy `turkish_pos_abstract_payment` folder to `/opt/odoo/addons/`.

---

## 📁 Klasör Yapısı / Folder Structure

```
/opt/odoo/addons/
├── turkish_pos/                      (Ana modül / Main module)
│   ├── __manifest__.py
│   ├── models/
│   └── ...
│
└── turkish_pos_abstract_payment/     (Bu modül / This module)
    ├── __manifest__.py
    ├── models/
    ├── controllers/
    ├── views/
    ├── data/
    └── ...
```

## 🔗 Bağlantılar / Links

- GitHub: https://github.com/preamae/odoo19-turkish-pos-main
- Branch: copilot/add-turkish-pos-abstract-payment
- Dokümantasyon / Documentation: README.md
- Fix Detayları / Fix Details: FIX_MANY2MANY_CONFLICT.md

## ✅ Başarı Kontrolü / Success Check

Modül başarıyla yüklendiğinde:
- ✅ Apps listesinde "Turkish POS Abstract Payment" yüklü görünür
- ✅ Abstract Payment menüsü üstte görünür
- ✅ 3 ödeme metodu oluşturulmuş olur
- ✅ Hata mesajı yok

When module is successfully installed:
- ✅ "Turkish POS Abstract Payment" appears as installed in Apps list
- ✅ Abstract Payment menu appears at top
- ✅ 3 payment methods are created
- ✅ No error messages
