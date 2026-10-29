import ctypes
import json
import os
import queue
import sys
import threading
import time
import tkinter as tk

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    pass

import mss
import winocr
from deep_translator import GoogleTranslator
from PIL import Image

if getattr(sys, "frozen", False):
    BASE = os.path.dirname(sys.executable)
else:
    BASE = os.path.dirname(os.path.abspath(__file__))
CFG = os.path.join(BASE, "bolge.json")


def bolge_sec():
    kok = tk.Tk()
    kok.attributes("-fullscreen", True)
    kok.attributes("-alpha", 0.3)
    kok.attributes("-topmost", True)
    kok.configure(bg="black", cursor="cross")
    cv = tk.Canvas(kok, bg="black", highlightthickness=0)
    cv.pack(fill="both", expand=True)
    cv.create_text(
        kok.winfo_screenwidth() // 2, 70,
        text="Altyazının çıktığı alanı fareyle sürükleyerek seçin (İptal: Esc)",
        fill="white", font=("Segoe UI", 22),
    )
    s = {}

    def bas(e):
        s["x"], s["y"] = e.x_root, e.y_root
        s["cx"], s["cy"] = e.x, e.y
        s["r"] = cv.create_rectangle(e.x, e.y, e.x, e.y, outline="red", width=3)

    def surukle(e):
        if "r" in s:
            cv.coords(s["r"], s["cx"], s["cy"], e.x, e.y)

    def birak(e):
        if "x" not in s:
            return
        x1, x2 = sorted((s["x"], e.x_root))
        y1, y2 = sorted((s["y"], e.y_root))
        s["box"] = (x1, y1, x2, y2)
        kok.destroy()

    cv.bind("<ButtonPress-1>", bas)
    cv.bind("<B1-Motion>", surukle)
    cv.bind("<ButtonRelease-1>", birak)
    kok.bind("<Escape>", lambda e: kok.destroy())
    kok.mainloop()
    return s.get("box")


def main():
    g = GoogleTranslator(source="en", target="tr")

    box = None
    if os.path.exists(CFG):
        c = input("Kayıtlı bölge var. Enter = devam, S + Enter = yeniden seç: ")
        if c.strip().lower() != "s":
            with open(CFG) as f:
                box = tuple(json.load(f))
    if not box:
        box = bolge_sec()
        if not box or box[2] - box[0] < 20 or box[3] - box[1] < 10:
            print("Bölge seçilmedi, çıkılıyor.")
            return
        with open(CFG, "w") as f:
            json.dump(box, f)
    x1, y1, x2, y2 = box
    w, h = x2 - x1, y2 - y1

    root = tk.Tk()
    root.overrideredirect(True)
    root.attributes("-topmost", True)
    root.attributes("-alpha", 0.0)
    root.configure(bg="#111111")
    boyut = max(14, min(32, int(h * 0.45)))
    lbl = tk.Label(
        root, text="", bg="#111111", fg="white",
        font=("Segoe UI", boyut, "bold"), wraplength=w - 20, justify="center",
    )
    lbl.pack(fill="both", expand=True, padx=10, pady=6)
    root.geometry(f"{w}x{h}+{x1}+{y1}")
    root.update()

    hwnd = ctypes.windll.user32.GetParent(root.winfo_id()) or root.winfo_id()
    stil = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
    ctypes.windll.user32.SetWindowLongW(hwnd, -20, stil | 0x80000 | 0x20 | 0x80)
    if not ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, 0x11):
        root.geometry(f"{w}x{h}+{x1}+{max(0, y1 - h - 10)}")

    q = queue.Queue()

    def isci():
        onceki, son, onbellek = None, "", {}
        with mss.mss() as sct:
            while True:
                try:
                    ham = sct.grab({"left": x1, "top": y1, "width": w, "height": h})
                    img = Image.frombytes("RGB", ham.size, ham.bgra, "raw", "BGRX")
                    kucuk = list(img.convert("L").resize((48, 12)).getdata())
                    if onceki and sum(abs(a - b) for a, b in zip(kucuk, onceki)) / len(kucuk) < 4:
                        time.sleep(0.15)
                        continue
                    onceki = kucuk
                    metin = " ".join(winocr.recognize_pil_sync(img, "en")["text"].split())
                    if len(metin) < 3:
                        son = ""
                        q.put("")
                    elif metin != son:
                        son = metin
                        if metin not in onbellek:
                            if len(onbellek) > 300:
                                onbellek.clear()
                            onbellek[metin] = g.translate(metin) or metin
                        q.put(onbellek[metin])
                except Exception as e:
                    print("Hata:", e)
                    time.sleep(1)
                time.sleep(0.1)

    threading.Thread(target=isci, daemon=True).start()

    def guncelle():
        try:
            while True:
                t = q.get_nowait()
                lbl.config(text=t)
                root.attributes("-alpha", 0.92 if t else 0.0)
        except queue.Empty:
            pass
        root.after(80, guncelle)

    guncelle()
    print("Çalışıyor. Kapatmak için bu pencereyi kapatın.")
    try:
        root.mainloop()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("Beklenmeyen hata:", e)
        input("Kapatmak için Enter'a basın...")
