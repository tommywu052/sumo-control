import time
import struct
import socket
import datetime
import logging
from collections import defaultdict
from threading import Thread, Lock, Event

"""
For full reference, see: http://developer.parrot.com/docs/bebop/ARSDK_Protocols.pdf
The xml files for command definitions can be found here: https://github.com/Parrot-Developers/arsdk-xml/tree/master/xml

A commands is identified by its first 4 bytes:
    - Project/Feature (1 byte)
    - Class ID in project/feature (1 byte)
    - Command ID in class (2 bytes) 
All data is sent in Little Endian byte order
"""


class SumoSender(Thread):
    """
    Sends commands to the Jumping Sumo. PCMD commands are sent at a fixed frequency (every 25ms)
    """

    def __init__(self, host, port):
        Thread.__init__(self, name='SumoSender')
        self.setDaemon(True)
        self.parser = SumoMarshaller()
        self.host = host
        self.port = port
        self.send_lock = Lock()
        self.should_run = Event()
        self.should_run.set()
        self.seq_ids = defaultdict(int)
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.cmd_activate = False
        # Initial command (no motion)
        self.cmd = _pack_frame(move_cmd(0, 0))
        assert _is_pcmd(self.cmd)

    def _update_seq(self, cmd):
        """
        Updates the sequence number for the given framed command
        """
        assert len(cmd) > 3, str(cmd)
        buffer_id = cmd[1]

        self.seq_ids[buffer_id] = (self.seq_ids[buffer_id] + 1) % 256
        return cmd[:2] + struct.pack('<B', self.seq_ids[buffer_id]) + cmd[3:]

    def send(self, cmd):
        """
        Sends the given command to the Jumping Sumo. Non-PCMD commands are sent immediately
        while PCMD commands are sent at the next cycle (see run). cmd is the payload and the
        method creates a frame by prepending a header
        """
        #print('cmd:')
        #print (cmd)

        if cmd is not None:
            with self.send_lock:
                frame = self._update_seq(_pack_frame(cmd))
                if _is_pcmd(frame):
                    self.cmd = frame
                else:
                    self.socket.sendto(frame, (self.host, self.port))

    def run(self):
        logging.info('SumoSender started.')

        # Initial configuration
        date_time = datetime.datetime.now()
        self.send(sync_date_cmd(date_time.date()))
        self.send(sync_time_cmd(date_time.time()))
        self.send(set_media_streaming_cmd(enable=True))

        # Run loop
        while self.should_run.isSet():
            with self.send_lock:
                logging.debug('PCMD: {}'.format(self.cmd))
                self.socket.sendto(self.cmd, (self.host, self.port))
                self.cmd = _pack_frame(move_cmd(0, 0))

            time.sleep(0.025)

    def mkcmd1(self, klass, func, param):
        self.parser.initCommand('\x02\x0b\x00\x0f\x00\x00\x00\x03')
        self.parser.marshal('bHI',klass, func, param)

        self.parser.setSeqId(self.seq_ids[self.cmd[1]] )
        #self.cmd_seq = (self.cmd_seq + 1 ) % 256

        return self.parser.getEncodedCommand()

    
    def posture(self, param):
    # param = enum[standing, jumper, kicker]
        cmd = self.mkcmd1(0, 1,param)
    #    print[cmd]
        self.cmd_activate = True
        self.send(cmd)
        self.cmd_activate = False

    def disconnect(self):
        """
        Stops the main loop and closes the connection to the Jumping Sumo
        """
        self.should_run.clear()
        self.socket.close()


def move_cmd(speed, turn):
    """
    Project: jpsumo(3), Class: Piloting (0), Command: PCMD (0)
        Flag: boolean for touch screen
        Speed: [-100, 100]
        Turn: [-100, 100]
    """
    return struct.pack('<BBHBbb', 3, 0, 0, (speed != 0 or turn != 0), speed, turn)

def jumpCmd( param ):
    # ARCOMMANDS_ID_PROJECT_JUMPINGSUMO = 3,
    # ARCOMMANDS_ID_JUMPINGSUMO_CLASS_ANIMATIONS = 2,    
    # ARCOMMANDS_ID_JUMPINGSUMO_ANIMATIONS_CMD_JUMP = 3,
    # param = enum[long, high]
    return struct.pack("<BBHI", 3, 2, 3, param )

