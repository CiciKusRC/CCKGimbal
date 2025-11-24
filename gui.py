import sys
import threading
import socket
import json
import math
import time
import queue
import collections
import csv
from datetime import datetime
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QSlider, QLabel, QGridLayout, QGroupBox,
                             QLineEdit, QComboBox, QDialog, QDialogButtonBox, QCheckBox)
from PyQt5.QtCore import Qt, QTimer, QPointF, QObject, pyqtSignal
from PyQt5.QtGui import (QPainter, QColor, QFont, QPen, QBrush, QPolygonF, QPainterPath)

try:
    import pygame
    PYGAME_AVAILABLE = True
except ImportError:
    PYGAME_AVAILABLE = False
    print("Uyarı: Pygame modülü bulunamadı. Joystick özellikleri devre dışı bırakıldı.")

try:
    from siyi_sdk import SIYISDK
except ImportError:
    print("Uyarı: SIYISDK modülü bulunamadı. Lütfen siyi_sdk.py dosyasının projenizde olduğundan emin olun.")
    class SIYISDK:
        def __init__(self, *args, **kwargs): self._connected = False
        def connect(self): self._connected = True; print("Sahte SIYISDK: Bağlandı."); return True
        def disconnect(self): self._connected = False; print("Sahte SIYISDK: Bağlantı kesildi.")
        def isConnected(self): return self._connected
        def getAttitude(self): return 0.0, 0.0, 0.0
        def getCurrentZoomLevel(self): return 1.0
        def getGimbalInfo(self): return type('info', (object,), {'record_state': 0, 'motion_mode': 0, 'mount_dir': 1, 'hdr_sta': 0})()
        def setGimbalSpeed(self, yaw, pitch): pass
        def requestCenterGimbal(self): pass
        def takePhoto(self): pass
        def toggleRecording(self): pass
        def requestManualZoom(self, direction): pass
        def setMotionMode(self, mode): pass
        def requestAutoFocus(self): pass
        def requestManualFocus(self, direction): pass
        def getCameraTypeString(self): return "Sahte Kamera"

class AttitudeIndicator(QWidget):
    """
    Gimbal'in Yaw, Pitch ve Roll açılarını gösteren bir yapay ufuk göstergesi widget'ı.
    """
    
    COLOR_BACKGROUND = QColor(20, 20, 20)
    COLOR_SKY = QColor(0, 120, 215)
    COLOR_GROUND = QColor(139, 69, 19)
    COLOR_TEXT_AND_LINES = QColor(Qt.white)
    COLOR_AIRCRAFT_SYMBOL = QColor(255, 200, 0)
    
    PIXELS_PER_DEGREE_PITCH = 2.5
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.yaw = 0.0
        self.pitch = 0.0
        self.roll = 0.0
        self.setMinimumSize(220, 220)

    def set_attitude(self, yaw, pitch, roll):
        """
        Göstergenin açılarını günceller ve yeniden çizilmesini tetikler.
        """
        self.yaw = yaw
        self.pitch = pitch
        self.roll = roll
        self.update()

    def paintEvent(self, event):
        """
        Qt tarafından çağrılan ve widget'ı boyayan ana metot.
        """
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        width = self.width()
        height = self.height()
        center = QPointF(width / 2, height / 2)
        radius = min(width, height) / 2 - 10

        self._draw_background_bezel(painter, center, radius)
        self._draw_artificial_horizon(painter, center, radius)
        self._draw_compass(painter, center, radius)
        self._draw_aircraft_symbol(painter, center)
        
    def _draw_background_bezel(self, painter, center, radius):
        """
        Göstergenin dairesel arka planını ve çerçevesini çizer.
        """
        painter.setPen(Qt.NoPen)
        painter.setBrush(self.COLOR_BACKGROUND)
        painter.drawEllipse(center, radius, radius)
        
    def _draw_artificial_horizon(self, painter, center, radius):
        """
        Yapay ufku (gökyüzü/yer) ve pitch merdivenini çizer.
        Bu bölüm, pitch ve roll açılarına göre hareket eder.
        """
        painter.save()
        
        clip_path = QPainterPath()
        clip_path.addEllipse(QPointF(0, 0), radius - 1, radius - 1)

        painter.translate(center)
        painter.setClipPath(clip_path)

        painter.rotate(self.roll)
        painter.translate(0, self.pitch * self.PIXELS_PER_DEGREE_PITCH)
        
        huge_rect_size = int(radius * 4)
        painter.setPen(QPen(self.COLOR_TEXT_AND_LINES, 2))
        painter.setFont(QFont("Arial", 8))
        painter.setBrush(self.COLOR_GROUND)
        painter.drawRect(-huge_rect_size, 0, huge_rect_size * 2, huge_rect_size)
        painter.setBrush(self.COLOR_SKY)
        painter.drawRect(-huge_rect_size, -huge_rect_size, huge_rect_size * 2, huge_rect_size)

        for p_angle in range(-90, 91, 10):
            y_pos = int(-p_angle * self.PIXELS_PER_DEGREE_PITCH)
            
            is_major_tick = (p_angle % 30 == 0)
            length = 30 if is_major_tick else 15
            pen_width = 2 if p_angle == 0 else 1 
            
            painter.setPen(QPen(self.COLOR_TEXT_AND_LINES, pen_width))
            painter.drawLine(-length, y_pos, length, y_pos)
            
            if is_major_tick and p_angle != 0:
                painter.drawText(-length - 25, y_pos + 4, str(p_angle))
                painter.drawText(length + 5, y_pos + 4, str(p_angle))
                
        painter.restore()

    def _draw_compass(self, painter, center, radius):
        """
        Pusula halkasını (yaw göstergesi) çizer.
        Bu bölüm, yaw açısına göre döner.
        """
        painter.save()
        painter.translate(center)
        painter.rotate(-self.yaw) 
        
        painter.setPen(QPen(self.COLOR_TEXT_AND_LINES, 2))
        painter.setFont(QFont("Arial", 10, QFont.Bold))

        for angle_deg in range(0, 360, 15):
            painter.save()
            painter.rotate(angle_deg)
            
            is_major_tick = (angle_deg % 45 == 0)
            tick_length = 10 if is_major_tick else 5
            
            painter.drawLine(0, int(-radius), 0, int(-radius + tick_length))
            
            if is_major_tick:
                cardinal_points = {0: "K", 90: "D", 180: "G", 270: "B"}
                point_text = cardinal_points.get(angle_deg, "")
                painter.drawText(QPointF(-7, -radius + 25), point_text)
                
            painter.restore()
            
        painter.restore()
        
    def _draw_aircraft_symbol(self, painter, center):
        """
        Ekranın ortasında duran sabit uçak sembolünü ve yaw işaretçisini çizer.
        """
        painter.translate(center)
        
        pen = QPen(self.COLOR_AIRCRAFT_SYMBOL, 3)
        brush = QBrush(self.COLOR_AIRCRAFT_SYMBOL)
        painter.setPen(pen)
        painter.setBrush(brush)
        
        yaw_pointer_poly = QPolygonF([
            QPointF(0, -self.height()/2+10),   
            QPointF(-7, -self.height()/2+22),
            QPointF(7, -self.height()/2+22)
        ])
        painter.drawPolygon(yaw_pointer_poly)

        painter.drawLine(-40, 0, -10, 0) 
        painter.drawLine(10, 0, 40, 0) 
        painter.drawLine(-10, 0, 0, 5) 
        painter.drawLine(10, 0, 0, 5)

