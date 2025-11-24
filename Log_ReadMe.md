# Gimbal Kontrol Paneli - CSV Log Dosyası Açıklaması

Bu doküman, Gimbal Kontrol Paneli uygulaması tarafından oluşturulan `gimbal_log_*.csv` dosyalarının içeriğini ve sütun başlıklarının ne anlama geldiğini açıklar.

Log dosyası, gimbalden gelen anlık sensör verilerini, hesaplanan hedef bilgilerini ve kayıt anında arayüzde bulunan tüm kullanıcı ayarlarını içerir. Veriler, analiz ve hata ayıklama kolaylığı için **10Hz** (saniyede 10 kayıt) frekansıyla kaydedilir.

## Sütun Açıklamaları

### Zaman Damgası
- **time** (`string`): Kaydın yapıldığı anın tam zamanı. _Format: YYYY-AA-GG SS:DD:ss.SSS_

### Ham Gimbal Verileri
Bu değerler, gimbal sensöründen doğrudan ve işlenmemiş olarak alınan ham verilerdir.
- **raw_yaw** (`float`): Ham sapma (yaw) açısı. _Birim: derece (°)_
- **raw_pitch** (`float`): Ham yükseliş (pitch) açısı. _Birim: derece (°)_
- **raw_roll** (`float`): Ham yatış (roll) açısı. _Birim: derece (°)_

### İşlenmiş Gimbal Verileri
Ham verilerin filtrelenmesi ve arayüzdeki "Gerçek Kuzey Ofseti" gibi ayarların uygulanmasıyla elde edilen son kullanıcıya gösterilen değerlerdir.
- **filtered_heading** (`float`): Filtrelenmiş ve kuzey ofseti uygulanmış yönelim (kerteriz) açısı. _Birim: derece (°)_
- **filtered_pitch** (`float`): Filtrelenmiş ve işlenmiş yükseliş açısı. _Birim: derece (°)_

### Kamera ve Gimbal Durum Bilgileri
- **zoom_level** (`float`): Kameranın anlık optik/dijital yakınlaştırma seviyesi. _Örnek: 1.0x, 30.0x_
- **focal_length** (`float`): Yakınlaştırma seviyesine göre hesaplanan etkin odak uzaklığı. _Birim: mm_
- **record_state** (`integer`): Video kayıt durumu. (`0`: Durdu, `1`: Kaydediyor, `2`: Kart Yok, `3`: Veri Kaybı)
- **motion_mode** (`integer`): Gimbalin hareket modu. (`3`: Kilit, `4`: Takip, `5`: FPV)
- **mount_dir** (`integer`): Gimbalin montaj yönü. (`1`: Normal, `2`: Ters)
- **hdr_state** (`integer`): HDR (Yüksek Dinamik Aralık) durumu. (`0`: Kapalı, `1`: Açık)

### Görüntü Takip Verileri
Görüntü işleme servisinden gelen anlık takip verileridir.
- **tracker_status** (`integer`): Takipçinin durumu. (`1` ise hedefi takip ediyor demektir).
- **tracker_dx** (`integer`): Hedefin görüntü merkezine olan yatay (X ekseni) piksel farkı.
- **tracker_dy** (`integer`): Hedefin görüntü merkezine olan dikey (Y ekseni) piksel farkı.
- **tracker_dz** (`float`): Hedefe olan tahmini uzaklık. _Birim: metre (m)_
- **is_gui_tracking_enabled** (`boolean`): Arayüzdeki "Takibi Başlat" butonunun aktif olup olmadığı.

### Hesaplanan Hedef Kinematiği
Takip aktifken, gimbal açıları ve uzaklık verisi kullanılarak hesaplanan hedef bilgileridir.
- **target_latitude** (`float`): Hedefin hesaplanan enlemi. _Birim: derece_
- **target_longitude** (`float`): Hedefin hesaplanan boylamı. _Birim: derece_
- **target_altitude** (`float`): Hedefin hesaplanan irtifası. _Birim: metre (m)_
- **target_velocity** (`float`): Hedefin hesaplanan anlık hızı. _Birim: m/s_
- **target_heading** (`float`): Hedefin hesaplanan anlık hareket yönü (kerteriz). _Birim: derece (°)_

### PI Kontrolcü Verileri
Görüntü takibi sırasında gimbalin hedefe kilitlenmesini sağlayan PI kontrolcünün iç durum değişkenleridir.
- **yaw_pi_error** (`float`): Sapma (yaw) eksenindeki anlık hata değeri (genellikle `tracker_dx`). _Birim: piksel_
- **pitch_pi_error** (`float`): Yükseliş (pitch) eksenindeki anlık hata değeri (genellikle `tracker_dy`). _Birim: piksel_
- **yaw_pi_integrator** (`float`): Sapma eksenindeki integral teriminin anlık birikmiş değeri.
- **pitch_pi_integrator** (`float`): Yükseliş eksenindeki integral teriminin anlık birikmiş değeri.

### Arayüz Ayar Parametreleri
Log kaydının alındığı anda arayüzdeki giriş kutularında bulunan değerlerdir.
- **kp_yaw**, **ki_yaw**, **kp_pitch**, **ki_pitch** (`string`): PI kontrolcünün kazanç katsayıları.
- **pixel_filter_alpha** (`string`): Görüntü takipçisinden gelen `dx`/`dy` piksel verisine uygulanan alçak geçiren filtre katsayısı.
- **pi_speed_limit** (`string`): PI kontrolcünün gimbale gönderebileceği maksimum hız komutu (yüzdesel).
- **gimbal_filter_alpha** (`string`): Gimbalden gelen ham açı verilerine uygulanan alçak geçiren filtre katsayısı.
- **coord_window_size** (`string`): Hedef koordinatlarını yumuşatmak için kullanılan hareketli ortalama penceresinin boyutu.
- **gimbal_lat_input**, **gimbal_lon_input**, **gimbal_alt_input** (`string`): Arayüze girilen gimbalin kendi konumu.
- **north_offset_input** (`string`): Gerçek kuzey ile manyetik kuzey arasındaki farkı düzeltmek için girilen ofset değeri.
- **home_lat_input**, **home_lon_input**, **home_alt_input** (`string`): Arayüze girilen "Ev" konumu.
- **min_speed_input**, **max_speed_input** (`string`): Manuel gimbal kontrolü için hız kaydırıcısının minimum ve maksimum hız limitleri.

## Notlar
- Dosya formatı, virgülle ayrılmış değerler (CSV) ve UTF-8 karakter kodlaması kullanır.