def set_media_streaming_cmd(enable=True):
    """
    Project: jpsumo(3), Class: MediaStreaming (18), Command: VideoEnable (0)
    Args:
        enable: 1 to enable, 0 to disable
    :return:
    """
    flag = 1 if enable else 0
    return struct.pack('<BBHB', 3, 18, 0, flag)


def sync_date_cmd(sync_date):
    """
    Project: Commom(0), Class: Common(4), Command: CurrentDate(1)
        Date (ISO-8601 format)
    """
    return struct.pack('<BBH', 0, 4, 1) + sync_date.isoformat().encode() + b'\0'


def sync_time_cmd(sync_time):
    """
    Project: Commom(0), Class: Common(4), Command: CurrentDate(2)
        Time (ISO-8601 format)
    """
    return struct.pack('<BBH', 0, 4, 2) + sync_time.strftime('T%H%M%S+0000').encode() + b'\0'


def _pack_frame(payload):
    """
    Creates a complete frame by prepending a header to the given payload
    Data type: normal data(2)
    Target buffer ID:
    Sequence number
    Frame size
    Payload
    """
    data_type = 2
    buffer_id = 10
    seq_no = 0  # Will be set at a later time
    frame_size = 7 + len(payload)

    header = struct.pack('<BBBI', data_type, buffer_id, seq_no, frame_size)
    return header + payload


def _is_pcmd(cmd):
    """
    Returns true if the given command is a pcmd command and false otherwise
    """
    # BBHBbb: Header (7) + payload (7)
    if len(cmd) != 14:
        return False

    return struct.unpack('<BBH', cmd[7:11]) == (3, 0, 0)



