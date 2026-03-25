# Pi 5 还没装系统时怎么办

结论先说清楚：

## 可以做到的部分

现在已经可以把“从零到可 SSH 登录、可继续跑 LeLamp 一键脚本”的流程做成真正可执行的半自动链路。

## 不能做到的部分

如果树莓派完全还没有系统，那么 **不可能靠树莓派自己运行仓库里的脚本来安装系统**。  
原因很简单：没有 OS，就没有 shell、没有 Python、没有 `bash`，也没有地方执行这些脚本。

所以这件事必须分成两个阶段：

1. **Pre-OS 阶段**
   在另一台电脑上准备启动介质，或者用 Pi 5 官方 `Network Install`。
2. **Post-OS 阶段**
   系统第一次可启动以后，再运行本仓库的一键安装器。

## 仓库现在新增的直接解法

新增脚本：

- `host_tools/pi5_zero_touch_seed.sh`
- `host_tools/pi5_zero_touch.env.example`

它的职责不是替代官方刷机，而是把刷完卡之后最容易漏掉的第一启动配置直接种进去：

- 建用户
- 开 SSH
- 写 hostname
- 可选写 Wi-Fi
- 安装 `lelamp-bootstrap.service`
- 首启自动克隆 `lelamp-dev`
- 首启自动执行 `lelamp_runtime/scripts/pi5_all_in_one.sh`

最短用法：

```bash
cp host_tools/pi5_zero_touch.env.example .pi5_zero_touch.env
$EDITOR .pi5_zero_touch.env
set -a
source ./.pi5_zero_touch.env
set +a
./host_tools/pi5_zero_touch_seed.sh --bootfs "$BOOTFS_PATH" --password "$BOOTSTRAP_PASSWORD"
```

## 官方认可的两条路

### 路线 A：另一台电脑 + Raspberry Pi Imager

这是我最推荐的路线。

官方文档说明，Raspberry Pi Imager 可以在写卡时预配置：

- hostname
- username / password
- Wi-Fi
- SSH
- localisation

这意味着你可以有两种做法：

1. 直接在 Imager 里填 SSH / Wi-Fi / 用户，然后开机后手动跑 `pi5_all_in_one.sh`
2. 先刷卡，再用 `pi5_zero_touch_seed.sh` 给 bootfs 打种子，让 Pi 首启后自己拉仓库并自动跑 installer

### 路线 B：Pi 5 自己走 Network Install

Raspberry Pi 官方也支持 `Network Install`。

这条路适合：

- 你手边没有 SD 读卡器
- 但你有显示器、键盘和有线网络

官方要求是：

- 兼容的树莓派型号
- 支持 Network Install 的 bootloader
- 显示器
- 键盘
- 有线网络

## 这个仓库现在提供了什么

为了把 Pre-OS 阶段也收进来，我补了两个宿主机脚本：

- `host_tools/pi5_preos_check_macos.sh`
- `host_tools/pi5_zero_touch_seed.sh`

它不会做危险的强制写盘，但会帮你检查：

- 你是不是在 macOS
- Raspberry Pi Imager 是否已安装
- 当前外接磁盘情况
- 你之后应该填哪些 OS customisation 项

而 `host_tools/pi5_zero_touch_seed.sh` 会在“卡已经刷好并挂载以后”完成真正的首启自举配置。

## 推荐的极致保险流程

### 第 0 阶段：在你的 Mac 上

1. 安装 Raspberry Pi Imager
2. 运行：

```bash
./host_tools/pi5_preos_check_macos.sh
```

3. 按脚本输出准备：
   - hostname
   - username
   - password
   - Wi-Fi
   - 启用 SSH

### 第 1 阶段：把 Raspberry Pi OS 写到卡里

推荐直接用官方 Imager，原因是它对 Pi 5、镜像、用户配置、SSH 这些事情是官方支持路径。

写卡完成并挂载 boot 分区以后，继续执行：

```bash
cp host_tools/pi5_zero_touch.env.example .pi5_zero_touch.env
$EDITOR .pi5_zero_touch.env
set -a
source ./.pi5_zero_touch.env
set +a
./host_tools/pi5_zero_touch_seed.sh --bootfs "$BOOTFS_PATH" --password "$BOOTSTRAP_PASSWORD"
```

### 第 2 阶段：Pi 第一次启动

如果你已经跑过 `pi5_zero_touch_seed.sh`，这一阶段默认不再需要你手工 SSH 进去跑 installer。

Pi 会自己：

1. 执行 `firstrun.sh`
2. 安装 `lelamp-bootstrap.service`
3. 克隆 `wujiajunhahah/lelamp-dev`
4. 自动运行 `lelamp_runtime/scripts/pi5_all_in_one.sh`

### 第 3 阶段：重启后检查

重启后看：

- `POST_BOOT_REPORT.md`
- `./scripts/lelamp_doctor.sh`

## 如果你问“能不能做到真正一条龙”

答案是：

- **刷系统之前**，不能靠裸 Pi 自己完成。
- **刷系统之后、第一次启动之前**，现在已经可以用宿主机脚本把首启自动化。
- **系统启动以后**，仍然保留 `pi5_all_in_one.sh` 作为单独可运行的总入口。

所以最现实的目标是：

- **Pre-OS**：官方 Imager / Network Install + 本仓库的 bootfs 种子脚本
- **Post-OS**：本仓库一键 bring-up