if PYGAME_AVAILABLE:
    class JoystickConfigDialog(QDialog):
        """
        Kullanıcının joystick'lerini seçmesine ve gimbal eylemlerini (eksenler, düğmeler, POV Hat)
        bu joystick'lere atamasına olanak tanıyan bir yapılandırma penceresi.
        """
        config_saved = pyqtSignal(dict)
        
        ACTIONS = {
            "Yönelim (Yaw)": {"type": "axis", "key": "YAW_AXIS", "rev_key": "REVERSE_YAW"},
            "Yükseliş (Pitch)": {"type": "axis", "key": "PITCH_AXIS", "rev_key": "REVERSE_PITCH"},
            "Gimbal Hız": {"type": "axis", "key": "SPEED_AXIS", "rev_key": "REVERSE_SPEED"},
            "Fotoğraf Çek": {"type": "button", "key": "PHOTO_BUTTON"},
            "Video Kaydet": {"type": "button", "key": "RECORD_BUTTON"},
            "Takibi Başlat": {"type": "button", "key": "TRACK_START_BUTTON"},
            "Takibi Bitir": {"type": "button", "key": "TRACK_STOP_BUTTON"},
            "Görüntü Takip": {"type": "button", "key": "TRACK_RESET_BUTTON"},
            "Zoom In (+)": {"type": "button", "key": "ZOOM_IN_BUTTON"},
            "Zoom Out (-)": {"type": "button", "key": "ZOOM_OUT_BUTTON"},
            "Odak Yakınlaştır (+)": {"type": "button", "key": "FOCUS_NEAR_BUTTON"},
            "Odak Uzaklaştır (-)": {"type": "button", "key": "FOCUS_FAR_BUTTON"},
        }
        
        def __init__(self, current_config, parent=None):
            super().__init__(parent)
            self.setWindowTitle("Joystick Ayarları"); self.setMinimumWidth(500)
            self.config, self.widgets = current_config, {}
            pygame.joystick.init()
            main_layout = QVBoxLayout(self)
            form_layout, button_box = self._create_form_layout(), self._create_button_box()
            main_layout.addLayout(form_layout); main_layout.addWidget(button_box)
            if pygame.joystick.get_count() > 0: self.populate_axes_and_buttons(); self.load_config_to_ui()

        def _create_form_layout(self):
            form_layout = QGridLayout()
            self._create_joystick_selector(form_layout)
            for row, (name, data) in enumerate(self.ACTIONS.items(), 1): self._create_action_row(form_layout, name, data, row)
            return form_layout

        def _create_joystick_selector(self, layout):
            self.joy_select = QComboBox()
            joystick_count = pygame.joystick.get_count()
            if joystick_count == 0: self.joy_select.addItem("Joystick Bulunamadı")
            else:
                for i in range(joystick_count): self.joy_select.addItem(pygame.joystick.Joystick(i).get_name())
            self.joy_select.currentIndexChanged.connect(self.populate_axes_and_buttons)
            layout.addWidget(QLabel("Joystick:"), 0, 0); layout.addWidget(self.joy_select, 0, 1, 1, 2)

        def _create_action_row(self, layout, name, data, row):
            combo = QComboBox(); self.widgets[data["key"]] = combo
            detect_btn = QPushButton("Oto. Algıla"); detect_btn.clicked.connect(lambda ch, action_name=name: self.auto_detect(action_name))
            layout.addWidget(QLabel(name + ":"), row, 0); layout.addWidget(combo, row, 1); layout.addWidget(detect_btn, row, 2)
            if data["type"] == "axis":
                checkbox = QCheckBox("Ters Çevir"); self.widgets[data["rev_key"]] = checkbox; layout.addWidget(checkbox, row, 3)

        def _create_button_box(self):
            button_box = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
            button_box.accepted.connect(self.save_and_accept); button_box.rejected.connect(self.reject)
            return button_box

        def populate_axes_and_buttons(self):
            joy_index = self.joy_select.currentIndex()
            if joy_index < 0: return
            joystick = pygame.joystick.Joystick(joy_index)
            axis_items = ["-"]+[f"Eksen {i}" for i in range(joystick.get_numaxes())]
            button_items = ["-"]+[f"Düğme {i}" for i in range(joystick.get_numbuttons())]
            hat_directions = {"Yukarı":(0,1),"Aşağı":(0,-1),"Sol":(-1,0),"Sağ":(1,0)}
            for i in range(joystick.get_numhats()):
                for name in hat_directions: button_items.append(f"Hat {i} {name}")
            for data in self.ACTIONS.values(): 
                self.widgets[data["key"]].clear()
                self.widgets[data["key"]].addItems(axis_items if data["type"] == "axis" else button_items)
        
        def load_config_to_ui(self):
            for data in self.ACTIONS.values():
                if data["key"] in self.config:
                    index = self.widgets[data["key"]].findText(str(self.config[data['key']]))
                    if index > -1: self.widgets[data["key"]].setCurrentIndex(index)
                    else: 
                        text_to_find = f"{'Eksen' if data['type']=='axis' else 'Düğme'} {self.config[data['key']]}"
                        index = self.widgets[data["key"]].findText(text_to_find)
                        if index > -1: self.widgets[data["key"]].setCurrentIndex(index)
                if data.get("rev_key") and data["rev_key"] in self.config: self.widgets[data["rev_key"]].setChecked(self.config[data["rev_key"]])

        def auto_detect(self, action_name):
            data, widget = self.ACTIONS[action_name], self.widgets[data["key"]]
            detect_dialog = QDialog(self); detect_dialog.setWindowTitle(f"{action_name} Algılanıyor...")
            detect_dialog.setLayout(QVBoxLayout()); detect_dialog.layout().addWidget(QLabel("Lütfen istediğiniz düğmeye basın veya ekseni/POV'u hareket ettirin."))
            detect_dialog.show()
            pygame.event.clear(); found, start_time = False, time.time()
            while not found and time.time() - start_time < 5:
                QApplication.processEvents()
                for event in pygame.event.get():
                    detected_text = None
                    if data["type"] == "axis" and event.type == pygame.JOYAXISMOTION and abs(event.value) > 0.8: detected_text, found = f"Eksen {event.axis}", True
                    elif data["type"] == "button" and event.type == pygame.JOYBUTTONDOWN: detected_text, found = f"Düğme {event.button}", True
                    elif data["type"] == "button" and event.type == pygame.JOYHATMOTION:
                        hat_id, value = event.hat, event.value
                        if value == (0, 1): detected_text = f"Hat {hat_id} Yukarı"
                        elif value == (0, -1): detected_text = f"Hat {hat_id} Aşağı"
                        elif value == (-1, 0): detected_text = f"Hat {hat_id} Sol"
                        elif value == (1, 0): detected_text = f"Hat {hat_id} Sağ"
                        if detected_text: found = True
                    if found and detected_text:
                        index = widget.findText(detected_text)
                        if index > -1: widget.setCurrentIndex(index)
                        break
            detect_dialog.close()

        def save_and_accept(self):
            new_config = {}
            for data in self.ACTIONS.values():
                text = self.widgets[data["key"]].currentText()
                if text != "-": new_config[data["key"]] = text
                if data.get("rev_key"): new_config[data["rev_key"]] = self.widgets[data["rev_key"]].isChecked()
            self.config_saved.emit(new_config); self.accept()

    class JoystickHandler(QObject):
        axis_moved = pyqtSignal(int, float); button_pressed = pyqtSignal(int)
        button_released = pyqtSignal(int); joystick_disconnected = pyqtSignal()
        hat_moved = pyqtSignal(int, tuple)

        def __init__(self):
            super().__init__(); self._stop_event = threading.Event(); self.joystick = None

        def run(self):
            pygame.joystick.init()
            if pygame.joystick.get_count() > 0: self.joystick = pygame.joystick.Joystick(0); self.joystick.init()
            else: self.joystick_disconnected.emit(); return
            while not self._stop_event.is_set():
                for event in pygame.event.get():
                    if event.type == pygame.JOYAXISMOTION:
                        value = self.joystick.get_axis(event.axis)
                        if abs(value) < 0.1: value = 0.0
                        self.axis_moved.emit(event.axis, value)
                    elif event.type == pygame.JOYBUTTONDOWN: self.button_pressed.emit(event.button)
                    elif event.type == pygame.JOYBUTTONUP: self.button_released.emit(event.button)
                    elif event.type == pygame.JOYHATMOTION: self.hat_moved.emit(event.hat, event.value)
                time.sleep(0.01)
                
        def stop(self): self._stop_event.set()

class GimbalGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.cam=None; self.gimbal_speed=50; self.motion_modes={"Kilit Modu":3, "Takip Modu":4, "FPV Modu":5}; self.record_map={0:"Durdu", 1:"Kaydediyor", 2:"Kart Yok", 3:"Veri Kaybı"}
        self.mode_map={0:"Kilit", 1:"Takip", 2:"FPV"}; self.mount_map={1:"Normal", 2:"Ters"}; self.hdr_map={0:"Kapalı", 1:"Açık"}
        self.tracker_socket=None; self.tracker_client_addr=None
        self.tracker_handler_thread=None; self.tracker_thread_stop_flag=threading.Event(); self.interface_socket=None
        self.tracker_dx=0; self.tracker_dy=0; self.tracker_dz=0.0; self.tracker_status=0; self.gui_tracker_enabled=False; self.is_manual_control=False; self.yaw_integral_error=0.0; self.pitch_integral_error=0.0
        self.yaw_error = 0.0; self.pitch_error = 0.0
        self.last_control_time=time.time(); self.target_lat=0.0; self.target_lon=0.0; self.target_alt=0.0; self.tracker_data_queue=queue.Queue()
        self.last_tracker_data_time = 0
        self.joystick_handler=None; self.joystick_thread=None; self.joystick_values={}
        self.joystick_config = self.load_joystick_config()
        self.gui_config = self.load_gui_config()
        self._define_stylesheets(); self.is_dark_theme=True
        self.image_tracker_reset_flag = 0
        
        self.filtered_dx = 0.0
        self.filtered_dy = 0.0
        self.filtered_heading = 0.0
        self.filtered_pitch = 0.0
        
        self.prev_target_lat = 0.0
        self.prev_target_lon = 0.0
        self.prev_target_alt = 0.0
        self.last_target_update_time = time.time()

        self.current_target_heading = 0.0
        self.current_target_velocity = 0.0

        self.velocity_buffer = []
        self.heading_buffer = []
        self.MEDIAN_FILTER_WINDOW_SIZE = 30
        
        # --- Veri Kaydı (Loglama) Durumları ---
        self.is_logging = False
        self.log_file = None
        self.csv_writer = None
        
        # Yumuşatma Filtresi Değişkenleri
        self.filter_initialized = False
        self.smoothed_lat = 0.0
        self.lat_trend = 0.0
        self.smoothed_lon = 0.0
        self.lon_trend = 0.0
        self.smoothed_alt = 0.0
        self.alt_trend = 0.0
        
        self.initUI()
        self.main_update_timer=QTimer(self); self.main_update_timer.timeout.connect(self._main_update_loop); self.loop_counter=0
        self.blink_timer=QTimer(self); self.blink_timer.timeout.connect(self.toggle_tracker_button_blink); self.blink_on=False
    
    def initUI(self):
        self.setWindowTitle('CCK Gimbal Kontrol Paneli'); self.setGeometry(100,100,1600,800); self._apply_stylesheet(self.dark_style)
        main_layout=QVBoxLayout(self); top_layout = QHBoxLayout(); bottom_layout = QHBoxLayout()
        top_layout.addWidget(self.create_settings_group(), 3); top_layout.addWidget(self.create_status_group(), 4); top_layout.addWidget(self.create_tracker_control_group(), 3)
        main_layout.addWidget(self.create_connection_group()); main_layout.addLayout(top_layout)
        main_layout.addWidget(self.create_movement_group()); main_layout.addWidget(self.create_camera_actions_group()); main_layout.addWidget(self.create_focus_group())
        
        bottom_layout.addWidget(self.create_tracker_group())
        bottom_layout.addWidget(self.create_interface_service_group())
        bottom_layout.addWidget(self.create_logging_group())
        main_layout.addLayout(bottom_layout)

        self.toggle_controls(False)
        if PYGAME_AVAILABLE:
            self.setup_joystick()

    # --- Core Logic & Main Loop ---
    def _calculate_focal_length(self, zoom_level, curve_factor=1.0):
        MIN_FOCAL_LENGTH = 4.5; MAX_FOCAL_LENGTH = 148.4; MAX_OPTICAL_ZOOM = 30.0; DIGITAL_ZOOM_DAMPENING_FACTOR = 0.5
        if zoom_level > MAX_OPTICAL_ZOOM:
            dampened_ratio = math.pow(zoom_level / MAX_OPTICAL_ZOOM, DIGITAL_ZOOM_DAMPENING_FACTOR)
            return MAX_FOCAL_LENGTH * dampened_ratio
        if zoom_level <= 1.0: return MIN_FOCAL_LENGTH
        log_zoom_ratio = math.log(zoom_level) / math.log(MAX_OPTICAL_ZOOM)
        curved_ratio = math.pow(log_zoom_ratio, curve_factor)
        focal_length = MIN_FOCAL_LENGTH * math.pow(MAX_FOCAL_LENGTH / MIN_FOCAL_LENGTH, curved_ratio)
        return focal_length
    
    def _haversine_distance(self, lat1, lon1, lat2, lon2):
        R = 6371000; lat1_rad, lon1_rad = math.radians(lat1), math.radians(lon1); lat2_rad, lon2_rad = math.radians(lat2), math.radians(lon2)
        dlat, dlon = lat2_rad - lat1_rad, lon2_rad - lon1_rad
        a = math.sin(dlat / 2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)); return R * c

    def _calculate_bearing(self, lat1, lon1, lat2, lon2):
        lat1_rad, lon1_rad = math.radians(lat1), math.radians(lon1); lat2_rad, lon2_rad = math.radians(lat2), math.radians(lon2)
        dlon = lon2_rad - lon1_rad
        y = math.sin(dlon) * math.cos(lat2_rad); x = math.cos(lat1_rad) * math.sin(lat2_rad) - math.sin(lat1_rad) * math.cos(lat2_rad) * math.cos(dlon)
        bearing_rad = math.atan2(y, x); return (math.degrees(bearing_rad) + 360) % 360
    
    def _apply_median_filter(self, new_value, buffer):
        buffer.append(new_value)
        if len(buffer) > self.MEDIAN_FILTER_WINDOW_SIZE: buffer.pop(0)
        if not buffer: return 0.0
        sorted_buffer, mid = sorted(buffer), len(buffer) // 2
        return (sorted_buffer[mid - 1] + sorted_buffer[mid]) / 2 if len(sorted_buffer) % 2 == 0 else sorted_buffer[mid]
    
    def _apply_angular_median_filter(self, new_value, buffer):
        buffer.append(new_value)
        if len(buffer) > self.MEDIAN_FILTER_WINDOW_SIZE: buffer.pop(0)
        if not buffer: return 0.0
        sorted_buffer = sorted(buffer)
        if len(sorted_buffer) > 2 and (sorted_buffer[-1] - sorted_buffer[0]) > 180.0:
            shifted_buffer = sorted([val + 360 if val < 180 else val for val in sorted_buffer])
        else: shifted_buffer = sorted_buffer
        mid = len(shifted_buffer) // 2
        median = (shifted_buffer[mid - 1] + shifted_buffer[mid]) / 2.0 if len(shifted_buffer) % 2 == 0 else shifted_buffer[mid]
        return median % 360.0

    def _send_focal_length_response(self, focal_length, zoom, gimbal_tracker_status):
        if self.tracker_socket and self.tracker_client_addr:
            try:
                response_data = {"focal_length": round(focal_length, 2), "zoom": round(zoom, 2), "gimbal_tracker_status": gimbal_tracker_status, "image_tracker_reset": self.image_tracker_reset_flag}
                self.tracker_socket.sendto(json.dumps(response_data).encode('utf-8'), self.tracker_client_addr)
            except (socket.error, Exception): pass
    
    def _main_update_loop(self):
        if not(self.cam and self.cam.isConnected()): return
        if self.tracker_button.isChecked() and self.tracker_client_addr and self.last_tracker_data_time != 0 and (time.time() - self.last_tracker_data_time > 2.0):
            print("Tracker data timeout!"); self.reset_tracker_state()
        self.loop_counter+=1 
        raw_yaw,raw_pitch,raw_roll,zoom,info=self._get_data_from_sources()
        heading,pitch,roll=self._process_and_calculate_values(raw_yaw,raw_pitch,raw_roll)
        focal_length = self._calculate_focal_length(zoom,curve_factor=1.25)
        self._send_focal_length_response(focal_length, zoom, 1 if self.gui_tracker_enabled else 0)
        is_tracking=self.gui_tracker_enabled and self.tracker_status==1
        self._execute_control_logic(is_tracking)
        self._update_target_kinematics(is_tracking)
        self._update_gui_widgets(raw_yaw,heading,pitch,roll,zoom,focal_length,info,is_tracking)
        if self.loop_counter%3==0: self._send_service_data(heading,is_tracking)

        if self.is_logging and self.loop_counter % 5 == 0:
            log_data = collections.OrderedDict()
            # --- Sensör ve Hesaplanan Veriler ---
            log_data['raw_yaw'] = f"{raw_yaw:.2f}"; log_data['raw_pitch'] = f"{raw_pitch:.2f}"; log_data['raw_roll'] = f"{raw_roll:.2f}"
            log_data['filtered_heading'] = f"{heading:.2f}"; log_data['filtered_pitch'] = f"{pitch:.2f}"
            log_data['zoom_level'] = f"{zoom:.1f}"; log_data['focal_length'] = f"{focal_length:.1f}"
            log_data['record_state'] = info.record_state; log_data['motion_mode'] = info.motion_mode
            log_data['mount_dir'] = info.mount_dir; log_data['hdr_state'] = info.hdr_sta
            log_data['tracker_status'] = self.tracker_status; log_data['tracker_dx'] = self.tracker_dx
            log_data['tracker_dy'] = self.tracker_dy; log_data['tracker_dz'] = f"{self.tracker_dz:.2f}"
            log_data['is_gui_tracking_enabled'] = self.gui_tracker_enabled
            log_data['target_latitude'] = f"{self.target_lat:.7f}"; log_data['target_longitude'] = f"{self.target_lon:.7f}"
            log_data['target_altitude'] = f"{self.target_alt:.2f}"; log_data['target_velocity'] = f"{self.current_target_velocity:.2f}"
            log_data['target_heading'] = f"{self.current_target_heading:.2f}"; log_data['yaw_pi_error'] = f"{self.yaw_error:.2f}"
            log_data['pitch_pi_error'] = f"{self.pitch_error:.2f}"; log_data['yaw_pi_integrator'] = f"{self.yaw_integral_error:.2f}"
            log_data['pitch_pi_integrator'] = f"{self.pitch_integral_error:.2f}"
            # --- Arayüzden Girilen Değerler ---
            log_data['kp_yaw'] = self.kp_yaw_input.text(); log_data['ki_yaw'] = self.ki_yaw_input.text()
            log_data['kp_pitch'] = self.kp_pitch_input.text(); log_data['ki_pitch'] = self.ki_pitch_input.text()
            log_data['pixel_filter_alpha'] = self.filter_alpha_input.text(); log_data['pi_speed_limit'] = self.pi_speed_limit_input.text()
            log_data['gimbal_filter_alpha'] = self.gimbal_filter_alpha_input.text()
            log_data['max_jump_distance'] = self.max_jump_distance_input.text()
            log_data['smoothing_alpha'] = self.smoothing_alpha_input.text()
            log_data['smoothing_beta'] = self.smoothing_beta_input.text()
            log_data['gimbal_lat_input'] = self.gimbal_lat_input.text(); log_data['gimbal_lon_input'] = self.gimbal_lon_input.text()
            log_data['gimbal_alt_input'] = self.gimbal_alt_input.text(); log_data['north_offset_input'] = self.true_north_offset_input.text()
            log_data['home_lat_input'] = self.home_lat_input.text(); log_data['home_lon_input'] = self.home_lon_input.text()
            log_data['home_alt_input'] = self.home_alt_input.text(); log_data['min_speed_input'] = self.min_speed_input.text()
            log_data['max_speed_input'] = self.max_speed_input.text()
            self._write_log_entry(log_data)

    def _get_data_from_sources(self):
        try: 
            tracker_data = self.tracker_data_queue.get_nowait()
            raw_dx = tracker_data.get('dx', 0); raw_dy = tracker_data.get('dy', 0)
            try: alpha = max(0.0, min(1.0, float(self.filter_alpha_input.text())))
            except (ValueError, TypeError): alpha = 0.3
            self.filtered_dx = (alpha * raw_dx) + (1 - alpha) * self.filtered_dx
            self.filtered_dy = (alpha * raw_dy) + (1 - alpha) * self.filtered_dy
            self.tracker_dx = int(self.filtered_dx); self.tracker_dy = int(self.filtered_dy)
            raw_dz  = tracker_data.get('dz', 0.0)
            self.tracker_dz = (alpha * raw_dz) + (1 - alpha) * self.tracker_dz
            self.tracker_status = tracker_data.get('tracker_status', 0)
            self.last_tracker_data_time = time.time()
        except queue.Empty: pass
        raw_yaw, raw_pitch, raw_roll = self.cam.getAttitude()
        zoom = self.cam.getCurrentZoomLevel(); info = self.cam.getGimbalInfo()
        return raw_yaw, raw_pitch, raw_roll, zoom, info

    def _process_and_calculate_values(self,raw_yaw,raw_pitch,raw_roll):
        normalized_pitch=(raw_pitch+360)%360; raw_pitch_processed=180.0-normalized_pitch; raw_pitch_processed=max(-90.0,min(90.0,raw_pitch_processed)); roll=-raw_roll
        try: true_north_offset=float(self.true_north_offset_input.text())
        except(ValueError,TypeError): true_north_offset=0.0
        raw_heading=(raw_yaw+true_north_offset)%360
        try: alpha = max(0.0, min(1.0, float(self.gimbal_filter_alpha_input.text())))
        except(ValueError,TypeError): alpha = 0.2
        if self.filtered_heading == 0.0 and self.filtered_pitch == 0.0:
            self.filtered_heading, self.filtered_pitch = raw_heading, raw_pitch_processed
        diff = (raw_heading - self.filtered_heading + 180) % 360 - 180
        self.filtered_heading = (self.filtered_heading + alpha * diff + 360) % 360
        self.filtered_pitch = (alpha * raw_pitch_processed) + (1 - alpha) * self.filtered_pitch
        return self.filtered_heading,self.filtered_pitch,roll
        
    def _execute_control_logic(self, is_tracking):
        if self.is_manual_control: return
        if not self.gui_tracker_enabled:
            if not PYGAME_AVAILABLE: return
            try: min_speed, max_speed = int(self.min_speed_input.text()), int(self.max_speed_input.text())
            except ValueError: min_speed, max_speed = 1, 100
            speed_range = max_speed - min_speed
            speed_axis_str, yaw_axis_str, pitch_axis_str = self.joystick_config.get("SPEED_AXIS"), self.joystick_config.get("YAW_AXIS"), self.joystick_config.get("PITCH_AXIS")
            speed_axis_index, yaw_axis_index, pitch_axis_index = -1, -1, -1
            if isinstance(speed_axis_str, str) and speed_axis_str.startswith("Eksen "): speed_axis_index = int(speed_axis_str.split(" ")[-1])
            if isinstance(yaw_axis_str, str) and yaw_axis_str.startswith("Eksen "): yaw_axis_index = int(yaw_axis_str.split(" ")[-1])
            if isinstance(pitch_axis_str, str) and pitch_axis_str.startswith("Eksen "): pitch_axis_index = int(pitch_axis_str.split(" ")[-1])
            speed_axis_val=self.joystick_values.get(speed_axis_index,-1.0);joystick_yaw_val=self.joystick_values.get(yaw_axis_index,0.0);joystick_pitch_val=self.joystick_values.get(pitch_axis_index,0.0)
            if self.joystick_config.get("REVERSE_SPEED"): speed_axis_val *= -1
            if speed_axis_val > -0.99:
                new_speed = int(min_speed + speed_range * ((speed_axis_val + 1.0) / 2.0))
                if abs(new_speed - self.gimbal_speed) > 1: self.speed_slider.setValue(new_speed)
            if self.joystick_config.get("REVERSE_YAW"): joystick_yaw_val *= -1
            if self.joystick_config.get("REVERSE_PITCH"): joystick_pitch_val *= -1
            if abs(joystick_yaw_val) > 0 or abs(joystick_pitch_val) > 0:
                self.cam.setGimbalSpeed(int(self.gimbal_speed*joystick_yaw_val),int(-self.gimbal_speed*joystick_pitch_val)); return
        self._run_pi_controller(is_tracking)

    def _update_target_kinematics(self, is_tracking):
        if is_tracking and self.target_lat != 0.0 and self.prev_target_lat != 0.0:
            current_time, dt = time.time(), time.time() - self.last_target_update_time
            if dt > 0.01:
                horizontal_dist = self._haversine_distance(self.prev_target_lat, self.prev_target_lon, self.target_lat, self.target_lon)
                raw_velocity = math.sqrt(horizontal_dist**2 + (self.target_alt-self.prev_target_alt)**2) / dt
                self.current_target_velocity = self._apply_median_filter(raw_velocity, self.velocity_buffer)
                raw_heading = self._calculate_bearing(self.prev_target_lat, self.prev_target_lon, self.target_lat, self.target_lon)
                self.current_target_heading = self._apply_angular_median_filter(raw_heading, self.heading_buffer)
            self.prev_target_lat,self.prev_target_lon,self.prev_target_alt=self.target_lat,self.target_lon,self.target_alt
            self.last_target_update_time = current_time
        elif is_tracking and self.target_lat != 0.0 and self.prev_target_lat == 0.0:
            self.prev_target_lat,self.prev_target_lon,self.prev_target_alt = self.target_lat,self.target_lon,self.target_alt
            self.last_target_update_time = time.time()
            self.current_target_velocity, self.current_target_heading = 0.0, 0.0
            self.velocity_buffer.clear(); self.heading_buffer.clear()
        elif not is_tracking:
            self.prev_target_lat,self.prev_target_lon,self.prev_target_alt=0.0,0.0,0.0
            self.current_target_heading, self.current_target_velocity = 0.0, 0.0
            self.velocity_buffer.clear(); self.heading_buffer.clear()

    def _update_gui_widgets(self,raw_yaw,heading,pitch,roll,zoom,focal_length,info,is_tracking):

        self.attitude_widget.set_attitude(heading,pitch,roll); self.yaw_value.setText(f"{raw_yaw:.2f}°(H:{heading:.2f}°)"); self.pitch_value.setText(f"{pitch:.2f}°"); self.roll_value.setText(f"{roll:.2f}°")
        self.zoom_value.setText(f"{zoom:.1f}x"); self.focal_length_value.setText(f"{focal_length:.1f} mm"); self.record_value.setText(f"{self.record_map.get(info.record_state,'-')}")
        self.mode_value.setText(f"{self.mode_map.get(info.motion_mode,'-')}"); self.mount_value.setText(f"{self.mount_map.get(info.mount_dir,'-')}"); self.hdr_value.setText(f"{self.hdr_map.get(info.hdr_sta,'-')}")
        self.tracker_status_label.setText(f"{self.tracker_status}"); self.dx_label.setText(f"{self.tracker_dx}"); self.dy_label.setText(f"{self.tracker_dy}"); self.dz_label.setText(f"{self.tracker_dz:.2f}")
        
        if is_tracking:
            try:
                # Gerekli verileri al
                gimbal_lat,gimbal_lon,gimbal_alt=(float(self.gimbal_lat_input.text()),float(self.gimbal_lon_input.text()),float(self.gimbal_alt_input.text()))
                alpha = float(self.smoothing_alpha_input.text())
                beta = float(self.smoothing_beta_input.text())

                # Ham hedef koordinatlarını hesapla
                raw_target_lat, raw_target_lon, raw_target_alt = self.calculate_target_coordinates(gimbal_lat,gimbal_lon,gimbal_alt,heading,pitch,self.tracker_dz)

                if not self.filter_initialized:
                    self._initialize_smoothing(raw_target_lat, raw_target_lon, raw_target_alt)
                    self.filter_initialized = True
                else:
                    self._apply_smoothing(raw_target_lat, raw_target_lon, raw_target_alt, alpha, beta)

                # Nihai yumuşatılmış hedefi `self.target_*` değişkenlerine ata
                self.target_lat, self.target_lon, self.target_alt = self.smoothed_lat, self.smoothed_lon, self.smoothed_alt

                # GUI'yi güncelle
                self.target_lat_label.setText(f"{self.target_lat:.7f}"); self.target_lon_label.setText(f"{self.target_lon:.7f}"); self.target_alt_label.setText(f"{self.target_alt:.2f} m")
                self.target_heading_label.setText(f"{self.current_target_heading:.2f}°"); self.target_velocity_label.setText(f"{self.current_target_velocity:.2f} m/s")
                
            except (ValueError, TypeError):
                self.target_lat_label.setText("Hatalı Veri"); self.target_lon_label.setText("Hatalı Veri"); self.target_alt_label.setText("Hatalı Veri")

            # PI Kontrolcü hata göstergelerini güncelle
            self.yaw_error_label.setText(f"{self.yaw_error:.2f}"); self.pitch_error_label.setText(f"{self.pitch_error:.2f}")
            self.yaw_integrator_label.setText(f"{self.yaw_integral_error:.2f}"); self.pitch_integrator_label.setText(f"{self.pitch_integral_error:.2f}")
        else: 
            self.reset_target_info()
        
        if self.tracker_status==1 and not self.gui_tracker_enabled:
            if not self.blink_timer.isActive(): self.blink_timer.start(300)
        else:
            if self.blink_timer.isActive(): self.blink_timer.stop()
            self.start_tracker_button.setStyleSheet("")

    def _send_service_data(self,heading,is_tracking):
        if self.interface_socket:
            try:
                gimbal_lat, gimbal_lon, gimbal_alt = float(self.gimbal_lat_input.text()), float(self.gimbal_lon_input.text()), float(self.gimbal_alt_input.text())
                target_status = 1 if is_tracking else 0
                if target_status == 1:
                    target_payload = {"target_latitude": round(self.target_lat,7), "target_longitude": round(self.target_lon,7), "target_altitude": round(self.target_alt,2) - 5, "target_status": target_status, "target_heading": round(self.current_target_heading,2), "target_velocity": round(self.current_target_velocity,2)}
                else:
                    try: home_lat, home_lon, home_alt = float(self.home_lat_input.text()), float(self.home_lon_input.text()), float(self.home_alt_input.text())
                    except (ValueError, TypeError): home_lat, home_lon, home_alt = 0.0, 0.0, 0.0
                    target_payload = {"target_latitude": home_lat, "target_longitude": home_lon, "target_altitude": home_alt, "target_status": target_status, "target_heading": 0.0, "target_velocity": 0.0}
                data_to_send = {"target": target_payload, "gimbal": {"gimbal_latitude": round(gimbal_lat,14), "gimbal_longitude": round(gimbal_lon,14), "gimbal_altitude": round(gimbal_alt,2), "gimbal_heading": round(heading,0)}, "tracker": {"tracker_x":0.0,"tracker_y":0.0,"tracker_z":0.0,"tracker_status":0.0}}
                message = json.dumps(data_to_send, indent=4).encode('utf-8')
                target_ip, target_port = self.interface_ip_input.text(), int(self.interface_port_input.text())
                self.interface_socket.sendto(message, (target_ip, target_port))
            except(ValueError, socket.error): pass
    
    # --- Configuration Management ---
    def load_gui_config(self):
        try:
            with open("gui_config.json", 'r') as f: return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {"kp_yaw":"0.8","ki_yaw":"0.01","kp_pitch":"0.8","ki_pitch":"0.01","gimbal_lat":"0.0","gimbal_lon":"0.0","gimbal_alt":"0.0","home_lat":"0.0","home_lon":"0.0","home_alt":"0.0","north_offset":"0.0","filter_alpha":"0.3","gimbal_filter_alpha":"0.2","pi_speed_limit":"100","connection_ip":"192.168.144.25","connection_port":"37260","min_speed":"5","max_speed":"100","tracker_listen_ip":"0.0.0.0","tracker_listen_port":"8888","interface_target_ip":"127.0.0.1","interface_target_port":"8889", "max_jump_distance": "50.0", "smoothing_alpha": "0.4", "smoothing_beta": "0.2"}

    def save_gui_config(self):
        config_to_save = {
            "kp_yaw": self.kp_yaw_input.text(), "ki_yaw": self.ki_yaw_input.text(),
            "kp_pitch": self.kp_pitch_input.text(), "ki_pitch": self.ki_pitch_input.text(),
            "gimbal_lat": self.gimbal_lat_input.text(), "gimbal_lon": self.gimbal_lon_input.text(),
            "gimbal_alt": self.gimbal_alt_input.text(), "home_lat": self.home_lat_input.text(),
            "home_lon": self.home_lon_input.text(), "home_alt": self.home_alt_input.text(),
            "north_offset": self.true_north_offset_input.text(), "filter_alpha": self.filter_alpha_input.text(),
            "gimbal_filter_alpha": self.gimbal_filter_alpha_input.text(), "pi_speed_limit": self.pi_speed_limit_input.text(),
            "connection_ip": self.ip_input.text(), "connection_port": self.port_input.text(),
            "min_speed": self.min_speed_input.text(), "max_speed": self.max_speed_input.text(),
            "tracker_listen_ip": self.tracker_ip_input.text(), "tracker_listen_port": self.tracker_port_input.text(),
            "interface_target_ip": self.interface_ip_input.text(), "interface_target_port": self.interface_port_input.text(),
            "max_jump_distance": self.max_jump_distance_input.text(),
            "smoothing_alpha": self.smoothing_alpha_input.text(),
            "smoothing_beta": self.smoothing_beta_input.text()
        }
        try:
            with open("gui_config.json", 'w') as f: json.dump(config_to_save, f, indent=4)
        except Exception as e: print(f"GUI yapılandırması kaydedilemedi: {e}")
    
    def load_joystick_config(self):
        try:
            with open("joystick_config.json",'r') as f: return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {"YAW_AXIS":0,"REVERSE_YAW":False,"PITCH_AXIS":1,"REVERSE_PITCH":True,"SPEED_AXIS":2,"REVERSE_SPEED":False,"PHOTO_BUTTON":1,"RECORD_BUTTON":0,"TRACK_START_BUTTON":2,"TRACK_STOP_BUTTON":3,"TRACK_RESET_BUTTON":-1,"ZOOM_IN_BUTTON":-1,"ZOOM_OUT_BUTTON":-1,"FOCUS_NEAR_BUTTON":-1,"FOCUS_FAR_BUTTON":-1}

    def save_joystick_config(self,config):
        try:
            with open("joystick_config.json",'w')as f:json.dump(config,f,indent=4)
        except Exception as e:print(f"Joystick yapılandırması kaydedilemedi: {e}")
    
    # --- Joystick Methods ---
    def open_joystick_config(self):
        if not PYGAME_AVAILABLE: return
        dialog=JoystickConfigDialog(self.joystick_config,self);dialog.config_saved.connect(self.update_joystick_config);dialog.exec_()
    
    def update_joystick_config(self,new_config):
        self.joystick_config=new_config;self.save_joystick_config(new_config)
        if PYGAME_AVAILABLE: self.setup_joystick()
        print("Joystick ayarları güncellendi ve kaydedildi.")
    
    def setup_joystick(self):
        if not PYGAME_AVAILABLE: return
        if self.joystick_thread and self.joystick_thread.is_alive():
            self.joystick_handler.stop(); self.joystick_thread.join()
        self.joystick_handler = JoystickHandler(); self.joystick_thread = threading.Thread(target=self.joystick_handler.run, daemon=True)
        self.joystick_handler.axis_moved.connect(self._handle_joystick_axis)
        self.joystick_handler.button_pressed.connect(self._handle_joystick_button_press)
        self.joystick_handler.button_released.connect(self._handle_joystick_button_release)
        self.joystick_handler.hat_moved.connect(self._handle_joystick_hat)
        self.joystick_handler.joystick_disconnected.connect(lambda:print("Joystick bağlı değil!"))
        self.joystick_thread.start()

    def _handle_joystick_axis(self, axis, value): self.joystick_values[axis]=value
    
    def _handle_joystick_button_press(self, button):
        config,button_str = self.joystick_config,f"Düğme {button}" 
        if config.get("PHOTO_BUTTON")==button_str: self.take_photo()
        if config.get("RECORD_BUTTON")==button_str: self.toggle_record()
        if config.get("TRACK_START_BUTTON")==button_str: self.start_gui_tracker()
        if config.get("TRACK_STOP_BUTTON")==button_str: self.stop_gui_tracker()
        if config.get("TRACK_RESET_BUTTON")==button_str: self.trigger_image_tracker_reset()
        if config.get("ZOOM_IN_BUTTON")==button_str: self.start_zoom(1)
        if config.get("ZOOM_OUT_BUTTON")==button_str: self.start_zoom(-1)
        if config.get("FOCUS_NEAR_BUTTON")==button_str: self.start_manual_focus(1)
        if config.get("FOCUS_FAR_BUTTON")==button_str: self.start_manual_focus(-1)

    def _handle_joystick_button_release(self, button):
        config,button_str = self.joystick_config,f"Düğme {button}"
        if config.get("ZOOM_IN_BUTTON")==button_str or config.get("ZOOM_OUT_BUTTON")==button_str: self.stop_zoom()
        if config.get("FOCUS_NEAR_BUTTON")==button_str or config.get("FOCUS_FAR_BUTTON")==button_str: self.stop_manual_focus()
    
    def _handle_joystick_hat(self, hat_id, value):
        config,hat_str=self.joystick_config,None
        if value==(0,1): hat_str=f"Hat {hat_id} Yukarı"
        elif value==(0,-1): hat_str=f"Hat {hat_id} Aşağı"
        elif value==(-1,0): hat_str=f"Hat {hat_id} Sol"
        elif value==(1,0): hat_str=f"Hat {hat_id} Sağ"
        if config.get("PHOTO_BUTTON")==hat_str: self.take_photo()
        if config.get("RECORD_BUTTON")==hat_str: self.toggle_record()
        if config.get("TRACK_START_BUTTON")==hat_str: self.start_gui_tracker()
        if config.get("TRACK_STOP_BUTTON")==hat_str: self.stop_gui_tracker()
        if config.get("TRACK_RESET_BUTTON")==hat_str: self.trigger_image_tracker_reset()
        is_zoom_in=config.get("ZOOM_IN_BUTTON")==hat_str; is_zoom_out=config.get("ZOOM_OUT_BUTTON")==hat_str
        is_focus_near=config.get("FOCUS_NEAR_BUTTON")==hat_str; is_focus_far=config.get("FOCUS_FAR_BUTTON")==hat_str
        if is_zoom_in: self.start_zoom(1)
        elif is_zoom_out: self.start_zoom(-1)
        if is_focus_near: self.start_manual_focus(1)
        elif is_focus_far: self.start_manual_focus(-1)
        if value == (0, 0):
            zoom_in_binding,zoom_out_binding=config.get("ZOOM_IN_BUTTON",""),config.get("ZOOM_OUT_BUTTON","")
            focus_near_binding,focus_far_binding=config.get("FOCUS_NEAR_BUTTON",""),config.get("FOCUS_FAR_BUTTON","")
            should_stop_zoom=(zoom_in_binding.startswith(f"Hat {hat_id}") or zoom_out_binding.startswith(f"Hat {hat_id}"))
            should_stop_focus=(focus_near_binding.startswith(f"Hat {hat_id}") or focus_far_binding.startswith(f"Hat {hat_id}"))
            if should_stop_zoom: self.stop_zoom()
            if should_stop_focus: self.stop_manual_focus()
    
    # --- Service & Communication Methods ---
    def receive_tracker_data_loop(self):
        while not self.tracker_thread_stop_flag.is_set():
            try:
                data, addr = self.tracker_socket.recvfrom(1024)
                if not data: continue
                if self.tracker_client_addr != addr:
                    print(f"Görüntü işleme istemcisinden ilk veri alındı: {addr}")
                    self.tracker_client_addr=addr; self.last_tracker_data_time=time.time()
                try:
                    self.tracker_data_queue.put(json.loads(data.decode('utf-8')))
                except (json.JSONDecodeError, UnicodeDecodeError) as e: print(f"Hatalı tracker verisi: {e}. Alınan: {data}")
            except socket.error:
                if self.tracker_thread_stop_flag.is_set(): break
                else: print(f"Tracker soket hatası."); break
            except Exception as e: print(f"Tracker dinleme döngüsünde beklenmedik hata: {e}"); break
        print("Tracker dinleme döngüsü durdu.")

    # --- UI Creation Methods ---
    def create_status_group(self):
        group_box=QGroupBox("Gimbal Durumu"); group_box.setObjectName("StatusGroup"); main_layout=QHBoxLayout(); self.attitude_widget=AttitudeIndicator(); main_layout.addWidget(self.attitude_widget,1); main_layout.addSpacing(15); text_layout=QGridLayout()
        self.yaw_value=QLabel("-");self.pitch_value=QLabel("-");self.roll_value=QLabel("-");self.zoom_value=QLabel("-");self.focal_length_value=QLabel("-");self.record_value=QLabel("-");self.mode_value=QLabel("-");self.mount_value=QLabel("-");self.hdr_value=QLabel("-");self.model_value=QLabel("-")
        labels={"Sapma:":self.yaw_value,"Tırmanış:":self.pitch_value,"Yatış:":self.roll_value,"Yakınlaştırma:":self.zoom_value,"Odak Uzaklığı:":self.focal_length_value,"Kayıt:":self.record_value,"Mod:":self.mode_value,"Yön:":self.mount_value,"HDR:":self.hdr_value,"Model:":self.model_value}
        for row,(header_text,value_label) in enumerate(labels.items()):
            header_label=QLabel(header_text);header_label.setObjectName("StatusHeader");value_label.setObjectName("StatusValue");text_layout.addWidget(header_label,row,0);text_layout.addWidget(value_label,row,1)
        text_layout.setColumnStretch(2,1);main_layout.addLayout(text_layout,1);group_box.setLayout(main_layout);return group_box
    
    def create_tracker_control_group(self):
        group_box=QGroupBox("Görüntü Takip"); group_box.setObjectName("TrackerControlGroup"); main_h_layout=QHBoxLayout(); left_layout=QGridLayout()
        self.kp_yaw_input = QLineEdit(self.gui_config.get("kp_yaw")); self.ki_yaw_input = QLineEdit(self.gui_config.get("ki_yaw")); self.kp_pitch_input = QLineEdit(self.gui_config.get("kp_pitch")); self.ki_pitch_input = QLineEdit(self.gui_config.get("ki_pitch"))
        left_layout.addWidget(QLabel("Yönelim Kp:"),0,0); left_layout.addWidget(self.kp_yaw_input,0,1); left_layout.addWidget(QLabel("Yönelim Ki:"),1,0); left_layout.addWidget(self.ki_yaw_input,1,1)
        left_layout.addWidget(QLabel("Yükseliş Kp:"),0,2); left_layout.addWidget(self.kp_pitch_input,0,3); left_layout.addWidget(QLabel("Yükseliş Ki:"),1,2); left_layout.addWidget(self.ki_pitch_input,1,3)
        self.filter_alpha_input=QLineEdit(self.gui_config.get("filter_alpha","0.3")); self.pi_speed_limit_input=QLineEdit(self.gui_config.get("pi_speed_limit","100")); self.gimbal_filter_alpha_input=QLineEdit(self.gui_config.get("gimbal_filter_alpha","0.2"))
        left_layout.addWidget(QLabel("Piksel Filtre Alpha:"),2,0); left_layout.addWidget(self.filter_alpha_input,2,1); left_layout.addWidget(QLabel("PI Hız Limiti (%):"),2,2); left_layout.addWidget(self.pi_speed_limit_input,2,3)
        left_layout.addWidget(QLabel("Gimbal Filtre Alpha:"),3,0); left_layout.addWidget(self.gimbal_filter_alpha_input,3,1)

        self.max_jump_distance_input=QLineEdit(self.gui_config.get("max_jump_distance", "50.0"))
        self.smoothing_alpha_input=QLineEdit(self.gui_config.get("smoothing_alpha", "0.4"))
        self.smoothing_beta_input=QLineEdit(self.gui_config.get("smoothing_beta", "0.2"))

        # left_layout.addWidget(QLabel("Maks. Sıçrama (m):"), 3, 2); left_layout.addWidget(self.max_jump_distance_input, 3, 3)
        
        left_layout.addWidget(QLabel("Konum Düzeltme α:"), 4, 0); left_layout.addWidget(self.smoothing_alpha_input, 4, 1)
        left_layout.addWidget(QLabel("Trend Düzeltme β:"), 4, 2); left_layout.addWidget(self.smoothing_beta_input, 4, 3)

        self.target_lat_label=QLabel("-"); self.target_lon_label=QLabel("-"); self.target_alt_label=QLabel("-"); self.target_heading_label=QLabel("-"); self.target_velocity_label=QLabel("-")
        for label in [self.target_lat_label,self.target_lon_label,self.target_alt_label,self.target_heading_label,self.target_velocity_label]:label.setObjectName("TrackerValue")
        
        left_layout.addWidget(QLabel("Hedef Enlem:"),5,0); left_layout.addWidget(self.target_lat_label,5,1,1,3)
        left_layout.addWidget(QLabel("Hedef Boylam:"),6,0); left_layout.addWidget(self.target_lon_label,6,1,1,3)
        left_layout.addWidget(QLabel("Hedef İrtifa:"),7,0); left_layout.addWidget(self.target_alt_label,7,1,1,3)
        left_layout.addWidget(QLabel("Hedef Kerteriz (°):"),8,0); left_layout.addWidget(self.target_heading_label,8,1,1,3)
        left_layout.addWidget(QLabel("Hedef Hız (m/s):"),9,0); left_layout.addWidget(self.target_velocity_label,9,1,1,3)
        
        self.start_tracker_button=QPushButton("Takibi Başlat"); self.start_tracker_button.setObjectName("GuiTrackerButtonStart"); self.stop_tracker_button=QPushButton("Takibi Bitir"); self.stop_tracker_button.setObjectName("GuiTrackerButtonStop"); self.reset_tracker_button=QPushButton("Görüntü Takip"); self.reset_tracker_button.setCheckable(True)
        self.start_tracker_button.clicked.connect(self.start_gui_tracker); self.stop_tracker_button.clicked.connect(self.stop_gui_tracker); self.stop_tracker_button.setEnabled(False)
        self.reset_tracker_button.setStyleSheet("QPushButton{background-color:#6A5ACD;color:white;font-weight:bold;}QPushButton:checked{background-color:#FF6347;}"); self.reset_tracker_button.clicked.connect(self.trigger_image_tracker_reset)
        button_layout = QHBoxLayout(); button_layout.addWidget(self.start_tracker_button); button_layout.addWidget(self.stop_tracker_button); button_layout.addWidget(self.reset_tracker_button)
        left_layout.addLayout(button_layout,10,0,1,4)
        
        right_group = QGroupBox("Anlık Takip Verisi"); right_layout = QVBoxLayout()
        self.tracker_status_label=QLabel("-");self.dx_label=QLabel("-");self.dy_label=QLabel("-");self.dz_label=QLabel("-");self.yaw_error_label=QLabel("-");self.pitch_error_label=QLabel("-");self.yaw_integrator_label=QLabel("-");self.pitch_integrator_label=QLabel("-")
        for label in [self.tracker_status_label,self.dx_label,self.dy_label,self.dz_label,self.yaw_error_label,self.pitch_error_label,self.yaw_integrator_label,self.pitch_integrator_label]:label.setObjectName("TrackerValue")
        form_layout=QGridLayout(); form_layout.addWidget(QLabel("Takip Durum:"),0,0); form_layout.addWidget(self.tracker_status_label,0,1); form_layout.addWidget(QLabel("dx (pixel):"),1,0); form_layout.addWidget(self.dx_label,1,1); form_layout.addWidget(QLabel("dy (pixel):"),2,0); form_layout.addWidget(self.dy_label,2,1); form_layout.addWidget(QLabel("dz (metre):"),3,0); form_layout.addWidget(self.dz_label,3,1)
        form_layout.addWidget(QLabel("Sapma Hata (px):"),4,0); form_layout.addWidget(self.yaw_error_label,4,1); form_layout.addWidget(QLabel("Tırmanış Hata (px):"),5,0); form_layout.addWidget(self.pitch_error_label,5,1)
        form_layout.addWidget(QLabel("Sapma İntegratör:"),6,0); form_layout.addWidget(self.yaw_integrator_label,6,1); form_layout.addWidget(QLabel("Tırmanış İntegratör:"),7,0); form_layout.addWidget(self.pitch_integrator_label,7,1)
        right_layout.addLayout(form_layout); right_layout.addStretch(); right_group.setLayout(right_layout)
        main_h_layout.addLayout(left_layout,3); main_h_layout.addWidget(right_group,1); group_box.setLayout(main_h_layout); return group_box
    
    # --- Tracker & PI Controller Methods ---
    def trigger_image_tracker_reset(self):
        self.image_tracker_reset_flag = 1 - self.image_tracker_reset_flag
        self.reset_tracker_button.setChecked(self.image_tracker_reset_flag == 1)
        
    def calculate_target_coordinates(self, gimbal_lat, gimbal_lon, gimbal_alt, heading, pitch, distance):
        if distance <= 0: return gimbal_lat, gimbal_lon, gimbal_alt
        EARTH_RADIUS=6378137.0; heading_rad,pitch_rad,gimbal_lat_rad=math.radians(heading),math.radians(pitch),math.radians(gimbal_lat)
        horizontal_distance,delta_up = distance*math.cos(pitch_rad),distance*math.sin(pitch_rad)
        delta_north,delta_east = horizontal_distance*math.cos(heading_rad),horizontal_distance*math.sin(heading_rad)
        delta_lat=math.degrees(delta_north/EARTH_RADIUS); delta_lon=math.degrees(delta_east/(EARTH_RADIUS*math.cos(gimbal_lat_rad)))
        return gimbal_lat + delta_lat, gimbal_lon + delta_lon, gimbal_alt + delta_up

    def _initialize_smoothing(self, lat, lon, alt):
        """Çift Üstel Düzeltme filtresini ilk geçerli veriyle başlatır."""
        self.smoothed_lat = lat
        self.smoothed_lon = lon
        self.smoothed_alt = alt
        # Trend (hız) başlangıçta sıfırdır.
        self.lat_trend = 0.0
        self.lon_trend = 0.0
        self.alt_trend = 0.0

    def _apply_smoothing(self, raw_lat, raw_lon, raw_alt, alpha, beta):
        """Verilen ham koordinatlara Holt's Method'u uygular ve sınıf değişkenlerini günceller."""
        
        # Enlem için hesaplama
        last_smoothed_lat = self.smoothed_lat
        self.smoothed_lat = alpha * raw_lat + (1 - alpha) * (last_smoothed_lat + self.lat_trend)
        self.lat_trend = beta * (self.smoothed_lat - last_smoothed_lat) + (1 - beta) * self.lat_trend
        
        # Boylam için hesaplama
        last_smoothed_lon = self.smoothed_lon
        self.smoothed_lon = alpha * raw_lon + (1 - alpha) * (last_smoothed_lon + self.lon_trend)
        self.lon_trend = beta * (self.smoothed_lon - last_smoothed_lon) + (1 - beta) * self.lon_trend
        
        # İrtifa için hesaplama
        last_smoothed_alt = self.smoothed_alt
        self.smoothed_alt = alpha * raw_alt + (1 - alpha) * (last_smoothed_alt + self.alt_trend)
        self.alt_trend = beta * (self.smoothed_alt - last_smoothed_alt) + (1 - beta) * self.alt_trend

    def toggle_tracker_button_blink(self):
        COLOR_STANDBY = "#A9A9A9" if self.is_dark_theme else "#D3D3D3"
        COLOR_ACTIVE_REQUEST = "#00FF00" if self.is_dark_theme else "#32CD32"
        color = COLOR_STANDBY if self.blink_on else COLOR_ACTIVE_REQUEST
        self.start_tracker_button.setStyleSheet(f"background-color: {color}; color: black; font-weight: bold;")
        self.blink_on = not self.blink_on

    def start_gui_tracker(self):
        self.gui_tracker_enabled = True; self.is_manual_control = False
        self.yaw_integral_error, self.pitch_integral_error = 0.0, 0.0
        self.last_control_time = time.time()
        self.start_tracker_button.setEnabled(False); self.stop_tracker_button.setEnabled(True)
        self._set_manual_movement_enabled(False)  
        if self.cam and self.cam.isConnected(): self.cam.setGimbalSpeed(0, 0)
    
    def stop_gui_tracker(self):
        self.gui_tracker_enabled = False
        self.yaw_error, self.pitch_error = 0.0, 0.0
        self.yaw_integral_error, self.pitch_integral_error = 0.0, 0.0
        self.start_tracker_button.setEnabled(True); self.stop_tracker_button.setEnabled(False)
        self._set_manual_movement_enabled(True)
        if self.cam and self.cam.isConnected(): self.cam.setGimbalSpeed(0, 0)

    def _run_pi_controller(self, is_tracking):
        if not is_tracking:
            if self.cam and self.cam.isConnected(): self.cam.setGimbalSpeed(0, 0)
            return
        current_time=time.time(); dt=current_time - self.last_control_time
        if dt <= 0.001: return
        self.last_control_time = current_time
        try:
            kp_yaw,ki_yaw,kp_pitch,ki_pitch = float(self.kp_yaw_input.text()),float(self.ki_yaw_input.text()),float(self.kp_pitch_input.text()),float(self.ki_pitch_input.text())
            speed_limit = max(1, min(100, int(self.pi_speed_limit_input.text())))
        except ValueError: return
        self.yaw_error,self.pitch_error = self.tracker_dx,self.tracker_dy
        self.yaw_integral_error = max(-50,min(50,self.yaw_integral_error + self.yaw_error * dt))
        yaw_speed = (kp_yaw * self.yaw_error) + (ki_yaw * self.yaw_integral_error)
        self.pitch_integral_error = max(-50,min(50,self.pitch_integral_error + self.pitch_error * dt))
        pitch_speed = (kp_pitch * self.pitch_error) + (ki_pitch * self.pitch_integral_error)
        final_yaw_speed=int(max(-speed_limit,min(speed_limit,yaw_speed))); final_pitch_speed=int(max(-speed_limit,min(speed_limit,pitch_speed)))
        self.cam.setGimbalSpeed(final_yaw_speed, final_pitch_speed)

    def reset_status_labels(self):
        self.attitude_widget.set_attitude(0,0,0);self.yaw_value.setText("-");self.pitch_value.setText("-");self.roll_value.setText("-");self.zoom_value.setText("-");self.focal_length_value.setText("-");self.record_value.setText("-");self.mode_value.setText("-");self.mount_value.setText("-");self.hdr_value.setText("-");self.model_value.setText("-");self.target_lat_label.setText("-");self.target_lon_label.setText("-");self.target_alt_label.setText("-");self.target_heading_label.setText("-");self.target_velocity_label.setText("-")
    
    # --- UI Creation Methods ---
    def create_settings_group(self):
        group_box=QGroupBox("Gimbal Ayarları");layout=QGridLayout(); layout.addWidget(QLabel("Gimbal Modu:"),0,0)
        self.mode_combo=QComboBox(); self.mode_combo.addItems(self.motion_modes.keys()); self.mode_combo.currentIndexChanged.connect(self.change_motion_mode); layout.addWidget(self.mode_combo,0,1,1,3)
        self.gimbal_lat_input=QLineEdit(self.gui_config.get("gimbal_lat")); layout.addWidget(QLabel("Gimbal Enlem:"),1,0); layout.addWidget(self.gimbal_lat_input,1,1)
        self.gimbal_lon_input=QLineEdit(self.gui_config.get("gimbal_lon")); layout.addWidget(QLabel("Gimbal Boylam:"),1,2); layout.addWidget(self.gimbal_lon_input,1,3)
        self.gimbal_alt_input=QLineEdit(self.gui_config.get("gimbal_alt")); layout.addWidget(QLabel("Gimbal İrtifa (m):"),2,0); layout.addWidget(self.gimbal_alt_input,2,1)
        self.true_north_offset_input=QLineEdit(self.gui_config.get("north_offset")); layout.addWidget(QLabel("Gerçek Kuzey Ofseti (°):"),2,2); layout.addWidget(self.true_north_offset_input,2,3)
        layout.addWidget(QLabel("Ev Enlem:"), 3, 0); self.home_lat_input = QLineEdit(self.gui_config.get("home_lat")); layout.addWidget(self.home_lat_input, 3, 1)
        layout.addWidget(QLabel("Ev Boylam:"), 3, 2); self.home_lon_input = QLineEdit(self.gui_config.get("home_lon")); layout.addWidget(self.home_lon_input, 3, 3)
        layout.addWidget(QLabel("Ev İrtifa (m):"), 4, 0); self.home_alt_input = QLineEdit(self.gui_config.get("home_alt")); layout.addWidget(self.home_alt_input, 4, 1) 
        joystick_btn=QPushButton("Joystick Ayarları..."); joystick_btn.clicked.connect(self.open_joystick_config); layout.addWidget(joystick_btn,5,0,1,4)
        if not PYGAME_AVAILABLE: joystick_btn.setEnabled(False)
        group_box.setLayout(layout); return group_box
    
    def create_connection_group(self):
        group_box=QGroupBox("Bağlantı");layout=QHBoxLayout();self.ip_input=QLineEdit(self.gui_config.get("connection_ip"));self.port_input=QLineEdit(self.gui_config.get("connection_port"));self.connect_button=QPushButton("Bağlan");self.connect_button.clicked.connect(self.toggle_connection)
        self.status_label=QLabel("Bağlı Değil");self.status_label.setStyleSheet("color:#FF5555;font-size:14px;font-weight:bold;");layout.addWidget(QLabel("IP:"));layout.addWidget(self.ip_input);layout.addWidget(QLabel("Port:"));layout.addWidget(self.port_input);layout.addWidget(self.connect_button)
        theme_button=QPushButton("Tema Değiştir");theme_button.clicked.connect(self._toggle_theme);layout.addWidget(theme_button)
        layout.addWidget(self.status_label);group_box.setLayout(layout);return group_box
    
    # --- Action & Event Handlers ---
    def start_movement(self,direction):
        if not(self.cam and self.cam.isConnected()):return
        if self.gui_tracker_enabled: self.stop_gui_tracker()
        self.is_manual_control=True;yaw,pitch=(0,0)
        if direction=='up':pitch=self.gimbal_speed
        elif direction=='down':pitch=-self.gimbal_speed
        elif direction=='left':yaw=-self.gimbal_speed
        elif direction=='right':yaw=self.gimbal_speed
        self.cam.setGimbalSpeed(yaw,pitch)
    
    def stop_movement(self):
        self.is_manual_control=False
        if self.cam and self.cam.isConnected():self.cam.setGimbalSpeed(0,0)
    
    # --- UI Creation Methods ---
    def create_movement_group(self):
        group_box=QGroupBox("Yön ve Hız Kontrolü");main_layout=QVBoxLayout();grid_layout=QGridLayout()
        top_speed_layout=QHBoxLayout();top_speed_layout.addWidget(QLabel("Minimum Hız (%):"));self.min_speed_input=QLineEdit(self.gui_config.get("min_speed"));self.min_speed_input.setFixedWidth(50);top_speed_layout.addWidget(self.min_speed_input)
        top_speed_layout.addStretch();self.speed_label=QLabel(f"Hız: {self.gimbal_speed}%");top_speed_layout.addWidget(self.speed_label);top_speed_layout.addStretch()
        self.max_speed_input=QLineEdit(self.gui_config.get("max_speed"));self.max_speed_input.setFixedWidth(50);top_speed_layout.addWidget(QLabel("Maksimum Hız (%):"));top_speed_layout.addWidget(self.max_speed_input)
        self.speed_slider=QSlider(Qt.Horizontal);self.speed_slider.setRange(1,100);self.speed_slider.setValue(self.gimbal_speed);self.speed_slider.valueChanged.connect(self.speed_changed);
        main_layout.addLayout(top_speed_layout);main_layout.addWidget(self.speed_slider)
        self.up_btn,self.down_btn,self.left_btn,self.right_btn,self.center_btn=QPushButton("Yukarı"),QPushButton("Aşağı"),QPushButton("Sol"),QPushButton("Sağ"),QPushButton("Merkezle")
        self.up_btn.pressed.connect(lambda:self.start_movement('up'));self.down_btn.pressed.connect(lambda:self.start_movement('down'));self.left_btn.pressed.connect(lambda:self.start_movement('left'));self.right_btn.pressed.connect(lambda:self.start_movement('right'))
        self.up_btn.released.connect(self.stop_movement);self.down_btn.released.connect(self.stop_movement);self.left_btn.released.connect(self.stop_movement);self.right_btn.released.connect(self.stop_movement)
        self.center_btn.clicked.connect(self.center_gimbal);grid_layout.addWidget(self.up_btn,0,1);grid_layout.addWidget(self.left_btn,1,0);grid_layout.addWidget(self.center_btn,1,1);grid_layout.addWidget(self.right_btn,1,2);grid_layout.addWidget(self.down_btn,2,1)
        main_layout.addLayout(grid_layout); group_box.setLayout(main_layout); return group_box
    
    def create_camera_actions_group(self):
        group_box=QGroupBox("Kamera Fonksiyonları");layout=QHBoxLayout();photo_btn,record_btn=QPushButton("Fotoğraf Çek"),QPushButton("Video Kaydet");zoom_in_btn,zoom_out_btn=QPushButton("Yakınlaştır (+)"),QPushButton("Uzaklaştır (-)")
        photo_btn.clicked.connect(self.take_photo);record_btn.clicked.connect(self.toggle_record);zoom_in_btn.pressed.connect(lambda:self.start_zoom(1));zoom_in_btn.released.connect(self.stop_zoom);zoom_out_btn.pressed.connect(lambda:self.start_zoom(-1));zoom_out_btn.released.connect(self.stop_zoom)
        layout.addWidget(photo_btn);layout.addWidget(record_btn);layout.addWidget(zoom_in_btn);layout.addWidget(zoom_out_btn);group_box.setLayout(layout);return group_box
    
    def create_focus_group(self):
        group_box=QGroupBox("Odaklama Kontrolü");layout=QHBoxLayout();self.focus_mode_combo=QComboBox();self.focus_mode_combo.addItems(["Otomatik Odaklama","Manuel Odaklama"]);self.focus_mode_combo.currentIndexChanged.connect(self.on_focus_mode_changed);layout.addWidget(QLabel("Mod:"));layout.addWidget(self.focus_mode_combo)
        self.refocus_button=QPushButton("Tekrar Odakla");self.refocus_button.clicked.connect(self.trigger_autofocus);layout.addWidget(self.refocus_button);self.focus_near_button=QPushButton("Daha Yakın (+)");self.focus_near_button.pressed.connect(lambda:self.start_manual_focus(1));self.focus_near_button.released.connect(self.stop_manual_focus);layout.addWidget(self.focus_near_button)
        self.focus_far_button=QPushButton("Daha Uzak (-)");self.focus_far_button.pressed.connect(lambda:self.start_manual_focus(-1));self.focus_far_button.released.connect(self.stop_manual_focus);layout.addWidget(self.focus_far_button);group_box.setLayout(layout);group_box.setEnabled(False);self.on_focus_mode_changed(0);return group_box
    
    def create_tracker_group(self):
        group_box=QGroupBox("Görüntü İşleme Servisi");layout=QGridLayout();self.tracker_ip_input=QLineEdit(self.gui_config.get("tracker_listen_ip"));self.tracker_port_input=QLineEdit(self.gui_config.get("tracker_listen_port"));layout.addWidget(QLabel("Dinleme IP Adresi:"),0,0);layout.addWidget(self.tracker_ip_input,0,1);layout.addWidget(QLabel("Dinleme Portu:"),1,0);layout.addWidget(self.tracker_port_input,1,1)
        self.tracker_button=QPushButton("Servisi Başlat");self.tracker_button.setCheckable(True);self.tracker_button.setObjectName("TrackerButton");self.tracker_button.clicked.connect(self.toggle_tracker_service);layout.addWidget(self.tracker_button,2,0,1,2);group_box.setLayout(layout);group_box.setEnabled(False);return group_box
    
    def create_interface_service_group(self):
        group_box=QGroupBox("Arayüz Servis");layout=QGridLayout();self.interface_ip_input=QLineEdit(self.gui_config.get("interface_target_ip"));self.interface_port_input=QLineEdit(self.gui_config.get("interface_target_port"))
        layout.addWidget(QLabel("Hedef IP:"),0,0);layout.addWidget(self.interface_ip_input,0,1);layout.addWidget(QLabel("Hedef Port:"),1,0);layout.addWidget(self.interface_port_input,1,1)
        self.interface_button=QPushButton("Servisi Başlat");self.interface_button.setCheckable(True);self.interface_button.setObjectName("InterfaceButton");self.interface_button.clicked.connect(self.toggle_interface_service)
        layout.addWidget(self.interface_button,2,0,1,2);group_box.setLayout(layout);group_box.setEnabled(False);return group_box
    
    def create_logging_group(self):
        group_box = QGroupBox("Arayüz Veri Kaydı")
        layout = QHBoxLayout()
        self.log_button = QPushButton("Kaydı Başlat")
        self.log_button.setCheckable(True)
        self.log_button.setObjectName("LogButton")
        self.log_button.clicked.connect(self.toggle_logging)
        layout.addWidget(self.log_button)
        group_box.setLayout(layout)
        group_box.setEnabled(False)
        return group_box

    # --- Connection & State Methods ---
    def connect_worker(self,ip,port):
        self.cam=SIYISDK(server_ip=ip,port=port,debug=False)
        if self.cam.connect(): QTimer.singleShot(0,self.connection_successful)
        else: QTimer.singleShot(0,self.connection_failed)
    
    def connection_failed(self):
        self.status_label.setText("Bağlantı Hatası");self.status_label.setStyleSheet("color:#FF5555;");self.connect_button.setText("Bağlan");self.toggle_controls(False)
    
    def toggle_connection(self):
        if self.cam and self.cam.isConnected():
            self.main_update_timer.stop();self.cam.disconnect();self.cam=None;self.status_label.setText("Bağlı Değil");self.status_label.setStyleSheet("color:#FF5555;");self.connect_button.setText("Bağlan");self.toggle_controls(False);self.reset_status_labels()
        else:
            try:
                ip,port=self.ip_input.text(),int(self.port_input.text());self.status_label.setText("Bağlanılıyor...");self.status_label.setStyleSheet("color:#F0E68C;");threading.Thread(target=self.connect_worker,args=(ip,port),daemon=True).start()
            except (ValueError, TypeError): self.status_label.setText("Geçersiz IP/Port"); self.status_label.setStyleSheet("color:#FF5555;")
    
    def connection_successful(self):
        self.status_label.setText("Bağlandı");self.status_label.setStyleSheet("color:#55FF55;");self.connect_button.setText("Bağlantıyı Kes");self.toggle_controls(True);self.main_update_timer.start(20)
        model_name=self.cam.getCameraTypeString()or"Bilinmiyor";self.model_value.setText(f"{model_name}")
    
    def _set_manual_movement_enabled(self,enabled):
        self.up_btn.setEnabled(enabled);self.down_btn.setEnabled(enabled);self.left_btn.setEnabled(enabled);self.right_btn.setEnabled(enabled);self.center_btn.setEnabled(enabled);self.speed_slider.setEnabled(enabled);self.min_speed_input.setEnabled(enabled);self.max_speed_input.setEnabled(enabled)
    
    def toggle_controls(self,enabled):
        for child in self.findChildren(QGroupBox):
            if child.title() != "Bağlantı": child.setEnabled(enabled)
        if enabled: self._set_manual_movement_enabled(not self.gui_tracker_enabled)
        else: self._set_manual_movement_enabled(False)

    # --- Action & Event Handlers ---
    def speed_changed(self,value):self.gimbal_speed=value;self.speed_label.setText(f"Hız: {self.gimbal_speed}%")
    def center_gimbal(self):
        if self.gui_tracker_enabled: self.stop_gui_tracker()
        if self.cam and self.cam.isConnected():self.cam.requestCenterGimbal()
    def take_photo(self):
        if self.cam and self.cam.isConnected():self.cam.takePhoto()
    def toggle_record(self):
        if self.cam and self.cam.isConnected():self.cam.toggleRecording()
    def start_zoom(self,direction):
        if self.cam and self.cam.isConnected():self.cam.requestManualZoom(direction)
    def stop_zoom(self):
        if self.cam and self.cam.isConnected():self.cam.requestManualZoom(0)
    def change_motion_mode(self):
        if not(self.cam and self.cam.isConnected()):return
        sdk_mode_code=self.motion_modes.get(self.mode_combo.currentText());
        if sdk_mode_code:self.cam.setMotionMode(sdk_mode_code)
    def on_focus_mode_changed(self,index):
        is_manual=(self.focus_mode_combo.currentText()=="Manuel Odaklama");self.refocus_button.setEnabled(not is_manual);self.focus_near_button.setEnabled(is_manual);self.focus_far_button.setEnabled(is_manual)
    def trigger_autofocus(self):
        if self.cam and self.cam.isConnected():self.cam.requestAutoFocus()
    def start_manual_focus(self,direction):
        if self.cam and self.cam.isConnected():self.cam.requestManualFocus(direction)
    def stop_manual_focus(self):
        if self.cam and self.cam.isConnected():self.cam.requestManualFocus(0)
    
    # --- Service & Communication Methods ---
    def toggle_tracker_service(self, checked):
        if checked:
            try:
                listen_ip,port=self.tracker_ip_input.text(),int(self.tracker_port_input.text())
                self.tracker_socket=socket.socket(socket.AF_INET, socket.SOCK_DGRAM); self.tracker_socket.bind((listen_ip, port))
                self.tracker_thread_stop_flag.clear(); self.tracker_handler_thread=threading.Thread(target=self.receive_tracker_data_loop,daemon=True); self.tracker_handler_thread.start()
                self.tracker_button.setText("Servisi Durdur"); print(f"UDP Tracker servisi {listen_ip}:{port} üzerinde başlatıldı.")
            except Exception as e:
                print(f"UDP Tracker servisi başlatılamadı: {e}"); self.tracker_button.setChecked(False)
                if self.tracker_socket: self.tracker_socket.close(); self.tracker_socket=None
        else:
            self.tracker_thread_stop_flag.set()
            if self.tracker_socket: self.tracker_socket.close() 
            if self.tracker_handler_thread and self.tracker_handler_thread.is_alive(): self.tracker_handler_thread.join(timeout=0.2)
            self.tracker_socket, self.tracker_handler_thread = None, None
            self.tracker_button.setText("Servisi Başlat"); self.reset_tracker_state(); print("UDP Tracker servisi durduruldu.")

    def reset_target_info(self):
        """GUI üzerindeki hedef etiketlerini temizler ve filtre durumlarını sıfırlar."""
        self.target_lat, self.target_lon, self.target_alt = 0.0, 0.0, 0.0
        self.target_lat_label.setText("-"); self.target_lon_label.setText("-")
        self.target_alt_label.setText("-"); self.target_heading_label.setText("-")
        self.target_velocity_label.setText("-"); self.yaw_error_label.setText("-")
        self.pitch_error_label.setText("-"); self.yaw_integrator_label.setText("-")
        self.pitch_integrator_label.setText("-")
        
        # Filtre durumlarını sıfırla
        self.filter_initialized = False
        self.smoothed_lat, self.lat_trend = 0.0, 0.0
        self.smoothed_lon, self.lon_trend = 0.0, 0.0
        self.smoothed_alt, self.alt_trend = 0.0, 0.0

    def reset_tracker_state(self):
        self.tracker_status=0;self.tracker_dx=0;self.tracker_dy=0;self.tracker_dz=0.0
        self.tracker_client_addr = None; self.last_tracker_data_time = 0 
        if self.gui_tracker_enabled: self.stop_gui_tracker()
        with self.tracker_data_queue.mutex:self.tracker_data_queue.queue.clear()

        self.reset_target_info() # Filtreleri ve GUI'yi temizler

        self.filtered_heading, self.filtered_pitch = 0.0, 0.0
        self.prev_target_lat, self.prev_target_lon, self.prev_target_alt = 0.0, 0.0, 0.0
        self.last_target_update_time = time.time()
        self.current_target_heading, self.current_target_velocity = 0.0, 0.0
        self.velocity_buffer.clear(); self.heading_buffer.clear()
        QTimer.singleShot(0, self.update_tracker_gui_labels)

    def update_tracker_gui_labels(self):
        self.tracker_status_label.setText(f"{self.tracker_status}"); self.dx_label.setText(f"{self.tracker_dx}"); self.dy_label.setText(f"{self.tracker_dy}"); self.dz_label.setText(f"{self.tracker_dz:.2f}")

    def toggle_interface_service(self,checked):
        if checked:
            try:
                self.interface_socket=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);self.interface_button.setText("Servisi Durdur")
            except Exception as e:print(f"Arayüz servisi başlatılamadı: {e}");self.interface_button.setChecked(False)
        else:
            if self.interface_socket:self.interface_socket.close()
            self.interface_socket=None;self.interface_button.setText("Servisi Başlat")
    
    # --- Styling and Theming ---
    def _toggle_theme(self):
        self.is_dark_theme = not self.is_dark_theme
        self._apply_stylesheet(self.light_style if not self.is_dark_theme else self.dark_style)
    
    def _apply_stylesheet(self, style):
        self.setStyleSheet(style)
        for win in QApplication.topLevelWidgets():
            if isinstance(win, QDialog): win.setStyleSheet(style)
    
    def _define_stylesheets(self):
        self.dark_style="""QWidget,QDialog{background-color:#2E2E2E;color:#F0F0F0;font-family:Arial;}QGroupBox{font:bold 14px;border:1px solid #555;border-radius:5px;margin-top:1ex;padding-top:15px;}QGroupBox::title{subcontrol-origin:margin;subcontrol-position:top center;padding:0 5px;}QPushButton{background-color:#555;border:1px solid #777;padding:8px;border-radius:4px;font-size:12px;}QPushButton:hover{background-color:#6A6A6A;}QPushButton:pressed{background-color:#4C4C4C;}QPushButton#TrackerButton,QPushButton#InterfaceButton,QPushButton#LogButton{background-color:#006400;}QPushButton#TrackerButton:checked,QPushButton#InterfaceButton:checked,QPushButton#LogButton:checked{background-color:#8B0000;}QLineEdit,QComboBox{background-color:#444;border:1px solid #666;padding:5px;border-radius:4px;color:#F0F0F0;}QLabel#StatusValue,QLabel#TrackerValue{font-size:13px;font-weight:bold;color:#00AEEF;}QLabel#StatusHeader,QLabel#TrackerHeader{font-size:13px;color:#CCCCCC;}QPushButton#GuiTrackerButtonStart{background-color:#006400; color:white; font-weight:bold;}QPushButton#GuiTrackerButtonStop{background-color:#8B0000; color:white; font-weight:bold;}"""
        self.light_style="""QWidget,QDialog{background-color:#f0f0f0;color:#333;font-family:Arial;}QGroupBox{font:bold 14px;border:1px solid #ccc;border-radius:5px;margin-top:1ex;padding-top:15px;}QPushButton{background-color:#e0e0e0;border:1px solid #aaa;padding:8px;border-radius:4px;font-size:12px;}QPushButton:hover{background-color:#e8e8e8;}QPushButton:pressed{background-color:#d0d0d0;}QPushButton#TrackerButton,QPushButton#InterfaceButton,QPushButton#LogButton{background-color:#2E8B57;}QPushButton#TrackerButton:checked,QPushButton#InterfaceButton:checked,QPushButton#LogButton:checked{background-color:#A52A2A;}QLineEdit,QComboBox{background-color:#fff;border:1px solid #aaa;padding:5px;border-radius:4px;color:#333;}QLabel#StatusValue,QLabel#TrackerValue{font-size:13px;font-weight:bold;color:#007ACC;}QLabel#StatusHeader,QLabel#TrackerHeader{font-size:13px;color:#555;}QPushButton#GuiTrackerButtonStart{background-color:#2E8B57; color:white; font-weight:bold;}QPushButton#GuiTrackerButtonStop{background-color:#A52A2A; color:white; font-weight:bold;}"""
    
    # --- Veri Kaydı (Loglama) Metodları ---
    def toggle_logging(self, checked):
        if checked:
            try:
                timestamp=datetime.now().strftime("%Y%m%d_%H%M%S");filename=f"gimbal_log_{timestamp}.csv"
                self.log_file=open(filename,'w',newline='',encoding='utf-8');self.csv_writer=csv.writer(self.log_file)
                self._write_log_header();self.is_logging=True;self.log_button.setText("Kaydı Durdur");print(f"Veri kaydı başlatıldı: {filename}")
            except Exception as e: print(f"Veri kaydı başlatılamadı: {e}"); self.log_button.setChecked(False)
        else:
            if self.log_file: self.log_file.close()
            self.log_file,self.csv_writer,self.is_logging=None,None,False;self.log_button.setText("Kaydı Başlat");print("Veri kaydı durduruldu.")

    def _write_log_header(self):
        if not self.csv_writer: return
        headers = [
            "time", "raw_yaw", "raw_pitch", "raw_roll", "filtered_heading", "filtered_pitch", "zoom_level", 
            "focal_length", "record_state", "motion_mode", "mount_dir", "hdr_state", "tracker_status", 
            "tracker_dx", "tracker_dy", "tracker_dz", "is_gui_tracking_enabled", "target_latitude", 
            "target_longitude", "target_altitude", "target_velocity", "target_heading", "yaw_pi_error", 
            "pitch_pi_error", "yaw_pi_integrator", "pitch_pi_integrator", "kp_yaw", "ki_yaw", "kp_pitch", 
            "ki_pitch", "pixel_filter_alpha", "pi_speed_limit", "gimbal_filter_alpha", "max_jump_distance",
            "smoothing_alpha", "smoothing_beta", "gimbal_lat_input", "gimbal_lon_input", "gimbal_alt_input",
            "north_offset_input", "home_lat_input", "home_lon_input", "home_alt_input",
            "min_speed_input", "max_speed_input"
        ]
        self.csv_writer.writerow(headers)

    def _write_log_entry(self, log_data):
        if not self.csv_writer: return
        self.csv_writer.writerow([datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]] + list(log_data.values()))

    # --- Cleanup ---
    def closeEvent(self,event):
        self.save_gui_config()
        if self.is_logging: self.toggle_logging(False)
        self.main_update_timer.stop()
        if self.tracker_button.isChecked():self.toggle_tracker_service(False)
        if self.interface_button.isChecked():self.toggle_interface_service(False)
        if PYGAME_AVAILABLE:
            if self.joystick_handler:self.joystick_handler.stop()
            if self.joystick_thread and self.joystick_thread.is_alive():self.joystick_thread.join()
            pygame.quit()
        if self.cam:self.cam.disconnect()
        event.accept()

if __name__=='__main__':
    if PYGAME_AVAILABLE:
        pygame.init()
    app=QApplication(sys.argv)
    ex=GimbalGUI()
    ex.showMaximized() 
    sys.exit(app.exec_())