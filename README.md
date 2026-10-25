# SysDash

Linux için masaüstü sistem sağlığı uygulaması: CPU, RAM, swap, disk, sıcaklık ve çalışan processler.
Python + PySide6 (Qt) + psutil + pyqtgraph + qtawesome ile yazıldı.

## Özellikler

- **Yan menü:** Genel bakış, Performans, Diskler ve Sıcaklıklar sayfaları; en altta koyu/açık tema düğmesi
  (seçim kaydedilir, ilk açılışta sistem temasına uyulur)
- **Özet kartları:** CPU, RAM, kök disk ve en sıcak sensör. Her kartta yumuşakça dolan dairesel gösterge
  ve son 1 dakikanın mini grafiği var; eşik aşılınca renk turuncuya, sonra kırmızıya döner
- **Processler:** canlı tablo; tüm sütunlarda arama, sütuna tıklayarak sıralama, yüke göre renklenen CPU
  çubukları, renkli durum etiketleri, sağ tıkla sonlandırma / zorla öldürme
- **Performans:** son 3 dakikanın CPU ve RAM grafiği, çekirdek başına CPU çubukları
- **Diskler:** her bağlama noktası için doluluk çubuğu
- **Sıcaklıklar:** tüm sensörler (lm-sensors / hwmon); sensör yoksa açıklayıcı bir boş ekran

## Dosyalar

| Dosya | Görevi |
|---|---|
| `collector.py` | psutil ile tüm metrikleri toplar. Arayüzden bağımsızdır; tek başına `python collector.py` ile test edilebilir. |
| `process_model.py` | Process tablosunun Qt modeli. Satırları PID'ye göre günceller, böylece seçim ve kaydırma konumu korunur. |
| `theme.py` | Koyu ve açık renk paleti, Qt stil sayfası (QSS) ve yazı tipleri. |
| `widgets.py` | Dairesel gösterge, mini grafik, doluluk çubuğu, kartlar ve grafikler. |
| `delegates.py` | Process tablosundaki CPU çubuğu ve durum etiketi hücreleri. |
| `main.py` | Ana pencere, yan menü, sayfalar ve arka plan veri toplama thread'i. |
| `sysdash.desktop` | Uygulama menüsünde görünmesi için masaüstü girdisi. |

## Çalıştırma (Linux)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

Ubuntu/Debian'da Qt "xcb platform plugin" hatası alırsan:

```bash
sudo apt install libxcb-cursor0
```

Arayüz Inter ve JetBrains Mono yazı tiplerini kullanır; kurulu değillerse sistemdeki benzerlerine geçer:

```bash
sudo apt install fonts-inter fonts-jetbrains-mono
```

Fiziksel makinede sıcaklık görünmüyorsa:

```bash
sudo apt install lm-sensors
sudo sensors-detect
```

## Windows'ta geliştirme

psutil ve PySide6 Windows'ta da çalışır. Sıcaklık dışındaki her şeyi Windows'ta geliştirip deneyebilirsin;
son testleri gerçek bir Linux makinede ya da sanal makinede yap. Sanal makinede ve WSL'de sıcaklık sensörü olmaz.

Geliştirirken belirli bir sayfanın ve temanın görüntüsünü almak için (`--page` 0-3, `--delay` saniye):

```bash
python main.py --page 1 --theme light --delay 20 --screenshot ekran.png
```

## Nasıl çalışıyor?

`CollectorWorker` ayrı bir `QThread`'de 2 saniyede bir `collector.snapshot()` çağırır ve sonucu sinyal olarak
arayüze gönderir. Veri toplama arayüz thread'inde yapılsaydı, yüzlerce process taranırken pencere donardı.

Arayüze yalnızca ana thread dokunabilir. Bu yüzden `on_update` `@Slot` ile işaretli ve sinyale
`Qt.QueuedConnection` ile bağlı. Böylece PySide6 onu her zaman ana thread'de çalıştırır.

Özel çizilen bileşenler (gösterge, mini grafik, çubuklar) renklerini her çizimde `theme.current`'tan okur.
Tema değişince yeni stil sayfası uygulanır ve bileşenler yeniden çizilir.

psutil'in `cpu_percent()` değerleri iki çağrı arasındaki farktan hesaplanır. Bu yüzden psutil'i yalnızca
bu worker çağırır ve ilk (her zaman 0 olan) ölçüm atılır.

Process CPU yüzdesi, htop'tan farklı olarak toplam CPU'ya oranlanır (çekirdek sayısına bölünür). Yani
tüm processlerin toplamı en fazla %100 olur.

## Paketleme

Tek dosyalık çalıştırılabilir dosya:

```bash
pip install pyinstaller
pyinstaller --onefile --name sysdash main.py
```

Çıkan `dist/sysdash` dosyasını `/opt/sysdash/` altına koy ve `sysdash.desktop` dosyasını
`~/.local/share/applications/` klasörüne kopyala. Dağıtım için AppImage ya da `.deb` (ör. `fpm` ile) uygundur.
Flatpak ve Snap sandbox'ı ana sistemin processlerini gizlediği için bu uygulamaya uygun değildir.

## Yol haritası

- [ ] Process detay penceresi (çift tık): thread'ler, açık dosyalar, ağ bağlantıları
- [ ] Process ağacı görünümü (`ppid`)
- [ ] Ağ ve disk I/O hızları
- [ ] Sistem tepsisi simgesi (`QSystemTrayIcon`) ve eşik aşımında masaüstü bildirimi
- [x] Koyu/açık tema (`QSettings` ile kaydediliyor)
- [ ] Ayarlar: yenileme aralığı, eşikler
- [ ] Başka kullanıcıların processlerini `pkexec` ile durdurma
