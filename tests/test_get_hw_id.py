"""
@file test_get_hw_id.py
@Description: This is a test script for using the SIYI SDK Python implementation to get hardware ID
@Author: Mohamed Abdelkader
@Contact: mohamedashraf123@gmail.com
All rights reserved 2022
"""

import sys
import os
from time import sleep

current = os.path.dirname(os.path.realpath(__file__))
parent_directory = os.path.dirname(current)
sys.path.append(parent_directory)

from siyi_sdk import SIYISDK

def test():
    # --- Ağ Ayarları ---
    # Sadece gimbalin IP adresini belirtmemiz yeterli
    GIMBAL_IP = "192.168.144.24"
    PORT = 37260

    print("SIYI SDK Testi Başlatılıyor...")
    print(f"Gimbal'e bağlanılıyor: {GIMBAL_IP}")

    # GÜNCELLENDİ: Artık 'server_ip' parametresini vermiyoruz.
    # SDK, varsayılan olarak '0.0.0.0' (tüm arayüzler) adresinden dinleyecektir.
    cam = SIYISDK(gimbal_ip=GIMBAL_IP, port=PORT, debug=True)

    if not cam.connect():
        print("Bağlantı başarısız oldu.")
        exit(1)
    
    print("\nBağlantı başarılı!")

    print("\n--- Kamera Bilgileri ---")
    print("Kamera Donanım ID (Tam Veri):", cam.getHardwareID())
    print("Kamera Modeli:", cam.getCameraTypeString())
    print("--------------------------\n")

    cam.disconnect()
    print("Test başarıyla tamamlandı.")

if __name__ == "__main__":
    test()