import argparse
import json

from .runtime_config import load_runtime_settings
from .service.motors.motors_service import MotorsService
from .service.rgb.rgb_service import RGBService


def _build_rgb_service(args) -> RGBService:
    return RGBService(
        led_count=args.led_count,
        led_pin=args.led_pin,
        led_freq_hz=args.led_freq_hz,
        led_dma=args.led_dma,
        led_brightness=args.led_brightness,
        led_invert=args.led_invert,
        led_channel=args.led_channel,
    )


def _handle_show_config(args) -> int:
    payload = {
        "lamp_id": args.id,
        "port": args.port,
        "fps": args.fps,
        "led_count": args.led_count,
        "led_pin": args.led_pin,
        "audio_user": args.audio_user,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def _handle_list_recordings(args) -> int:
    service = MotorsService(port=args.port, lamp_id=args.id, fps=args.fps)
    recordings = service.get_available_recordings()

    if not recordings:
        print("No recordings found.")
        return 1

    for recording in recordings:
        print(recording)
    return 0


def _handle_play(args) -> int:
    service = MotorsService(port=args.port, lamp_id=args.id, fps=args.fps)
    recordings = set(service.get_available_recordings())

    if args.name not in recordings:
        print(f"Recording not found: {args.name}")
        return 1

    service.start()
    try:
        service.dispatch("play", args.name)
        if not service.wait_until_idle(timeout=args.timeout):
            print(f"Timed out waiting for recording to finish: {args.name}")
            return 1
    finally:
        service.stop()

    print(f"Finished playing recording: {args.name}")
    return 0


def _handle_solid(args) -> int:
    service = _build_rgb_service(args)
    service.handle_event("solid", (args.red, args.green, args.blue))
    print(f"Set RGB solid color to ({args.red}, {args.green}, {args.blue})")
    return 0


def _handle_clear(args) -> int:
    service = _build_rgb_service(args)
    service.clear()
    print("Cleared RGB LEDs")
    return 0


def build_parser() -> argparse.ArgumentParser:
    settings = load_runtime_settings()

    parser = argparse.ArgumentParser(description="High-level LeLamp control helpers for automation and OpenClaw")
    parser.add_argument("--id", default=settings.lamp_id, help="Lamp ID")
    parser.add_argument("--port", default=settings.port, help="Serial port for the lamp")
    parser.add_argument("--fps", type=int, default=settings.fps, help="Motor playback FPS")
    parser.add_argument("--audio-user", default=settings.audio_user, help="Current audio control user")
    parser.add_argument("--led-count", type=int, default=settings.led_count, help="LED count")
    parser.add_argument("--led-pin", type=int, default=settings.led_pin, help="LED GPIO pin")
    parser.add_argument("--led-freq-hz", type=int, default=settings.led_freq_hz, help="LED frequency")
    parser.add_argument("--led-dma", type=int, default=settings.led_dma, help="LED DMA channel")
    parser.add_argument("--led-brightness", type=int, default=settings.led_brightness, help="LED brightness")
    parser.add_argument("--led-invert", action="store_true", default=settings.led_invert, help="Invert LED signal")
    parser.add_argument("--led-channel", type=int, default=settings.led_channel, help="LED channel")

    subparsers = parser.add_subparsers(dest="command", required=True)

    show_config = subparsers.add_parser("show-config", help="Print the resolved control configuration")
    show_config.set_defaults(handler=_handle_show_config)

    list_recordings = subparsers.add_parser("list-recordings", help="List available motion recordings")
    list_recordings.set_defaults(handler=_handle_list_recordings)

    play = subparsers.add_parser("play", help="Play a named motion recording")
    play.add_argument("name", help="Recording name")
    play.add_argument("--timeout", type=float, default=120.0, help="Playback timeout in seconds")
    play.set_defaults(handler=_handle_play)

    solid = subparsers.add_parser("solid", help="Set the LEDs to a solid RGB color")
    solid.add_argument("red", type=int)
    solid.add_argument("green", type=int)
    solid.add_argument("blue", type=int)
    solid.set_defaults(handler=_handle_solid)

    clear = subparsers.add_parser("clear", help="Turn off all LEDs")
    clear.set_defaults(handler=_handle_clear)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
