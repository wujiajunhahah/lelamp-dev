# LeLamp Runtime for Pi 5

这个目录已经按 `Pi 5 + LeLamp + OpenClaw` 做过本地增强，不是上游原样。

## 一句话入口

在树莓派上执行：

```bash
cd ~/lelamp_runtime
chmod +x scripts/pi5_all_in_one.sh
./scripts/pi5_all_in_one.sh
```

这是当前推荐的唯一入口。

## 目录里现在最重要的东西

### 安装与编排脚本

- [scripts/pi5_all_in_one.sh](./scripts/pi5_all_in_one.sh)
  总控入口，负责 Pi 5 检测、`.env`、LeLamp、OpenClaw、post-boot finalizer。
- [scripts/pi_setup_max.sh](./scripts/pi_setup_max.sh)
  只处理 LeLamp runtime、依赖、音频 overlay、可选 systemd 服务。
- [scripts/openclaw_pi5_setup.sh](./scripts/openclaw_pi5_setup.sh)
  处理 OpenClaw、可选 Tailscale、可选 onboarding。
- [scripts/install_openclaw_skill.sh](./scripts/install_openclaw_skill.sh)
  把 LeLamp 的 OpenClaw skill 装到 `~/.openclaw/skills`。
- [scripts/pi5_post_reboot_finalize.sh](./scripts/pi5_post_reboot_finalize.sh)
  重启后自动跑一遍设备检查和可选下载步骤。

### 运行时配置

- [.env.example](./.env.example)
  环境变量模板。
- [lelamp/runtime_config.py](./lelamp/runtime_config.py)
  统一读取运行时配置。
- [main.py](./main.py)
  离散动作模式。
- [smooth_animation.py](./smooth_animation.py)
  平滑动作模式，默认推荐。

### OpenClaw 集成

- [lelamp/remote_control.py](./lelamp/remote_control.py)
  给 OpenClaw 调用的安全高层控制 CLI。
- [openclaw/skills/lelamp-control/SKILL.md](./openclaw/skills/lelamp-control/SKILL.md)
  OpenClaw 技能模板。

## 当前默认硬件假设

- Raspberry Pi 5
- Raspberry Pi OS Lite 64-bit
- ReSpeaker 2-Mics Pi HAT V2.0
- 8x5 WS2812B = 40 LEDs
- 5x STS3215
- TTL servo driver

如果你的 `ReSpeaker` 不是 `V2.0`，最重要的变量是：

```bash
RESPEAKER_VARIANT=auto|v2|v1|skip
```

默认是 `auto`，在 `Pi 5` 上会优先走 `v2`。

## 环境变量

最关键的是这几个：

```bash
OPENAI_API_KEY=
LIVEKIT_URL=
LIVEKIT_API_KEY=
LIVEKIT_API_SECRET=
LELAMP_ID=lelamp
LELAMP_PORT=/dev/ttyACM0
LELAMP_AUDIO_USER=pi
LELAMP_LED_COUNT=40
```

## OpenClaw 该怎么理解

OpenClaw 在这套系统里是“远程控制和消息入口层”，不是低延迟 teleop 引擎。

适合：

- 手机发命令让灯动
- 远程触发 recording
- 远程改灯光
- 远程健康检查

不适合：

- 真正实时摇杆控制
- 实时视频遥操作

## OpenClaw 对 LeLamp 暴露的命令

```bash
uv run -m lelamp.remote_control show-config
uv run -m lelamp.remote_control list-recordings
uv run -m lelamp.remote_control play curious
uv run -m lelamp.remote_control solid 255 160 32
uv run -m lelamp.remote_control clear
```

## 重启后自动收尾

总控脚本会安装一个 one-shot systemd 服务，在下一次重启后自动执行：

- `download-files`
- `aplay -l`
- `arecord -l`
- `/dev/ttyACM*`
- `openclaw status`

输出会写到：

- `POST_BOOT_REPORT.md`

## 仍然需要你人手参与的步骤

- 首次物理组装
- 舵机接线
- 舵机 ID 设置
- 首次校准摆位

也就是说：

- 软件与系统 bring-up 已经被尽量压成一条命令
- 机械和校准步骤仍然是互动式的

## 手动命令速查

### 舵机

```bash
uv run lerobot-find-port
uv run -m lelamp.setup_motors --id lelamp --port /dev/ttyACM0
uv run -m lelamp.calibrate --id lelamp --port /dev/ttyACM0
uv run -m lelamp.test.test_motors --id lelamp --port /dev/ttyACM0
```

### 音频与灯光

```bash
uv run -m lelamp.test.test_audio
sudo uv run -m lelamp.test.test_rgb
```

### 语音 Agent

```bash
uv run smooth_animation.py download-files
uv run smooth_animation.py console
```

### OpenClaw

```bash
openclaw onboard --install-daemon
openclaw doctor
openclaw status
```
