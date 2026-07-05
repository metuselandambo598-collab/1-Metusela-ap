import os
import math
import threading
from PIL import Image, ImageDraw
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.filechooser import FileChooserIconView
from kivy.uix.popup import Popup
from kivy.utils import platform
from kivy.clock import Clock

COLORS = [
    (255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0), (255, 0, 255),
    (0, 255, 255), (255, 128, 0), (128, 0, 128), (0, 128, 128), (0, 0, 0)
]
CELL_SIZE = 40

def create_cell_image(value):
    color_idx = value // 100
    shape_idx = (value % 100) // 10
    rot_idx = value % 10

    img = Image.new("RGBA", (CELL_SIZE, CELL_SIZE), (255, 255, 255, 255))
    draw = ImageDraw.Draw(img)
    color = COLORS[color_idx]

    pad = 8
    x0, y0 = pad, pad
    x1, y1 = CELL_SIZE - pad, CELL_SIZE - pad
    mid = CELL_SIZE // 2

    if shape_idx == 0: draw.rectangle([x0, y0, x1, y1], fill=color)
    elif shape_idx == 1: draw.ellipse([x0, y0, x1, y1], fill=color)
    elif shape_idx == 2: draw.polygon([(mid, y0), (x0, y1), (x1, y1)], fill=color)
    elif shape_idx == 3: draw.polygon([(mid, y0), (x0, mid), (mid, y1), (x1, mid)], fill=color)
    elif shape_idx == 4:
        draw.line([x0, y0, x1, y1], fill=color, width=4)
        draw.line([x0, y1, x1, y0], fill=color, width=4)
    elif shape_idx == 5:
        draw.line([(mid, y0), (mid, y1)], fill=color, width=4)
        draw.line([(x0, mid), (x1, mid)], fill=color, width=4)
    elif shape_idx == 6: draw.rectangle([mid - 3, y0, mid + 3, y1], fill=color)
    elif shape_idx == 7: draw.ellipse([mid - 6, mid - 6, mid + 6, mid + 6], fill=color)
    elif shape_idx == 8: draw.rectangle([x0 + 4, y0 + 4, x1 - 4, y1 - 4], outline=color, width=3)
    elif shape_idx == 9: draw.polygon([(mid, y0), (x0, y1 - 4), (x1, y1 - 4)], outline=color, width=3)

    angle = rot_idx * 36
    return img.rotate(angle, resample=Image.NEAREST, fillcolor=(255, 255, 255, 255))

