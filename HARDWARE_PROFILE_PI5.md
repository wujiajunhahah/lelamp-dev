# LeLamp Pi 5 Hardware Profile

这份清单是当前工作区默认假设的硬件画像。所有脚本和 README 都以它为主。

## 已确认的核心硬件

| 项目 | 当前画像 | 说明 |
| --- | --- | --- |
| 主控板 | Raspberry Pi 5 | 工作区按 `Pi 5` 路线收口 |
| 系统 | Raspberry Pi OS Lite 64-bit | 推荐 `Bookworm` 或更新版本 |
| 存储 | 32GB microSD 或更大 | 64GB 更从容 |
| 音频 HAT | ReSpeaker 2-Mics Pi HAT | 强烈建议 `V2.0` |
| 灯光 | 8x5 WS2812B Matrix | 脚本默认 `40 LEDs` |
| 舵机 | 5x Feetech STS3215 | ID 顺序固定 |
| 舵机驱动 | TTL servo driver | 通过 USB 接到 Pi |
| 扬声器 | 1x JST speaker | 走 ReSpeaker 音频链路 |
| 结构件 | LeLamp 3D printed parts | 按 TNKR / GitHub 模型 |

## 供电策略

| 项目 | 当前策略 | 说明 |
| --- | --- | --- |
| Pi 5 主供电 | 5V / 5A USB-C | 不用 TNKR BOM 里的 5V/2A 给 Pi 5 主板供电 |
| 舵机和外设 | 按原项目 wiring | 但整机实际接线仍需按装配文档确认 |

## 音频版本策略

| ReSpeaker 版本 | 当前处理 |
| --- | --- |
| `V2.0` | 自动配置，默认路径 |
| `V1 / WM8960` | 在 `Pi 5 + Bookworm/Trixie` 上默认拒绝自动配置，避免走不受支持的危险路径 |
| 不确定 | 用 `RESPEAKER_VARIANT=auto`，脚本默认按 `V2.0` 处理 |

## OpenClaw 策略

| 层 | 当前建议 |
| --- | --- |
| 安装方式 | 官方 `install.sh` 或 `install-cli.sh` |
| 手机入口 | Telegram |
| 远程 dashboard | Tailscale Serve |
| 控制方式 | 调用 `uv run -m lelamp.remote_control ...` |

## 仍然不能自动化的部分

- 物理组装
- 舵机贴标签和接线
- 首次舵机 ID 配置
- 首次校准时的人手摆位
- 到手后对 ReSpeaker 实物版本的最终确认
