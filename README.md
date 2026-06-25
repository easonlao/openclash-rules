# openclash-config-tools

这是一个自用 OpenClash / Mihomo 配置仓库，维护两份配置：

| 文件 | 使用场景 |
|---|---|
| `config_local.yaml` | 家里软路由 / OpenClash 使用 |
| `config_simple_mobile.yaml` | 手机 Clash Meta / Clash Mi 简化版，带“回家”能力 |

当前目标很简单：**稳定可用、出口可控、少折腾**。默认不追求大而全模板，也不默认加载低频规则。

## 当前状态

- 家用版已完成实机收口：`DNS` 不泄露，`Claude` 和 `ChatGPT` 已测试可用。
- 手机版已收敛为 simple 基线，只保留“回家”能力，不再维护手机完整版。
- 两份发布 YAML 都不内置 DNS 细节；DNS / fake-ip / nameserver 交给 OpenClash 或 ClashMi 的覆写页面处理。
- 后续任何改动，都应先保证这些结果不回退。

## 配置职责边界

| 内容 | 放哪里 |
|---|---|
| 节点、策略组、规则引用 | `config_local.yaml` / `config_simple_mobile.yaml` |
| DNS、fake-ip、nameserver、监听地址 | OpenClash / ClashMi 覆写页面 |
| 个性化强制代理 | `list/Proxy.list` |
| 个性化强制直连 | `list/Direct.list` |

`no-resolve` 继续用于 IP 规则，避免为了匹配 IP 规则额外解析域名；但它不是单独的 DNS 防泄露方案。DNS 是否符合预期仍看最终运行态和测试结果。

## 使用前需要改哪里

### 1. 填机场订阅

两个配置都要填：

```yaml
proxy-providers:
  聚合机场:
    url: "https://你的机场订阅链接"
```

### 2. 填住宅 SOCKS5 节点

两个配置都要填。住宅节点是一个固定出口，不是订阅链接。

```yaml
proxies:
  - name: 住宅-socks5
    type: socks5
    server: "你的住宅IP地址"
    port: 12345
    username: "你的用户名"
    password: "你的密码"
    dialer-proxy: 住宅中继组
```

### 3. 手机版额外填回家密码

只改 `config_simple_mobile.yaml`：

```yaml
proxies:
  - name: 回家
    password: "你的SS密码"
```

`回家` 用来从手机外网访问家里服务，例如路由器面板、NAS、内网应用，也可以作为手机日常默认出口。它默认放在 `通用选择` 的第一项。

## 日常怎么用

### 家用版

导入 `config_local.yaml` 到 OpenClash。

日常只需要关注一个策略组：

| 策略组 | 用途 |
|---|---|
| `通用选择` | 默认出口，总开关 |

建议默认选择 `新加坡` 或其他你长期稳定使用的地区，不要频繁切换。

### 手机版

导入 `config_simple_mobile.yaml` 到手机 Clash 客户端。

日常只需要关注一个策略组：

| 策略组 | 用途 |
|---|---|
| `通用选择` | 手机总开关；默认第一项是 `回家` |

默认保持 `通用选择 = 回家`，这样人在外面也可以访问 NAS / 路由器面板 / 家里内网服务，并通过家里网络继续上网。

如果家里线路不可用，或者临时需要切机场，只改 `通用选择`：

| 场景 | 操作 |
|---|---|
| 日常外出，访问 NAS + 正常翻墙 | `通用选择 = 回家` |
| 家里掉线 / 回家不可用 | `通用选择 = 新加坡 / 香港 / 全部` |
| 需要住宅出口 | `通用选择 = 住宅-socks5` |
| 某个业务临时特殊出口 | 只改对应业务策略组 |

## 出口使用建议

- AI 服务尽量长期使用同一个出口，不要频繁换地区。
- 住宅 SOCKS5 只在确实需要固定住宅出口时使用。
- 不要把默认出口设成频繁自动测速切换的策略。
- 如果某个网站对 IP 敏感，先固定一个能用的节点，再长期保持。

## 不要做的事

- 不要把住宅节点写成 `proxy-provider` 订阅。
- 不要把所有业务都切到自动测速组。
- 不要频繁在 AI / 金融 / 风控敏感网站之间切出口。
- 不要把真实订阅链接、住宅账号密码、回家密码提交到公开仓库。
- 不要直接在主路由上试错 reload；先本地验证，再上线。

## 基础语法检查

这个发布目录默认不再内置项目维护脚本。

修改配置后，至少先用本地 Mihomo / Clash Meta 核心做一次 `-t` 检查，确认 YAML 可以被核心加载；运行态效果仍需再做隔离验证和 `Net.Coffee` 复验。

如果你在维护项目本身，还可以运行项目级工具目录里的两个脚本：

```bash
python3 tools/validate_config.py
python3 tools/validate_openclash_wiki.py
```

## 上线前建议

影响家里主网络的改动，建议按这个顺序：

1. 先用本地 Mihomo / Clash Meta 核心执行 `-t`。
2. 在隔离环境或备用环境确认配置能启动。
3. 再导入 OpenClash / 手机客户端。
4. 通过 OpenClash / ClashMi 覆写页面设置 DNS / fake-ip 等运行态选项。
5. 上线后重新检查 IP、DNS、WebRTC 是否符合预期。

可用的在线检查入口：

- `https://ip.net.coffee/`

## 低频能力

广告拦截、游戏平台、加密货币、英伟达、Amazon、测试规则等低频能力不再默认维护独立扩展文件。

如果后续确实要用，直接按需补回主配置，不长期保留一份“也许以后会用”的扩展模板。

## 规则来源

主要使用：

- MetaCubeX `meta-rules-dat`
- blackmatrix7 `ios_rule_script`
- 本仓库少量自维护补丁规则

原则：能用公开规则源就不自维护；只有公开规则缺口明确、且当前确实需要时，才保留本地补丁规则。

## 文件说明

| 路径 | 说明 |
|---|---|
| `config_local.yaml` | 家用 OpenClash 配置 |
| `config_simple_mobile.yaml` | 手机 Clash 简化版配置 |
| `list/` | 当前配置直接引用的少量本地补丁规则 |

## 安全提醒

这个仓库里的配置应保持占位符。真实连接信息只应保存在你自己的私密位置，不要提交到 Git 历史。
