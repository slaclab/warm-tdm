#!/usr/bin/env python3
"""Decode classic tcpdump pcap into compact RSSI/SRP CSV; standard library only."""
import argparse
import csv
import hashlib
import ipaddress
import struct
import sys
import zlib


def frames(path):
    with open(path, 'rb') as f:
        header = f.read(24)
        formats = {b'\xd4\xc3\xb2\xa1': ('<', 1000000), b'\xa1\xb2\xc3\xd4': ('>', 1000000),
                   b'\x4d\x3c\xb2\xa1': ('<', 1000000000), b'\xa1\xb2\x3c\x4d': ('>', 1000000000)}
        if len(header) != 24 or header[:4] not in formats:
            raise ValueError('Expected classic pcap from tcpdump -w (not pcapng).')
        endian, scale = formats[header[:4]]
        linktype = struct.unpack(endian+'I', header[20:24])[0] & 0xffff
        if linktype not in (1, 101, 113, 228, 276):
            raise ValueError(f'Unsupported pcap link type {linktype}')
        number = 0
        while True:
            h = f.read(16)
            if not h:
                break
            if len(h) != 16:
                raise ValueError('Truncated packet header')
            sec, fraction, size, original = struct.unpack(endian+'IIII', h)
            if size > 16*1024*1024:
                raise ValueError('Implausible captured packet length')
            data = f.read(size)
            if len(data) != size:
                raise ValueError('Truncated packet data')
            number += 1
            yield number, sec+fraction/scale, linktype, data, size < original


def decode(linktype, data):
    offset = {1: 14, 101: 0, 113: 16, 228: 0, 276: 20}[linktype]
    if linktype == 1 and len(data) >= 14:
        ether_type = int.from_bytes(data[12:14], 'big')
        while ether_type in (0x8100, 0x88a8):
            if len(data) < offset+4:
                return None
            ether_type = int.from_bytes(data[offset+2:offset+4], 'big')
            offset += 4
        if ether_type != 0x0800:
            return None
    ip = data[offset:]
    if len(ip) < 20 or ip[0] >> 4 != 4 or ip[9] != 17:
        return None
    if int.from_bytes(ip[6:8], 'big') & 0x3fff:
        raise ValueError('Fragmented IPv4 packet: reassembly required; retain raw capture.')
    ihl = (ip[0] & 15)*4
    ip = ip[:int.from_bytes(ip[2:4], 'big')]
    udp = ip[ihl:]
    if ihl < 20 or len(udp) < 8:
        return None
    src, dst, length = struct.unpack('!HHH', udp[:6])
    if len(udp) < length:
        raise ValueError('Truncated UDP payload')
    return str(ipaddress.IPv4Address(ip[12:16])), src, str(ipaddress.IPv4Address(ip[16:20])), dst, udp[8:length]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('pcap')
    p.add_argument('--board-ip', default='192.168.3.11')
    p.add_argument('--port', type=int, choices=(8192, 8193))
    args = p.parse_args()
    fields = ['packet', 'epoch', 'direction', 'src', 'sport', 'dst', 'dport', 'udp_bytes',
              'flags', 'seq', 'ack', 'busy', 'syn', 'null', 'rst', 'rssi_checksum_ok',
              'payload_hash', 'tdest', 'sof', 'eof', 'packetizer_crc_ok',
              'srp_id', 'srp_address', 'srp_size', 'srp_op', 'srp_status']
    out = csv.DictWriter(sys.stdout, fields)
    out.writeheader()
    for number, stamp, linktype, data, truncated in frames(args.pcap):
        if truncated:
            raise ValueError(f'Packet {number} was snaplen-truncated; capture with -s 0')
        parsed = decode(linktype, data)
        if not parsed:
            continue
        src, sport, dst, dport, payload = parsed
        if args.board_ip not in (src, dst):
            continue
        if not ({sport, dport} & ({args.port} if args.port else {8192, 8193})):
            continue
        if len(payload) < 8:
            raise ValueError(f'Packet {number}: short RSSI header')
        flags, length, seq, ack = payload[:4]
        if length < 8 or length > len(payload) or length % 2:
            raise ValueError(f'Packet {number}: invalid RSSI header length {length}')
        checksum = sum(int.from_bytes(payload[j:j+2], 'big') for j in range(0, length, 2))
        while checksum >> 16:
            checksum = (checksum & 65535)+(checksum >> 16)
        app = payload[length:]
        row = dict(packet=number, epoch=f'{stamp:.9f}', direction='FPGA->host' if src == args.board_ip else 'host->FPGA',
                   src=src, sport=sport, dst=dst, dport=dport, udp_bytes=len(payload),
                   flags=f'0x{flags:02x}', seq=seq, ack=ack, busy=int(bool(flags & 1)),
                   syn=int(bool(flags & 0x80)), null=int(bool(flags & 8)), rst=int(bool(flags & 16)),
                   rssi_checksum_ok=int(checksum == 65535),
                   payload_hash=hashlib.sha256(app).hexdigest()[:16] if app else '')
        if not flags & 0x98 and len(app) >= 24 and app[0] & 15 == 2:
            sof, eof = bool(app[7] & 0x80), bool(app[-7] & 1)
            row.update(tdest=app[2], sof=int(sof), eof=int(eof))
            # CRC is cumulative across fragments: validate only a complete single-frame packet.
            if sof and eof and app[0] & 0x20:
                row['packetizer_crc_ok'] = int(zlib.crc32(app[:-4]) == int.from_bytes(app[-4:], 'big'))
            body = app[8:-8]
            if eof:
                last = app[-6]
                if not 1 <= last <= 8:
                    raise ValueError(f'Packet {number}: invalid packetizer final-byte count')
                if last != 8:
                    body = body[:-(8-last)]
            if 8192 in (sport, dport) and sof and len(body) >= 20 and body[0] == 3:
                row.update(srp_id=int.from_bytes(body[4:8], 'little'),
                           srp_address=f'0x{int.from_bytes(body[8:16], "little"):016x}',
                           srp_size=int.from_bytes(body[16:20], 'little')+1,
                           srp_op=(int.from_bytes(body[:4], 'little') >> 8) & 3)
                if eof and src == args.board_ip and len(body) >= 24:
                    row['srp_status'] = f'0x{int.from_bytes(body[-4:], "little"):08x}'
        out.writerow(row)


if __name__ == '__main__':
    main()
