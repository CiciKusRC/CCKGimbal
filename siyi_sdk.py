"""
Python implementation of SIYI SDK - Updated for ZR30
"""
import socket
from siyi_message import *
from time import sleep, time
import logging
from utils import toInt
import threading
import cameras

class SIYISDK:
    def __init__(self, server_ip="192.168.144.25", port=37260, debug=False):
        self._debug = debug
        if self._debug: d_level = logging.DEBUG
        else: d_level = logging.INFO
        LOG_FORMAT = ' [%(levelname)s] %(asctime)s [SIYISDK::%(funcName)s] :\t%(message)s'
        logging.basicConfig(format=LOG_FORMAT, level=d_level)
        self._logger = logging.getLogger(self.__class__.__name__)
        self._out_msg = SIYIMESSAGE(debug=self._debug)
        self._in_msg = SIYIMESSAGE(debug=self._debug)
        
        self._gimbal_ip = server_ip
        self._server_ip = "0.0.0.0"   

        self._port = port
        self._BUFF_SIZE = 1024
        self._socket = None
        self._rcv_wait_t = 5
        
        self.resetVars()
        self._stop = False
        
        self._info_update_period = 1.0 / 5
        self._zoom_update_period = 1.0 / 20
        
        self._last_message_time = 0
        self.CONNECTION_TIMEOUT = 3.0
        
        self._recv_thread = None; self._conn_thread = None
        self._g_info_thread = None; self._zoom_thread = None

    def _initialize_socket(self):
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socket.settimeout(self._rcv_wait_t)

    def resetVars(self):
        self._connected = False
        self._fw_msg = FirmwareMsg(); self._hw_msg = HardwareIDMsg()
        self._autoFocus_msg = AutoFocusMsg(); self._gimbal_info_msg = GimbalInfoMsg()
        self._att_msg = AttitdueMsg(); self._current_zoom_level_msg = CurrentZoomValueMsg()
        self._max_zoom_value_msg = MaxZoomValueMsg(); self._format_sd_card_msg = FormatSDCardMsg()
        self._center_msg = CenterMsg(); self._gimbalSpeed_msg = GimbalSpeedMsg()
        return True

    def connect(self, maxWaitTime=5.0):
        self._stop = False
        self._initialize_socket()
        
        try:
            self._socket.bind((self._server_ip, self._port))
        except Exception as e:
            self._logger.error(f"Failed to bind socket to {self._server_ip}:{self._port}. Error: {e}")
            return False
            
        self._recv_thread = threading.Thread(target=self.recvLoop, daemon=True)
        self._conn_thread = threading.Thread(target=self.connectionLoop, daemon=True)
        self._g_info_thread = threading.Thread(target=self.gimbalInfoLoop, daemon=True)
        self._zoom_thread = threading.Thread(target=self.zoomLoop, daemon=True)

        try:
            self._recv_thread.start()
            self._conn_thread.start()
        except RuntimeError: pass
        
        self._logger.info(f"Connecting to Gimbal at {self._gimbal_ip}...")
        
        t0 = time()
        while time() - t0 < maxWaitTime:
            self.requestHardwareID()

            if self._hw_msg.cam_type_str and self._hw_msg.cam_type_str != "Unknown":
                self._connected = True 
                self._logger.info(f"Connection successful! Camera model: {self._hw_msg.cam_type_str}")
                
                if not self.requestDataStream(100):
                    self._logger.warning("Failed to set attitude data stream rate.")
                
                if not self._g_info_thread.is_alive(): self._g_info_thread.start()
                if not self._zoom_thread.is_alive(): self._zoom_thread.start()
                
                return True 
                
            sleep(0.5)

        self._logger.error("Failed to connect. No valid Hardware ID received from the camera.")
        self.disconnect()
        return False

    def disconnect(self):
        self._logger.info("Disconnecting..."); self._stop = True; self._connected = False
        if self._socket: self._socket.close()
        
    def checkConnection(self):
        if not self._connected: return
        if (time() - self._last_message_time) > self.CONNECTION_TIMEOUT:
            self._logger.warning("Connection lost (timeout).")
            self._connected = False
    
    def connectionLoop(self):
        while not self._stop:
            self.checkConnection()
            sleep(1)

    def gimbalInfoLoop(self):
        while not self._stop:
            if self._connected: self.requestGimbalInfo()
            sleep(self._info_update_period)

    def zoomLoop(self):
        while not self._stop:
            if self._connected: self.requestCurrentZoomLevel()
            sleep(self._zoom_update_period)
            
    def requestDataStream(self, freq_hz):
        data_type = RequestDataStreamMsg.ATTITUDE_DATA
        freq_code = RequestDataStreamMsg.FREQ.get(freq_hz)
        if freq_code is None:
            self._logger.error(f"Unsupported frequency: {freq_hz} Hz"); return False
        return self.sendMsg(self._out_msg.setDataStreamMsg(data_type, freq_code))
            
    def isConnected(self): return self._connected

    def sendMsg(self, msg):
        if msg and self._socket:
            b = bytes.fromhex(msg)
            try:
                self._socket.sendto(b, (self._gimbal_ip, self._port))
                return True
            except Exception as e:
                self._logger.error(f"Error sending message: {e}")
        return False

    def recvLoop(self):
        self._logger.debug("Started data receiving thread")
        while not self._stop: self.bufferCallback()
        self._logger.debug("Exiting data receiving thread")

    def bufferCallback(self):
        try:
            buff, addr = self._socket.recvfrom(self._BUFF_SIZE)
        except Exception: return
        
        self._last_message_time = time()

        buff_str = buff.hex(); HEADER='5566'
        while len(buff_str) >= 20:
            if not buff_str.startswith(HEADER): buff_str = buff_str[2:]; continue
            val = self._in_msg.decodeMsg(buff_str)
            if val is None: buff_str = buff_str[2:]; continue
            data, data_len, cmd_id, seq = val; packet_len = 10 + data_len; buff_str = buff_str[packet_len*2:]
            
            parser_map = {
                COMMAND.ACQUIRE_FW_VER: self.parseFirmwareMsg, COMMAND.ACQUIRE_HW_ID: self.parseHardwareIDMsg,
                COMMAND.ACQUIRE_GIMBAL_INFO: self.parseGimbalInfoMsg, COMMAND.ACQUIRE_GIMBAL_ATT: self.parseAttitudeMsg,
                COMMAND.AUTO_FOCUS: self.parseAutoFocusMsg, COMMAND.CENTER: self.parseGimbalCenterMsg,
                COMMAND.CURRENT_ZOOM_VALUE: self.parseCurrentZoomLevelMsg, COMMAND.REQUEST_MAX_ZOOM: self.parseMaxZoomValueMsg,
                COMMAND.FORMAT_SD_CARD: self.parseFormatSDCardMsg, COMMAND.GIMBAL_SPEED: self.parseGimbalSpeedMsg,
            }
            
            parser = parser_map.get(cmd_id)
            if parser: parser(data, seq)
            else: self._logger.debug(f"CMD ID '{cmd_id}' parser not implemented.")

    def requestFirmwareVersion(self): return self.sendMsg(self._out_msg.requestFirmwareVersionMsg())
    def requestHardwareID(self): return self.sendMsg(self._out_msg.requestHardwareIDMsg())
    def requestGimbalInfo(self): return self.sendMsg(self._out_msg.requestGimbalInfoMsg())
    def requestAutoFocus(self, x=None, y=None): return self.sendMsg(self._out_msg.autoFocusMsg(x,y))
    def requestManualZoom(self, direction): return self.sendMsg(self._out_msg.manualZoomMsg(direction))
    def requestManualFocus(self, direction): return self.sendMsg(self._out_msg.manualFocusMsg(direction))
    def requestCenterGimbal(self): return self.sendMsg(self._out_msg.centerGimbalMsg())
    def setGimbalSpeed(self, yaw_speed, pitch_speed): return self.sendMsg(self._out_msg.setGimbalSpeedMsg(yaw_speed, pitch_speed))
    def requestCurrentZoomLevel(self): return self.sendMsg(self._out_msg.requestCurrentZoomMsg())
    def takePhoto(self): return self.sendMsg(self._out_msg.takePhotoMsg())
    def toggleRecording(self): return self.sendMsg(self._out_msg.recordMsg())
    def setMotionMode(self, mode): return self.sendMsg(self._out_msg.setMotionModeMsg(mode))

    def parseFirmwareMsg(self, msg, seq): self._fw_msg.seq = seq
    
    def parseHardwareIDMsg(self, msg, seq):
        self._hw_msg.seq = seq
        self._hw_msg.id = msg

        if len(msg) >= 4:

            model_code_hex = msg[0:4]
            try:
                model_code_bytes = bytes.fromhex(model_code_hex)
                model_code_str = model_code_bytes.decode('ascii').upper()
            except (ValueError, UnicodeDecodeError):
                self._logger.error(f"Could not decode model code from hex: {model_code_hex}")
                self._hw_msg.cam_type_str = "Unknown"
                return

            self._hw_msg.cam_type_str = HardwareIDMsg.CAM_DICT.get(model_code_str, "Unknown")
            
            if self._hw_msg.cam_type_str == "Unknown":
                self._logger.warning(f"Unknown camera model string in dictionary: '{model_code_str}'")
        else:
            self._hw_msg.cam_type_str = "Unknown"
            self._logger.error(f"Malformed Hardware ID packet (too short): {msg}")

    def parseGimbalInfoMsg(self, msg, seq):
        try:
            self._gimbal_info_msg.record_state = int(msg[6:8], 16); self._gimbal_info_msg.motion_mode = int(msg[8:10], 16)
            self._gimbal_info_msg.mount_dir = int(msg[10:12], 16); self._gimbal_info_msg.hdr_sta = int(msg[2:4], 16)
        except (IndexError, ValueError): pass 
    def parseAttitudeMsg(self, msg, seq):
        try:
            self._att_msg.yaw = toInt(msg[2:4] + msg[0:2]) / 10.0
            self._att_msg.pitch = toInt(msg[6:8] + msg[4:6]) / 10.0
            self._att_msg.roll = toInt(msg[10:12] + msg[8:10]) / 10.0
        except (IndexError, ValueError): pass
    def parseGimbalSpeedMsg(self, msg, seq): 
        try: self._gimbalSpeed_msg.success = bool(int(msg, 16))
        except (ValueError): pass
    def parseAutoFocusMsg(self, msg, seq): 
        try: self._autoFocus_msg.success = bool(int(msg, 16))
        except (ValueError): pass
    def parseGimbalCenterMsg(self, msg, seq): 
        try: self._center_msg.success = bool(int(msg, 16))
        except (ValueError): pass
    def parseCurrentZoomLevelMsg(self, msg, seq):
        try:
            int_part, float_part = int(msg[0:2], 16), int(msg[2:4], 16)
            self._current_zoom_level_msg.level = int_part + (float_part / 10.0)
        except (IndexError, ValueError): pass
    def parseMaxZoomValueMsg(self, msg, seq):
        try:
            int_part, float_part = int(msg[0:2], 16), int(msg[2:4], 16)
            self._max_zoom_value_msg.level = int_part + (float_part / 10.0)
        except (IndexError, ValueError): pass
    def parseFormatSDCardMsg(self, msg, seq):
        try: self._format_sd_card_msg.success = bool(int(msg[0:2], 16))
        except (ValueError): pass
    
    def getAttitude(self): return (self._att_msg.yaw, self._att_msg.pitch, self._att_msg.roll)
    def getGimbalInfo(self): return self._gimbal_info_msg
    def getCameraTypeString(self): return self._hw_msg.cam_type_str
    def getCurrentZoomLevel(self): return self._current_zoom_level_msg.level