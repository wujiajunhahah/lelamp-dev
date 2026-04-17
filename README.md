# LeLamp Pi 5 Bring-Up Workspace

这个工作区已经不是原始的上游仓库镜像了，而是按你现在的目标收成了一套 `Pi 5 + LeLamp + OpenClaw` 的落地环境。

目标很明确：

- 你的树莓派到手后尽量只跑一条命令
- 如果还是空白卡，先在宿主机上一条命令种好 bootfs
- 自动判断当前设备是不是 `Pi 5`
- 自动走最安全的 `ReSpeaker` 配置路径
- 自动准备 `LeLamp Runtime`
- 自动准备 `OpenClaw`
- 自动准备 `systemd` 服务和重启后的收尾检查

## 获取仓库

`lelamp_runtime/` 现在按 submodule 管理，不再是假定你本地另外放着一份独立 runtime。

首次 clone 顶层仓库时，使用：

```bash
git clone --recurse-submodules <你的 Lelamp 仓库 URL> Lelamp
cd Lelamp
```

如果你已经有旧 checkout、旧 worktree，或者之前只拉了顶层仓库但没初始化 runtime，先执行：

```bash
git submodule update --init --recursive
```

如果你按本文默认零接触脚本部署到 Pi，顶层仓库默认会落在 `~/lelamp-dev`，运行时目录就是 `~/lelamp-dev/lelamp_runtime`。

## GitHub Pages

仓库包含一个纯静态的 GitHub Pages 站点，源文件在 `site/`，部署工作流在 `.github/workflows/pages.yml`。

Pages 的职责是：

- 对外快速解释这套仓库到底做了什么
- 给到一键安装入口
- 给到开发和维护入口

如果仓库开启了 Pages，默认页面就是 `site/index.html`。

## 自动检测与缺失项审计

这个仓库现在已经补了一个 `doctor` 脚本，用来自动检测：

- 缺了什么命令
- 已经安装了什么
- `.env` 里哪些 `MODEL_*` / `LIVEKIT_*` 关键项已经有了
- 音频设备、串口设备是否出现
- `systemd` 服务是否安装 / 启用
- OpenClaw skill 是否在位

运行：

```bash
cd /path/to/Lelamp/lelamp_runtime
./scripts/lelamp_doctor.sh
```

## 你的当前硬件画像

详细清单见 [HARDWARE_PROFILE_PI5.md](./HARDWARE_PROFILE_PI5.md)。

当前默认假设是：

- `Raspberry Pi 5`
- `Raspberry Pi OS Lite 64-bit`
- `ReSpeaker 2-Mics Pi HAT V2.0`
- `8x5 WS2812B Matrix`
- `5x STS3215`
- `TTL servo driver`
- `Pi Camera`
- `speaker + microphone`
- `LeLamp 3D prints`

当前默认软件模型路径也已经收成：

- `MODEL_PROVIDER=qwen`
- `MODEL_BASE_URL=https://dashscope.aliyuncs.com/api-ws/v1/realtime`
- `MODEL_NAME=qwen3.5-omni-plus-realtime`
- `MODEL_VOICE=Tina`
- `MODEL_API_KEY=<your DashScope key>`

重要修正：

- `Pi 5` 主供电必须按 `5V / 5A USB-C` 处理
- TNKR / BOM 里的 `5V / 2A` 不能当 `Pi 5` 主供电

## 两段式极简入口

### Stage-0: 空白卡 bootfs 种子

如果你的 Pi 5 还没装完系统，现在已经不是只给说明，而是补了一个真正可执行的宿主机脚本：

```bash
cp host_tools/pi5_zero_touch.env.example .pi5_zero_touch.env
$EDITOR .pi5_zero_touch.env
set -a
source ./.pi5_zero_touch.env
set +a
./host_tools/pi5_zero_touch_seed.sh --bootfs "$BOOTFS_PATH" --password "$BOOTSTRAP_PASSWORD"
```

它会把这些首启关键件直接写进已经刷好官方 Raspberry Pi OS 的 boot 分区：

- `userconf.txt`
- `ssh`
- `firstrun.sh`
- `lelamp-bootstrap.env`
- 可选 `authorized_keys`

