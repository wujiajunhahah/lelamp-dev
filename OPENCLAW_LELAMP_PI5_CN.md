# OpenClaw + LeLamp Pi 5 集成方案

这份方案是给 `Pi 5` 用的，目标不是把 OpenClaw 硬说成万能控制器，而是把它正确地放在 `LeLamp` 上面，当一个远程控制和消息入口层。

## 先说结论

OpenClaw 适合你要的这几件事：

- 用手机发消息控制 LeLamp
- 远程触发动作、灯光和简单检查
- 从外网安全连回 Pi 上的 OpenClaw dashboard

OpenClaw 不适合拿来做这件事：

- 毫秒级摇杆遥操作
- 真正的实时视频流 teleop

如果你以后要做“像遥控车一样”的低延迟控制和实时视频，那要单独再做 WebRTC 或网页控制层。OpenClaw 更像“会执行命令的远程 agent”。

## 官方在树莓派上的几种部署路子

OpenClaw 官方当前文档里，树莓派上常见的是这几类：

1. 官方安装脚本
   `curl -fsSL https://openclaw.ai/install.sh | bash`
   这是官方推荐的最快路径，适合单台 `Pi 5`。
2. 本地前缀安装
   `install-cli.sh`
   适合你不想碰系统 Node，想把东西都收进 `~/.openclaw`。
3. `npm` / `pnpm` 全局安装
   适合你已经自己管 Node 环境。
4. Docker / Podman / Nix / Ansible
   更适合容器化、批量化或者你本来就有现成运维体系。
5. 从源码构建
   适合开发 OpenClaw 本体，不适合你现在这台 LeLamp 控制机首发。

对你这台 `Pi 5 + LeLamp`，我推荐的是：

- OpenClaw 本体用官方安装脚本
- 远控入口先接 Telegram
- dashboard 远程访问走 Tailscale
- LeLamp 控制走我给你准备的 `lelamp.remote_control`

这是最稳、最少折腾、也最容易后续维护的组合。

## 我推荐的 Pi 5 架构

1. `LeLamp Runtime`
   直接负责舵机、LED、音频和语音 agent。
   当前默认模型路径已经切到 `Qwen Omni Realtime`：
   `MODEL_PROVIDER=qwen`
   `MODEL_BASE_URL=https://dashscope.aliyuncs.com/api-ws/v1/realtime`
   `MODEL_NAME=qwen3.5-omni-plus-realtime`
   `MODEL_VOICE=Tina`
2. `OpenClaw`
   负责消息入口、远程访问和手机控制。
3. `Telegram`
   作为最轻量的手机入口。
4. `Tailscale`
   作为 dashboard 的安全远程通道。

## 我已经给你准备好的 OpenClaw 接口

- `uv run -m lelamp.remote_control show-config`
- `uv run -m lelamp.remote_control list-recordings`
- `uv run -m lelamp.remote_control play <recording>`
- `uv run -m lelamp.remote_control solid <r> <g> <b>`
- `uv run -m lelamp.remote_control clear`

这层接口是专门给 OpenClaw 调的，避免它直接乱碰 `setup_motors` 或 `calibrate`。

## 先确认 runtime 已经拉下来

`lelamp_runtime/` 现在按顶层仓库里的 submodule 管理。

首次 clone 顶层仓库时，使用：

```bash
git clone --recurse-submodules <你的 Lelamp 仓库 URL> Lelamp
cd Lelamp
```

如果你已经有旧 checkout、旧 worktree，或者只拉过顶层仓库：

```bash
git submodule update --init --recursive
```

如果你按本文默认零接触脚本部署在 Pi 上，下面这些命令里的 `/path/to/Lelamp/lelamp_runtime` 通常可以替换成 `~/lelamp-dev/lelamp_runtime`。

## 一次性安装顺序

1. 先完成 LeLamp 基础 bring-up

```bash
cd /path/to/Lelamp/lelamp_runtime
chmod +x scripts/pi_setup_max.sh
./scripts/pi_setup_max.sh
```

2. 再装 OpenClaw

```bash
cd /path/to/Lelamp/lelamp_runtime
chmod +x scripts/openclaw_pi5_setup.sh
./scripts/openclaw_pi5_setup.sh
```

3. 跑 OpenClaw onboarding

```bash
openclaw onboard --install-daemon
```

4. 安装 LeLamp skill

```bash
cd /path/to/Lelamp/lelamp_runtime
chmod +x scripts/install_openclaw_skill.sh
./scripts/install_openclaw_skill.sh
```

## 我建议你 onboarding 时怎么选

1. 模式先选 `Local`
2. 模型优先接 `GLM Coding Plan` 路线
   推荐把 OpenClaw 侧单独配成：
   provider: `Z.AI / GLM`
   model: `glm-5` 或 `glm-4.7`
   base URL: `https://open.bigmodel.cn/api/coding/paas/v4`
3. 把 API keys 配好
4. 远程入口先加 `Telegram`
5. 如果你要从外网看 dashboard，再配 `Tailscale`

注意分层：

- `LeLamp Runtime` 这层默认用 `GLM Realtime`
- `OpenClaw` 这层更适合走智谱官方给 OpenClaw 准备的 `Coding Plan` 路线

两层不是同一个 endpoint，也不应该共用同一套默认参数

## 远程访问也有几条官方路子

1. 本地 dashboard + SSH 隧道
   最简单，最保守。
2. Tailscale Serve
   只给 tailnet 内设备访问，我最推荐。
3. Tailscale Funnel
   可以公开上网，但风险更高，必须额外设密码。

对你这台 LeLamp，我建议默认 `Tailscale Serve`，不要先上 Funnel。

## 手机上怎么用

最简单的路线是 Telegram 给 OpenClaw 发命令，比如：

- `list lamp recordings`
- `play curious`
- `set lamp to warm orange`
- `clear lamp LEDs`

OpenClaw 通过我给你准备的 `lelamp_control` skill，把这些高层命令翻译成 `uv run -m lelamp.remote_control ...`

## 我建议你不要让 OpenClaw 直接做的事

- 第一次配置舵机 ID
- 首次校准
- 长时间连续动作录制
- 一边语音 agent 在跑，一边反复抢占舵机

这些步骤都更适合你 SSH 上去手动做，等基础系统稳定后，再把 OpenClaw 放上来接管“远程触发”。

## 到货当天的推荐顺序

1. 先把 Pi 5、电源、ReSpeaker、串口、舵机全部跑通
2. 手动验证 `lelamp.remote_control` 五个命令
3. 再装 OpenClaw
4. 再装 skill
5. 最后才从手机端发第一条控制命令

## 到时候你给我这些信息，我就能继续收口

- `openclaw --version`
- `openclaw doctor` 的输出
- `uv run -m lelamp.remote_control show-config`
- `uv run -m lelamp.remote_control list-recordings`
- `aplay -l`
- `ls /dev/ttyACM*`

这样我就能继续把 OpenClaw 侧也帮你收成可长期用的远控方案。
