# LeLamp Runtime for Pi 5

这个目录已经按 `Pi 5 + LeLamp + OpenClaw` 做过本地增强，不是上游原样。

仓库级说明、Pages 入口和开发文档在上一级目录：

- `../README.md`
- `../DEVELOPMENT_GUIDE_PI5.md`
- `../site/index.html`

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
  处理 LeLamp runtime、依赖、音频 overlay、`ws2812-pio` LED overlay 持久化、可选 systemd 服务。
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
MODEL_PROVIDER=glm
MODEL_API_KEY=
MODEL_BASE_URL=https://open.bigmodel.cn/api/paas/v4
MODEL_NAME=glm-realtime
MODEL_VOICE=tongtong
LIVEKIT_URL=
LIVEKIT_API_KEY=
LIVEKIT_API_SECRET=
LELAMP_ID=lelamp
LELAMP_PORT=/dev/ttyACM0
LELAMP_AUDIO_USER=pi
LELAMP_LED_COUNT=40
LELAMP_ENABLE_RGB=true
```

说明：

- `MODEL_*` 是当前仓库的标准配置
- `MODEL_PROVIDER=glm` 是默认路径
- `ZAI_API_KEY` 和 `OPENAI_API_KEY` 仍然保留兼容回退，但不再是主配置键
- `LELAMP_ENABLE_RGB=false` 可以临时关闭 LED 路径，隔离音频、动作和语音问题

## Pi 5 LED 路径

Pi 5 上默认走官方 `ws2812-pio` 驱动，不走 `rpi_ws281x` DMA 路径。

`scripts/pi_setup_max.sh` 会把下面这行持久化到 `/boot/firmware/config.txt`：

```bash
dtoverlay=ws2812-pio,gpio=12,num_leds=40
```

重启以后应当满足：

```bash
ls -l /dev/leds0
sudo uv run -m lelamp.remote_control solid 255 160 32
```

如果你改了灯板数量或信号脚，安装时覆盖：

```bash
LED_PIN=12 LED_COUNT=40 ./scripts/pi_setup_max.sh
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

## Local Dashboard

本地状态面板现在和 runtime 一起内置在仓库里，适合：

- 树莓派本机屏幕全屏演示
- 同一局域网里的手机或电脑访问
- 手机热点或树莓派热点环境下的本地控制

启动：

```bash
uv run -m lelamp.dashboard.api
```

默认监听：

```bash
LELAMP_DASHBOARD_HOST=0.0.0.0
LELAMP_DASHBOARD_PORT=8765
LELAMP_DASHBOARD_POLL_MS=400
```

打开方式：

- 树莓派本机：`http://127.0.0.1:8765`
- 同网设备：看面板 `现场信息` 里的可访问地址
- 当前树莓派也会自动把局域网地址写进 `reachable_urls`

面板能力：

- 查看 system / motion / light / audio 的实时状态
- 触发 `startup`、`play`、`stop`、`shutdown_pose`
- 切到暖琥珀灯光或清灯
- 看当前可用 recordings、最近错误和可访问 URL

当前界面已经做过一轮演示向收口：

- 主界面默认中文
- 手机端优先显示当前状态
- 未接台灯时仍然诚实显示 `motion.status=error`

## Sync 到树莓派

如果你在 Mac 上改完了 `lelamp_runtime`，推荐用仓库自带脚本同步到树莓派，不要手工拷文件：

```bash
./scripts/sync_pi_runtime.sh
```

常用方式：

```bash
START_DASHBOARD=1 ./scripts/sync_pi_runtime.sh
```

这会做四件事：

- `rsync` 当前 runtime 到树莓派上的 `~/lelamp-dev/lelamp_runtime`
- 保留树莓派自己的 `.env` 和 `.venv`
- 在树莓派上跑 dashboard smoke tests
- 安全重启本地 dashboard 服务

现在这条脚本不再写死单个 IP，而是：

```bash
先找本地局域网目标，再在需要时回退到 Tailscale
```

默认探测顺序是：

```bash
wujiajun@lelamp.local
wujiajun@raspberrypi.local
wujiajun@172.20.10.2
```

如果你想覆盖本地探测目标，或者加上你现场热点 / 校园网下常见的地址：

```bash
export LELAMP_PI_LOCAL_CANDIDATES="wujiajun@lelamp.local,wujiajun@raspberrypi.local,wujiajun@192.168.31.42"
```

如果你已经给树莓派配了 Tailscale，也可以给同步脚本一个远程兜底：

```bash
export LELAMP_PI_TAILSCALE_NAME="lelamp-pi5"
```

或者直接写 Tailnet IP / 完整 SSH 目标：

```bash
export LELAMP_PI_TAILSCALE_HOST="wujiajun@100.x.y.z"
```

显式指定目标仍然可用：

```bash
./scripts/sync_pi_runtime.sh your-user@your-pi-ip /home/your-user/lelamp-dev
```

如果你只想强制指定一个目标，不让脚本探测：

```bash
export LELAMP_PI_HOST="wujiajun@100.x.y.z"
./scripts/sync_pi_runtime.sh
```

可用环境变量：

```bash
LELAMP_PI_USER
LELAMP_PI_HOST
LELAMP_PI_LOCAL_CANDIDATES
LELAMP_PI_TAILSCALE_NAME
LELAMP_PI_TAILSCALE_HOST
LELAMP_PI_SSH_TIMEOUT
```

## Tailscale 无头兜底

如果你不想每次都和树莓派在同一个局域网，推荐把 `Tailscale` 配成无头常驻。

首次在开发机上执行：

```bash
export LELAMP_PI_LOCAL_CANDIDATES="wujiajun@lelamp.local,wujiajun@raspberrypi.local"
export TAILSCALE_AUTH_KEY="tskey-xxxx"
export TAILSCALE_HOSTNAME="lelamp-pi5"
./scripts/setup_tailscale_remote.sh
```

这条脚本会在树莓派上：

- 安装 `tailscale`
- `enable + start tailscaled`
- 如果你提供了 `TAILSCALE_AUTH_KEY`，直接完成首次 `tailscale up --ssh`

配置好以后，树莓派只要重新连上网络，`tailscaled` 就会自动上线，不需要你再接键盘和显示器。

如果你不想在首次配置时传 auth key，也可以先只安装：

```bash
./scripts/setup_tailscale_remote.sh
```

然后未来有机会登录树莓派时手动补一次：

```bash
sudo tailscale up --ssh --hostname lelamp-pi5
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
sudo uv run -m lelamp.remote_control solid 255 160 32
sudo uv run -m lelamp.remote_control clear
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