Pi 首次启动以后会自己：

1. 创建用户
2. 开 SSH
3. 写 hostname
4. 可选写 Wi-Fi
5. 用多目标回退策略等网络就绪，不只盯 `github.com`
6. 安装 `lelamp-bootstrap.service`
7. 克隆顶层 bring-up 仓库并初始化 `lelamp_runtime` submodule
8. 自动执行 `lelamp_runtime/scripts/pi5_all_in_one.sh`

### Stage-1: Pi 上总控入口

如果系统已经起来，或者你要手工重跑 bring-up，进入 [`lelamp_runtime`](./lelamp_runtime/) 执行：

```bash
cd /path/to/Lelamp/lelamp_runtime
chmod +x scripts/pi5_all_in_one.sh
./scripts/pi5_all_in_one.sh
```

如果你想全程尽量不交互，也可以提前把变量带进去：

```bash
cd /path/to/Lelamp/lelamp_runtime
AUTO_ACCEPT_DEFAULTS=1 \
AUTO_REBOOT=1 \
LAMP_ID=lelamp \
LAMP_PORT=/dev/ttyACM0 \
MODEL_PROVIDER=qwen \
MODEL_API_KEY=your_dashscope_key \
MODEL_BASE_URL=https://dashscope.aliyuncs.com/api-ws/v1/realtime \
MODEL_NAME=qwen3.5-omni-plus-realtime \
MODEL_VOICE=Tina \
RESPEAKER_VARIANT=auto \
INSTALL_OPENCLAW=1 \
OPENCLAW_INSTALL_MODE=standard \
./scripts/pi5_all_in_one.sh
```

## 这条命令会做什么

总控脚本 [pi5_all_in_one.sh](./lelamp_runtime/scripts/pi5_all_in_one.sh) 会：

1. 检测 `Pi 型号 / OS / 架构`
2. 检测你是不是在 `Pi 5` 路线
3. 自动判断已有 `.env`、`/dev/ttyACM*`、已装 service、已装 OpenClaw
4. 写入 `.env`，统一使用 `MODEL_*` + `LIVEKIT_*` 配置
5. 调用 [pi_setup_max.sh](./lelamp_runtime/scripts/pi_setup_max.sh) 配好 LeLamp runtime
6. 按安全策略处理 `ReSpeaker`
7. 安装可选的 `LeLamp` 开机服务
8. 调用 [openclaw_pi5_setup.sh](./lelamp_runtime/scripts/openclaw_pi5_setup.sh) 安装 OpenClaw
9. 安装 LeLamp 的 OpenClaw skill
10. 安装一个重启后自动收尾的 one-shot service
11. 跑一遍 `doctor` 快照
12. 在重启后自动生成一份设备状态报告

## 自动适配策略

### Pi 版本

- 默认只为 `Pi 5` 收口
- 如果不是 `Pi 5`，脚本会拦住
- 如果你真的要在别的板子上试，显式传 `ALLOW_NON_PI5=1`

### ReSpeaker 版本

- `RESPEAKER_VARIANT=auto`
  默认当成 `V2.0`
- `RESPEAKER_VARIANT=v2`
  直接走安全的 `V2.0` 路线
- `RESPEAKER_VARIANT=v1`
  在 `Pi 5 + Bookworm/Trixie` 上默认拒绝自动配置
- `RESPEAKER_VARIANT=skip`
  完全跳过音频 HAT 配置

这不是保守，是为了避免你在不受支持的 `WM8960 / V1` 路线上踩坑。

## 当前已经准备好的关键文件

