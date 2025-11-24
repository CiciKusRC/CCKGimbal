"""
Python implementation of SIYI SDK - Updated for ZR30
"""
from crc16_python import crc16_str_swap
import logging
from utils import toHex

class FirmwareMsg:
    seq=0; code_board_ver=''; gimbal_firmware_ver=''; zoom_firmware_ver=''
class HardwareIDMsg:
    CAM_DICT ={'6B': 'ZR10', '73': 'A8 mini', '75': 'A2 mini', '78': 'ZR30', '83': 'ZT6', '7A': 'ZT30'}
    seq=0; id=''; cam_type_str=''
class AutoFocusMsg:
    seq=0; success=False
class ManualZoomMsg:
    seq=0; level=-1
class ManualFocusMsg:
    seq=0; success=False
class GimbalSpeedMsg:
    seq=0; success=False
class CenterMsg:
    seq=0; success=False
class GimbalInfoMsg:
    seq=0; record_state=-1; mount_dir=-1; motion_mode=-1; hdr_sta = -1; video_output = -1
class FuncFeedbackInfoMsg:
    seq=0; info_type=None
class AttitdueMsg:
    seq=0; yaw=0.0; pitch=0.0; roll=0.0; yaw_speed=0.0; pitch_speed=0.0; roll_speed=0.0
class SetGimbalAnglesMsg:
    seq = 0; yaw = 0.0; pitch = 0.0
class RequestDataStreamMsg:
    ATTITUDE_DATA = '01'; LASER_DATA = '02'
    FREQ = {0: '00', 2: '01', 4: '02', 5: '03', 10: '04', 20: '05', 50: '06', 100: '07'}
    seq = 0; data_type = 1; data_frequency = 0
class CurrentZoomValueMsg:
    seq = 0; level=0.0
class MaxZoomValueMsg:
    seq = 0; level = 0.0
class FormatSDCardMsg:
    seq = 0; success = False

class COMMAND:
    ACQUIRE_FW_VER = '01'; ACQUIRE_HW_ID = '02'; AUTO_FOCUS = '04'
    MANUAL_ZOOM = '05'; MANUAL_FOCUS = '06'; GIMBAL_SPEED = '07'
    CENTER = '08'; ACQUIRE_GIMBAL_INFO = '0a'; FUNC_FEEDBACK_INFO = '0b'
    PHOTO_VIDEO_HDR = '0c'; ACQUIRE_GIMBAL_ATT = '0d'; SET_GIMBAL_ATTITUDE = '0e'
    ABSOLUTE_ZOOM = '0f'; REQUEST_IMAGE_MODE = '10'; SEND_IMAGE_MODE = '11'
    REQUEST_MAX_ZOOM = '16'; CURRENT_ZOOM_VALUE = '18'; REQUEST_WORKING_MODE = '19'
    REQUEST_CODEC_SPECS = '20'; SET_CODEC_SPECS = '21'; SET_DATA_STREAM = '25'
    SET_UTC_TIME = '30'; FORMAT_SD_CARD = '48'

