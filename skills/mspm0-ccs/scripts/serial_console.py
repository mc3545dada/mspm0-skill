#!/usr/bin/env python3
"""Small serial console for MSPM0 UART smoke tests."""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime

try:
    import serial
    import serial.tools.list_ports
except ImportError as exc:
    raise SystemExit(
        "pyserial is required. Install it with: python -m pip install pyserial"
    ) from exc


def list_ports() -> int:
    ports = list(serial.tools.list_ports.comports())
    if not ports:
        print("No serial ports found.")
        return 1
    for port in ports:
        print(f"{port.device}\t{port.description}\t{port.hwid}")
    return 0


def format_bytes(data: bytes, *, as_hex: bool, encoding: str) -> str:
    if as_hex:
        return " ".join(f"{byte:02X}" for byte in data)
    return data.decode(encoding, errors="replace")


def timestamp_prefix() -> str:
    now = datetime.now()
    return f"[{now:%H:%M:%S}.{now.microsecond // 1000:03d}]"


def parse_hex_payload(text: str) -> bytes:
    compact = text.replace(",", " ").replace("0x", "").replace("0X", "")
    parts = compact.split()
    if len(parts) == 1 and len(parts[0]) > 2:
        compact = parts[0]
        if len(compact) % 2:
            raise ValueError("hex payload must contain an even number of digits")
        parts = [compact[index : index + 2] for index in range(0, len(compact), 2)]
    try:
        return bytes(int(part, 16) for part in parts)
    except ValueError as exc:
        raise ValueError(f"invalid hex payload: {text}") from exc


def build_tx_payload(args: argparse.Namespace) -> bytes | None:
    if args.send is not None and args.send_hex is not None:
        raise ValueError("use only one of --send or --send-hex")
    if args.send_hex is not None:
        payload = parse_hex_payload(args.send_hex)
    elif args.send is not None:
        payload = args.send.encode(args.encoding)
    else:
        return None

    if args.send_crlf:
        payload += b"\r\n"
    elif args.send_line or args.append_newline:
        payload += b"\n"
    return payload


def open_serial(args: argparse.Namespace) -> serial.Serial:
    return serial.Serial(
        port=args.port,
        baudrate=args.baudrate,
        bytesize=args.bytesize,
        parity=args.parity,
        stopbits=args.stopbits,
        timeout=args.timeout,
        write_timeout=args.write_timeout,
        rtscts=args.rtscts,
        dsrdtr=args.dsrdtr,
        xonxoff=args.xonxoff,
    )


def run_console(args: argparse.Namespace) -> int:
    start = time.monotonic()
    received = 0

    try:
        payload = build_tx_payload(args)
        with open_serial(args) as ser:
            print(
                f"Opened {ser.port} at {ser.baudrate} "
                f"{ser.bytesize}{ser.parity}{ser.stopbits}"
            )

            sent_count = 0
            next_send = time.monotonic()
            if payload is not None and args.repeat < 1:
                raise ValueError("--repeat must be at least 1")

            while True:
                if payload is not None and sent_count < args.repeat and time.monotonic() >= next_send:
                    ser.write(payload)
                    ser.flush()
                    sent_count += 1
                    print(f"TX {len(payload)} bytes")
                    next_send = time.monotonic() + args.interval

                if args.duration is not None and time.monotonic() - start >= args.duration:
                    break

                data = ser.read(args.chunk_size)
                if not data:
                    continue

                received += len(data)
                text = format_bytes(data, as_hex=args.hex, encoding=args.encoding)
                if args.timestamp:
                    prefix = timestamp_prefix()
                    print(f"{prefix} {text}", end="" if not args.hex else "\n")
                else:
                    print(text, end="" if not args.hex else "\n")
                sys.stdout.flush()

    except serial.SerialException as exc:
        print(f"Serial error: {exc}", file=sys.stderr)
        return 2
    except ValueError as exc:
        print(f"Argument error: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print()

    if args.duration is not None:
        print(f"\nDone. RX {received} bytes.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read and write a UART serial port.")
    parser.add_argument("--list", action="store_true", help="List available serial ports and exit.")
    parser.add_argument("-p", "--port", help="Serial port, such as COM6.")
    parser.add_argument("-b", "--baudrate", type=int, default=115200, help="Baud rate. Default: 115200.")
    parser.add_argument("--bytesize", type=int, default=8, choices=(5, 6, 7, 8), help="Data bits. Default: 8.")
    parser.add_argument("--parity", default="N", choices=("N", "E", "O", "M", "S"), help="Parity. Default: N.")
    parser.add_argument("--stopbits", type=float, default=1, choices=(1, 1.5, 2), help="Stop bits. Default: 1.")
    parser.add_argument("--timeout", type=float, default=0.2, help="Read timeout seconds. Default: 0.2.")
    parser.add_argument("--write-timeout", type=float, default=1.0, help="Write timeout seconds. Default: 1.0.")
    parser.add_argument("--duration", type=float, help="Read duration seconds. Omit to read until Ctrl+C.")
    parser.add_argument("--chunk-size", type=int, default=128, help="Read chunk size. Default: 128.")
    parser.add_argument("--encoding", default="utf-8", help="Text encoding. Default: utf-8.")
    parser.add_argument("--hex", action="store_true", help="Print received bytes as hex.")
    parser.add_argument("--timestamp", action="store_true", help="Prefix received data with local timestamps.")
    parser.add_argument("--send", help="Text to send after opening the port.")
    parser.add_argument("--send-line", action="store_true", help="Append LF to the sent payload. Useful for line-based MCU parsers.")
    parser.add_argument("--append-newline", action="store_true", help="Deprecated alias for --send-line.")
    parser.add_argument("--send-crlf", action="store_true", help="Append CRLF to the sent payload. If combined with --send-line, CRLF is used instead of LF.")
    parser.add_argument("--send-hex", help="Hex bytes to send, such as '01 02 0A' or '01020A'.")
    parser.add_argument("--repeat", type=int, default=1, help="Number of times to send the payload. Default: 1.")
    parser.add_argument("--interval", type=float, default=1.0, help="Seconds between repeated sends. Default: 1.0.")
    parser.add_argument("--rtscts", action="store_true", help="Enable RTS/CTS flow control.")
    parser.add_argument("--dsrdtr", action="store_true", help="Enable DSR/DTR flow control.")
    parser.add_argument("--xonxoff", action="store_true", help="Enable software flow control.")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.list:
        return list_ports()
    if not args.port:
        parser.error("--port is required unless --list is used")
    return run_console(args)


if __name__ == "__main__":
    raise SystemExit(main())