- 空白卡种子脚本: [host_tools/pi5_zero_touch_seed.sh](./host_tools/pi5_zero_touch_seed.sh)
- 空白卡环境模板: [host_tools/pi5_zero_touch.env.example](./host_tools/pi5_zero_touch.env.example)
- 总控入口: [lelamp_runtime/scripts/pi5_all_in_one.sh](./lelamp_runtime/scripts/pi5_all_in_one.sh)
- LeLamp Pi 配置: [lelamp_runtime/scripts/pi_setup_max.sh](./lelamp_runtime/scripts/pi_setup_max.sh)
- 重启后自动收尾: [lelamp_runtime/scripts/pi5_post_reboot_finalize.sh](./lelamp_runtime/scripts/pi5_post_reboot_finalize.sh)
- OpenClaw 安装: [lelamp_runtime/scripts/openclaw_pi5_setup.sh](./lelamp_runtime/scripts/openclaw_pi5_setup.sh)
- OpenClaw skill 安装: [lelamp_runtime/scripts/install_openclaw_skill.sh](./lelamp_runtime/scripts/install_openclaw_skill.sh)
- OpenClaw 技能: [lelamp_runtime/openclaw/skills/lelamp-control/SKILL.md](./lelamp_runtime/openclaw/skills/lelamp-control/SKILL.md)
- 环境变量模板: [lelamp_runtime/.env.example](./lelamp_runtime/.env.example)
- Pi 5 总说明: [LELAMP_PI5_BRINGUP_CN.md](./LELAMP_PI5_BRINGUP_CN.md)
- OpenClaw 总说明: [OPENCLAW_LELAMP_PI5_CN.md](./OPENCLAW_LELAMP_PI5_CN.md)
- 开发维护文档: [DEVELOPMENT_GUIDE_PI5.md](./DEVELOPMENT_GUIDE_PI5.md)
- Pages 主页: [site/index.html](./site/index.html)
- Pages 开发页: [site/developer.html](./site/developer.html)
- Pages 工作流: [.github/workflows/pages.yml](./.github/workflows/pages.yml)
- Pre-OS 说明: [PRE_OS_BOOTSTRAP_CN.md](./PRE_OS_BOOTSTRAP_CN.md)
- macOS 预检查脚本: [host_tools/pi5_preos_check_macos.sh](./host_tools/pi5_preos_check_macos.sh)
- 环境审计脚本: [lelamp_runtime/scripts/lelamp_doctor.sh](./lelamp_runtime/scripts/lelamp_doctor.sh)

## 重启后看哪里

重启以后，自动收尾脚本会生成：

- `lelamp_runtime/POST_BOOT_REPORT.md`

这份报告会收集：

- `aplay -l`
- `arecord -l`
- `/dev/ttyACM*`
- `download-files` 结果
- `OpenClaw` 状态检查

## 仍然必须手动做的事情

下面这些东西没有任何脚本能替你真自动完成：

- 实物组装
- 舵机接线
- 首次舵机 ID 配置
- 首次校准时的人手摆位
- 确认你拿到的 `ReSpeaker` 到底是 `V1` 还是 `V2.0`

所以这套方案的定义不是“把物理世界变没”，而是“把软件和系统配置压缩成一条安全路径”。

## 如果 Pi 还没装系统

这件事也已经收口成正式策略了，但要说清楚边界：

- **系统启动后**，本仓库可以尽量做到一条命令 bring-up
- **系统启动前**，不能靠一块完全没 OS 的 Pi 自己运行脚本
- **系统启动前的宿主机阶段**，现在已经可以通过 `host_tools/pi5_zero_touch_seed.sh` 直接把首启自举链种好

当前支持的前置路线：

1. 用另一台电脑通过官方 Raspberry Pi Imager 写卡并预配置 SSH / Wi-Fi / 用户
2. 用 Pi 5 官方 Network Install

详细说明见 [PRE_OS_BOOTSTRAP_CN.md](./PRE_OS_BOOTSTRAP_CN.md)。

## 到货后推荐顺序

1. 如果还是空白卡，先跑 `./host_tools/pi5_zero_touch_seed.sh`
2. Pi 首启后让 `lelamp-bootstrap.service` 自动收尾
3. 看 `POST_BOOT_REPORT.md`
4. 看 `./scripts/lelamp_doctor.sh`
5. 确认音频设备和串口设备正常
6. 再做舵机 ID 配置和校准
7. 再启用语音 agent
8. 最后再让 OpenClaw 从手机入口接管高层控制

## 上游参考

- LeLamp 文档与硬件: https://tnkr.ai/explore/docs/human-computer-lab/lelamp-v1
- LeLamp Runtime 上游: https://github.com/humancomputerlab/lelamp_runtime
- OpenClaw 文档: https://docs.openclaw.ai/