#
# Marshal/Unmarshal command packet for JumpingSumo
#
class SumoMarshaller:
  def __init__(self, buffer=''):
    self.buffer=buffer
    self.bufsize = len(buffer)

    self.offset=0

    self.header_size = self.calcsize('BBBHH')
    self.encbuf=None
    self.encpos=0

  #
  #  for buffer
  #
  def setBuffer(self, buffer):
    if self.buffer : del self.buffer
    self.buffer=buffer
    self.bufsize=len(buffer)
    self.offset=0

  def clearBuffer(self):
    self.setBuffer("")

  def appendBuffer(self, buffer):
    self.buffer += buffer
    self.bufsize = len(self.buffer)

  #
  #  check message format...  
  #
  def checkMsgFormat(self, buffer, offset=0):
    bufsize = len(buffer)

    if bufsize - offset >= self.header_size:
      self.buffer=buffer
      self.offset=offset
      (cmd, func, seq, size, fid) = self.unmarshal('bbbHH')

      if cmd in (0x01, 0x02, 0x03, 0x04):
        if size <= bufsize - offset:
          return size
        else:
          print ("Short Packet %d/%d" % (bufsize, size))
          return 0

      else:
        print ("Error in checkMsgFormat")
        return -1

    return 0

  #
  # extract message from buffer
  #
  def getMessage(self, buffer=None, offset=0):
    if buffer: self.buffer = buffer
    res =  self.checkMsgFormat(self.buffer, offset)

    if res > 0:
      start = offset 
      end =  offset + res
      cmd = self.buffer[start:end]
      self.buffer =  self.buffer[end:]
      self.offset =  0
      return cmd

    elif res == 0:
      return ''

    else:
      self.skipBuffer()
      return None

  #
  #  skip buffer, but not implemented....
  #
  def skipBuffer(self):
      print ("call skipBuffer")
      return 
  #
  #  print buffer for debug
  #
  def printPacket(self, data):
    for x in data:
      print ("0x%02x" % ord(x)) 
   

  #
  #  dencoding data
  # 
  def unmarshalString(self, offset=-1):
    if offset < 0 : offset=self.offset
    try:
     endpos = self.buffer.index('\x00', offset)
     size = endpos - offset
     if(size > 0):
       (str_res,) =  struct.unpack_from('!%ds' % (size), self.buffer, offset)
       self.offset += size + 1
       return str_res 
     else:
       return ""
    except:
      print ("Error in parseCommand")
      return None

  def unmarshalNum(self, fmt, offset=-1):
    if offset < 0 : offset=self.offset
    try:
     (res,) =  struct.unpack_from(fmt, self.buffer, offset)
     self.offset = offset + struct.calcsize(fmt)
     return res
    except:
      print ("Error in unmarshalNum")
      return None
     
  def unmarshalUShort(self, offset=-1):
    return self.unmarshalNum('<H', offset)
     
  def unmarshalUInt(self, offset=-1):
    return self.unmarshalNum('<I', offset)
     
  def unmarshalDouble(self, offset=-1):
    return self.unmarshalNum('d', offset)
     
  def unmarshalBool(self, offset=-1):
    return self.unmarshalNum('B', offset)

  def unmarshalByte(self, offset=-1):
    return self.unmarshalNum('b', offset)

  def unmarshalChar(self, offset=-1):
    return self.unmarshalNum('c', offset)

  def unmarshal(self, fmt):
    res=[]
    for x in fmt:
      if x in ('i', 'h', 'I', 'H'):
        res.append(self.unmarshalNum('<'+x))
      elif x in ('d', 'B', 'c', 'b'):
        res.append(self.unmarshalNum(x))
      elif x == 'S':
        res.append(self.unmarshalString())
    return res

  #  generate command
  #
  def createCommand(self):
    self.encbuf=bytearray()
    self.encpos=0 

  def initCommand(self, cmd):
    self.encbuf=bytearray(cmd)
    self.encpos=len(cmd) 

  def appendCommand(self, cmd):
    self.encbuf = self.encbuf + bytearray(cmd)
    self.encpos += len(cmd) 

  def setCommandSize(self):
    size = len(self.encbuf)
    struct.pack_into('<H', self.encbuf, 3, size)

  def setSeqId(self, sid):
    sid = sid % 256
    struct.pack_into('B', self.encbuf, 2, sid)

  def getEncodedCommand(self):
    self.setCommandSize()
    return str(self.encbuf)

  def getEncodedDataCommand(self):
    return str(self.encbuf)

  def clearEncodedCommand(self):
    if self.encbuf : del self.encbuf
    self.encbuf=None
    return
  #
  #  encoding data
  # 
  def marshalNumericData(self, fmt, s):
    enc_code = bytearray( struct.calcsize(fmt))
    struct.pack_into(fmt, enc_code, 0, s)
    self.encbuf = self.encbuf+enc_code
    self.encpos += struct.calcsize(fmt)

  def marshalChar(self, s):
    if type(s) == int:
      self.marshalNumericData('c', chr(s))
    else:
      self.marshalNumericData('c', s)

  def marshalUShort(self, s):
    self.marshalNumericData('>H', s)

  def marshalUInt(self, s):
    self.marshalNumericData('>I', s)

  def marshalDouble(self, d):
    self.marshalNumericData('>d', d)

  def marshalBool(self, d):
    if d :
      self.marshalNumericData('B', 1)
    else :
      self.marshalNumericData('B', 0)

  def marshalByte(self, d):
      self.marshalNumericData('b', d)

  def marshalString(self, str):
    size=len(str)
    enc_size = size+1
    enc_code = bytearray( size )

    if size > 0 :
      struct.pack_into('%ds' % (size,), enc_code, 0, str)

    self.encbuf = self.encbuf+enc_code+'\x00'
    self.encpos += enc_size

  def marshal(self, fmt, *data):
    pos = 0
    for x in fmt:
      if x in ('i', 'h', 'I', 'H', 'd'):
        self.marshalNumericData('<'+x, data[pos])
      elif x  == 'b':
        self.marshalByte(data[pos])
      elif x  == 'B':
        self.marshalBool(data[pos])
      elif x  == 'c':
        self.marshalChar(data[pos])
      elif x == 'S':
        self.marshalString(data[pos])
      elif x == 's':
        self.marshalString(data[pos])
      pos += 1
    return 

  def calcsize(self, fmt):
    res = 0
    for x in fmt:
      if x in ('i', 'h', 'I', 'H', 'd', 'B'):
        res += struct.calcsize(x)
      else:
        print ("Unsupported format:",x)
    return res

  #
  #  print encoded data for debug
  #
  def printEncoded(self):
    count=0
    for x in self.encbuf:
      print("0x%02x" % x)
      if count % 8 == 7 : 
        print(count)
    