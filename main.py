#!/usr/bin/env python3

import argparse
import sys
import os
import math
import tempfile

from collections import deque
from pathlib import Path
from datetime import datetime, timedelta

from mpeg2ts import ts
from mpeg2ts.packetize import packetize_section, packetize_pes
from mpeg2ts.section import Section
from mpeg2ts.pat import PATSection
from mpeg2ts.pmt import PMTSection
from mpeg2ts.h264 import H264PES

from mpeg2ts.parser import SectionParser, PESParser

from cea708.builder import CEA708Builder

builder = CEA708Builder(1)
TIME = 0
def cea708(string):
  global TIME
  TIME += 1
  return builder.cea708(
    CEA708Builder.buildDefineWindow(0) +
    CEA708Builder.buildClearWindows(0b00000001) +
    CEA708Builder.buildSetCurrentWindow(0) +
    CEA708Builder.buildSetWindowAttributes() +
    CEA708Builder.buildSetPenLocation(0, 0) +
    CEA708Builder.buildSetPenAttributes() +
    CEA708Builder.buildP16(string) +
    CEA708Builder.buildCR()
  )

if __name__ == "__main__":
  parser = argparse.ArgumentParser(description=('CEA-708'))

  parser.add_argument('-i', '--input', type=argparse.FileType('rb'), nargs='?', default=sys.stdin.buffer)
  parser.add_argument('-o', '--output', type=argparse.FileType('wb'), nargs='?', default=sys.stdout.buffer)
  parser.add_argument('-s', '--SID', type=int, nargs='?')

  args = parser.parse_args()

  PAT_Parser = SectionParser(PATSection)
  PMT_Parser = SectionParser(PMTSection)
  H264_PES_Parser = PESParser(H264PES)

  PMT_PID = None
  PCR_PID = None
  H264_PID = None

  H264_CC = 0
  SHOW = False

  while args.input:
    isEOF = False
    while True:
      sync_byte = args.input.read(1)
      if sync_byte == b'':
        isEOF = True
        break
      if sync_byte == ts.SYNC_BYTE:
        break
 
    if isEOF:
      break

    packet = ts.SYNC_BYTE + args.input.read(ts.PACKET_SIZE - 1)

    if ts.pid(packet) == 0x00:
      args.output.write(packet)
      PAT_Parser.push(packet)
      for PAT in PAT_Parser:
        if PAT.CRC32() != 0: continue
        SHOW = True

        for program_number, program_map_PID in PAT:
          if program_number == 0: continue

          if program_number == args.SID:
            PMT_PID = program_map_PID
          elif not PMT_PID and not args.SID:
            PMT_PID = program_map_PID

    elif ts.pid(packet) == PMT_PID:
      args.output.write(packet)
      PMT_Parser.push(packet)
      for PMT in PMT_Parser:
        if PMT.CRC32() != 0: continue

        PCR_PID = PMT.PCR_PID
        for stream_type, elementary_PID in PMT:
          if stream_type == 0x1b:
            H264_PID = elementary_PID

    elif ts.pid(packet) == H264_PID:
      H264_PES_Parser.push(packet)

      """
      if ts.has_pcr(packet):
        modified = bytearray(packet)
        modified[3] = ((modified[3] & 0xf0) | (H264_CC & 0x0f))
        H264_CC = (H264_CC + 1) & 0x0f
        args.output.write(packet)
        continue
      """

      for H264 in H264_PES_Parser:
        modified = bytearray(H264[:H264.PES_packet_offset()])

        prev, prev_nal_unit_type, begin, added = None, None, H264.PES_packet_offset(), False
        while begin < len(H264):
          nalu, nal_unit_type = None, None
          if begin + 3 < len(H264) and int.from_bytes(H264[begin:begin+4], byteorder='big') == 1:
            if prev is not None:
              nalu = bytes(H264[prev:begin])
              nal_unit_type = prev_nal_unit_type
            prev = begin
            prev_nal_unit_type = H264[begin + 4] & 0x1F
            begin += 4
          elif begin + 2 < len(H264) and int.from_bytes(H264[begin:begin+3], byteorder='big') == 1:
            if prev is not None:
              nalu = bytes(H264[prev:begin])
              nal_unit_type = prev_nal_unit_type
            prev = begin
            prev_nal_unit_type = H264[begin + 3] & 0x1F
            begin += 3
          else:
            begin += 1
          
          if nalu:
            modified += nalu
            if nal_unit_type == 0x09 and SHOW:
              #modified += cea708('さんぷる')
              modified += cea708('さんぷる')
              SHOW = False
              added = True

        if prev is not None:
          modified += H264[prev:begin]
          if not added and SHOW:
            #modified += cea708('さんぷる')
            SHOW = False
            added = True

        packets = packetize_pes(modified, False, False, H264_PID, 0, H264_CC)
        H264_CC = (H264_CC + len(packets)) & 0x0f
        for p in packets: args.output.write(p)
    
    else:
      args.output.write(packet)
    