class SIYIMESSAGE:
    def __init__(self, debug=False):
        self._debug=debug; LOG_FORMAT='[%(levelname)s] %(asctime)s [SIYIMessage::%(funcName)s] :\t%(message)s'
        logging.basicConfig(format=LOG_FORMAT, level=logging.DEBUG if self._debug else logging.INFO)
        self._logger = logging.getLogger(self.__class__.__name__)
        self.HEADER='5566'; self._ctr ='01'; self._seq= 0

    def encodeMsg(self, data, cmd_id):
        seq = self._seq = (self._seq + 1) & 0xFFFF; seq_hex = toHex(seq, 16); seq_str = seq_hex[2:4] + seq_hex[0:2]
        data_len = self.computeDataLen(data); msg_front = self.HEADER + self._ctr + data_len + seq_str + cmd_id + data
        crc = crc16_str_swap(msg_front)
        if crc: return msg_front + crc
        return ''
    def decodeMsg(self, msg):
        MINIMUM_DATA_LENGTH=10*2
        if not isinstance(msg, str) or len(msg) < MINIMUM_DATA_LENGTH: return None
        payload=msg[:-4]; expected_crc=crc16_str_swap(payload)
        if expected_crc != msg[-4:]: return None
        low_b_len, high_b_len = msg[6:8], msg[8:10]; data_len = int('0x' + high_b_len + low_b_len, 16)
        low_b_seq, high_b_seq = msg[10:12], msg[12:14]; seq = int('0x' + high_b_seq + low_b_seq, 16)
        cmd_id = msg[14:16]; data = msg[16:16 + data_len*2]
        return data, data_len, cmd_id, seq
    def computeDataLen(self, data):
        L = len(data) // 2; len_hex = format(L, '04x'); return len_hex[2:4] + len_hex[0:2]
    
    def requestFirmwareVersionMsg(self): return self.encodeMsg("", COMMAND.ACQUIRE_FW_VER)
    def requestHardwareIDMsg(self): return self.encodeMsg("", COMMAND.ACQUIRE_HW_ID)
    def requestGimbalInfoMsg(self): return self.encodeMsg("", COMMAND.ACQUIRE_GIMBAL_INFO)
    def requestGimbalAttitudeMsg(self): return self.encodeMsg("", COMMAND.ACQUIRE_GIMBAL_ATT)
    def requestMaxZoomMsg(self): return self.encodeMsg("", COMMAND.REQUEST_MAX_ZOOM)
    def requestCurrentZoomMsg(self): return self.encodeMsg("", COMMAND.CURRENT_ZOOM_VALUE)
    def takePhotoMsg(self): return self.encodeMsg(toHex(0, 8), COMMAND.PHOTO_VIDEO_HDR)
    def recordMsg(self): return self.encodeMsg(toHex(2, 8), COMMAND.PHOTO_VIDEO_HDR)
    def setMotionModeMsg(self, mode): return self.encodeMsg(toHex(mode, 8), COMMAND.PHOTO_VIDEO_HDR)
    def setVideoOutputMsg(self, output_type): return self.encodeMsg(toHex(output_type, 8), COMMAND.PHOTO_VIDEO_HDR)
    def autoFocusMsg(self, touch_x=None, touch_y=None):
        data = "01" + (toHex(touch_x, 16) + toHex(touch_y, 16) if touch_x is not None else "")
        return self.encodeMsg(data, COMMAND.AUTO_FOCUS)
    def manualZoomMsg(self, direction): return self.encodeMsg(toHex(direction, 8), COMMAND.MANUAL_ZOOM)
    def manualFocusMsg(self, direction): return self.encodeMsg(toHex(direction, 8), COMMAND.MANUAL_FOCUS)
    def centerGimbalMsg(self): return self.encodeMsg("01", COMMAND.CENTER)
    def setGimbalSpeedMsg(self, yaw_speed, pitch_speed):
        return self.encodeMsg(toHex(yaw_speed, 8) + toHex(pitch_speed, 8), COMMAND.GIMBAL_SPEED)
    def setGimbalAttitudeMsg(self, yaw_deg, pitch_deg):
        return self.encodeMsg(toHex(int(yaw_deg * 10), 16) + toHex(int(pitch_deg * 10), 16), COMMAND.SET_GIMBAL_ATTITUDE)
    def absoluteZoomMsg(self, zoom_level):
        integer_part, decimal_part = int(zoom_level), int((zoom_level * 10) % 10)
        return self.encodeMsg(toHex(integer_part, 8) + toHex(decimal_part, 8), COMMAND.ABSOLUTE_ZOOM)
    def formatSDCardMsg(self): return self.encodeMsg("", COMMAND.FORMAT_SD_CARD)
    def setUtcTimeMsg(self, timestamp): return self.encodeMsg(toHex(timestamp, 64), COMMAND.SET_UTC_TIME)
    
    def setDataStreamMsg(self, data_type, freq_code):
        data = data_type + freq_code
        return self.encodeMsg(data, COMMAND.SET_DATA_STREAM)
