#!/usr/bin/env python3

from itertools import zip_longest

class CEA708Builder:
  def __init__(self, service):
    self.service = max(0, service)
    self.sequence = 0
  
  def cea708(self, commands):
    results = []
    begin, end = 0, 0

    while begin < len(commands):
      while end < len(commands) and sum([len(command) for command in commands[begin:end]]) <= 0x1f:
        end += 1
      if sum([len(command) for command in commands[begin:end]]) > 0x1f:
        end -= 1
      part = b''.join(commands[begin:end])

      tail_payload = b''.join([
         b'\xfe' + bytes([fst]) + bytes([snd or 0x0])
        for fst, snd in zip_longest(part[0::2], part[1::2])
      ])
      block_header = bytes([((self.service & 0x07) << 5) | (len(part) & 0x1f)])
      packet_header = bytes([((self.sequence & 0x03) << 6) | (((len(part) + 1) // 2 + 1) & 0x1f)])
      start_payload = b'\xff' + packet_header + block_header

      cea608_payload = start_payload + tail_payload
      cea608_packet = bytes([0xc0 | (len(cea608_payload) // 3) & 0x1F]) + b'\xff' + cea608_payload + b'\xff'

      sei_content = bytes([0xb5, 0x0, 0x31, 0x47, 0x41, 0x39, 0x34, 0x3]) + cea608_packet
      sei_rbsp = bytes([0x6, 0x4, len(sei_content)]) + sei_content + b'\x80'
      sei_ebsp = bytearray(sei_rbsp[:2])
      for index in range(2, len(sei_rbsp)):
        if sei_rbsp[index - 2] == 0 and sei_rbsp[index - 1] == 0 and sei_rbsp[index] in [0, 1, 2, 3]:
          sei_ebsp += b'\x03'
        sei_ebsp += sei_rbsp[index].to_bytes(1, byteorder='big')

      self.sequence = (self.sequence + 1) & 0x03
      results.append((1).to_bytes(4, byteorder='big') + sei_ebsp)
      begin = end

    return b''.join(results)

  def buildDeleteWindows(bit):
    return [bytes([0x8c, bit])]
  
  def buildClearWindows(bit):
    return [bytes([0x88, bit])]
  
  def buildSetCurrentWindow(window):
    return [bytes([0x80 | (window & 0x07)])]
  
  def buildDefineWindow(window):
    return [bytes([0x98 | (window & 0x07), 0x20, 0x3c, 0x37, 0x2, 0x29, 0x11])]
  
  def buildSetWindowAttributes():
    return [bytes([0x97, 0xd5, 0x15, 0xc, 0x20])]

  def buildSetPenLocation(row, col):
    return [bytes([0x92, row & 0x0F, col & 0x3F])]

  def buildSetPenAttributes():
    return [bytes([0x90, 0x5, 0x0])]

  def buildP16(string):
    return [b'\x18' + ch.encode('utf_16_be') for ch in string]

  def buildCR():
    return [bytes([0x0d])]