def run_encode(file_path, output_path):
    file_size = os.path.getsize(file_path)
    symbols = []
    temp_size = file_size
    for _ in range(4):
        symbols.append(temp_size % 1000)
        temp_size //= 1000
    symbols.reverse()

    with open(file_path, "rb") as f:
        while True:
            chunk = f.read(3)
            if not chunk: break
            if len(chunk) < 3: chunk = chunk + b'\x00' * (3 - len(chunk))
            val = int.from_bytes(chunk, 'big')
            symbols.extend([val // 1000000, (val % 1000000) // 1000, val % 1000])

    cols = 100
    rows = math.ceil(len(symbols) / cols)
    main_img = Image.new("RGB", (cols * CELL_SIZE, rows * CELL_SIZE), (255, 255, 255))

    for idx, sym in enumerate(symbols):
        c, r = idx % cols, idx // cols
        cell_img = create_cell_image(sym).convert("RGB")
        main_img.paste(cell_img, (c * CELL_SIZE, r * CELL_SIZE))
    main_img.save(output_path, "PNG")

def run_decode(image_path, output_path):
    main_img = Image.open(image_path).convert("RGB")
    width, height = main_img.size
    cols, rows = width // CELL_SIZE, height // CELL_SIZE

    lookup = {create_cell_image(v).convert("RGB").tobytes(): v for v in range(1000)}
    symbols = []
    for r in range(rows):
        for c in range(cols):
            box = (c * CELL_SIZE, r * CELL_SIZE, (c + 1) * CELL_SIZE, (r + 1) * CELL_SIZE)
            cell_bytes = main_img.crop(box).tobytes()
            symbols.append(lookup.get(cell_bytes, 0))

    file_size = 0
    for i in range(4): file_size = (file_size * 1000) + symbols[i]

    all_bytes = bytearray()
    for i in range(4, len(symbols), 3):
        if i + 2 >= len(symbols): break
        val = (symbols[i] * 1000000) + (symbols[i+1] * 1000) + symbols[i+2]
        all_bytes.extend(val.to_bytes(3, 'big'))

    with open(output_path, "wb") as f: f.write(all_bytes[:file_size])

class MetuselaApp(App):
    def build(self):
        self.title = "1 Metusela"
        if platform == 'android':
            from android.permissions import request_permissions, Permission
            request_permissions([Permission.READ_EXTERNAL_STORAGE, Permission.WRITE_EXTERNAL_STORAGE])
        
        self.selected_file = ""
        self.layout = BoxLayout(orientation='vertical', padding=20, spacing=15)
        self.status_label = Label(text="1 Metusela Ready", font_size='16sp', halign='center')
        self.layout.add_widget(self.status_label)
        
        btn_browse = Button(text="Select File", size_hint=(1, 0.2))
        btn_browse.bind(on_press=self.open_file_chooser)
        self.layout.add_widget(btn_browse)
        
        self.btn_encode = Button(text="Encode to Image", size_hint=(1, 0.2), disabled=True)
        self.btn_encode.bind(on_press=self.start_encode)
        self.layout.add_widget(self.btn_encode)
        
        self.btn_decode = Button(text="Decode to File", size_hint=(1, 0.2), disabled=True)
        self.btn_decode.bind(on_press=self.start_decode)
        self.layout.add_widget(self.btn_decode)
        return self.layout

    def open_file_chooser(self, instance):
        box = BoxLayout(orientation='vertical')
        start_path = '/storage/emulated/0/' if platform == 'android' else '/'
        file_chooser = FileChooserIconView(path=start_path)
        box.add_widget(file_chooser)
        btn_layout = BoxLayout(size_hint_y=0.15, spacing=10)
        btn_select = Button(text="Select")
        btn_cancel = Button(text="Cancel")
        btn_layout.add_widget(btn_select)
        btn_layout.add_widget(btn_cancel)
        box.add_widget(btn_layout)
        popup = Popup(title="Choose File", content=box, size_hint=(0.9, 0.9))
        
        def select_path(obj):
            if file_chooser.selection:
                self.selected_file = file_chooser.selection[0]
                filename = os.path.basename(self.selected_file)
                self.status_label.text = filename
                if filename.endswith('.png'):
                    self.btn_decode.disabled = False
                    self.btn_encode.disabled = True
                else:
                    self.btn_encode.disabled = False
                    self.btn_decode.disabled = True
                popup.dismiss()
        btn_select.bind(on_press=select_path)
        btn_cancel.bind(on_press=popup.dismiss)
        popup.open()

    def update_status(self, text, *args):
        self.status_label.text = text

    def start_encode(self, instance):
        self.status_label.text = "Processing Encode..."
        threading.Thread(target=self.process_encode).start()

    def start_decode(self, instance):
        self.status_label.text = "Processing Decode..."
        threading.Thread(target=self.process_decode).start()

    def process_encode(self):
        if self.selected_file:
            output = self.selected_file + ".metusela.png"
            try:
                run_encode(self.selected_file, output)
                Clock.schedule_once(lambda dt: self.update_status(f"Success: {os.path.basename(output)}"))
            except Exception as e:
                Clock.schedule_once(lambda dt: self.update_status("Error during encoding"))

    def process_decode(self):
        if self.selected_file:
            output = self.selected_file.replace(".metusela.png", "").replace(".png", "") + "_restored.mp4"
            try:
                run_decode(self.selected_file, output)
                Clock.schedule_once(lambda dt: self.update_status(f"Success: {os.path.basename(output)}"))
            except Exception as e:
                Clock.schedule_once(lambda dt: self.update_status("Error during decoding"))

if __name__ == '__main__':
    MetuselaApp().run()
