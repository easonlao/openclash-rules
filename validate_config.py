#!/usr/bin/env python3
"""
OpenClash 配置文件发布前验证脚本
检测配置文件的语法、引用、URL、锚点格式等问题。
任何 ERROR 级别问题都会阻止发布（exit 1）。

格式规则：
- .mrs 文件（二进制）+ behavior=domain  → format=mrs, *domain 锚点
- .mrs 文件（二进制）+ behavior=ipcidr  → format=mrs, *ip 锚点
- .list 文件（纯文本）+ behavior=classical → format=text, *class 锚点
"""

import yaml
import requests
import sys
import re
import argparse
from pathlib import Path
from urllib.parse import urlparse

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')


def load_config(filename):
    """加载并解析 YAML 配置文件，同时返回原始文本用于重复键检查"""
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            raw_text = f.read()
        return yaml.safe_load(raw_text), None, raw_text
    except yaml.YAMLError as e:
        return None, str(e), ""


def extract_rule_refs(rules):
    """从 rules 列表中提取所有 RULE-SET 引用名"""
    refs = set()
    for rule in rules:
        if isinstance(rule, str) and 'RULE-SET,' in rule:
            parts = rule.split(',')
            if len(parts) >= 2:
                refs.add(parts[1].strip())
    return refs


def check_yaml_syntax(config, errors):
    """检查 1: YAML 语法"""
    if config is None:
        errors.append("YAML 语法错误")
        return False
    return True


def check_required_fields(config, errors):
    """检查 2: 必需的顶级字段"""
    required = ['mixed-port', 'allow-lan', 'mode', 'dns', 'proxies',
                'proxy-providers', 'proxy-groups', 'rule-providers', 'rules']
    for field in required:
        if field not in config:
            errors.append(f"缺失顶级字段: {field}")


def check_duplicate_providers(config, errors):
    """检查 3: 重复的规则集名称"""
    providers = config.get('rule-providers', {})
    names = list(providers.keys())
    dupes = {n for n in names if names.count(n) > 1}
    for d in sorted(dupes):
        errors.append(f"重复规则集名称: {d}")


def check_group_order(config, warnings):
    """检查 4: 策略组引用顺序警告（被引用的组建议先定义，方便阅读）
    注意：Mihomo 内核本身不要求定义顺序，会自动解析所有依赖。
    本检查仅为提高配置文件可读性的警告，不阻止发布。
    """
    groups = config.get('proxy-groups', [])
    group_names = [g['name'] for g in groups]
    for i, g in enumerate(groups):
        for ref in g.get('proxies', []):
            if ref in ['直连', '拒绝', 'DIRECT', 'REJECT', '住宅-socks5', '回家']:
                continue
            if ref in group_names and group_names.index(ref) > i:
                warnings.append(f"策略组顺序建议: '{g['name']}' 引用 '{ref}'，但 '{ref}' 定义在后面（不影响功能，仅可读性）")


def check_group_refs(config, errors):
    """检查 5: 策略组中引用的代理/组是否存在"""
    groups = config.get('proxy-groups', [])
    all_group_names = {g['name'] for g in groups}
    all_proxy_names = set()
    for p in config.get('proxies', []):
        if isinstance(p, dict) and 'name' in p:
            all_proxy_names.add(p['name'])

    valid = all_group_names | all_proxy_names | {'直连', '拒绝', 'DIRECT', 'REJECT'}
    for g in groups:
        for ref in g.get('proxies', []):
            if ref not in valid and not ref.startswith('DIRECT') and not ref.startswith('REJECT'):
                errors.append(f"策略组 '{g['name']}' 引用了不存在的 '{ref}'")


def check_provider_naming(config, errors):
    """检查 6: 规则集命名格式必须为 'Name / Domain' 或 'Name / IP'"""
    providers = config.get('rule-providers', {})
    for name in providers:
        if ' / Domain' not in name and ' / IP' not in name:
            errors.append(f"命名格式错误: '{name}'（应为 'Name / Domain' 或 'Name / IP'）")


def check_anchor_format(config, errors):
    """检查 7: 锚点格式一致性（核心规则）
    - .mrs + domain  → format=mrs, behavior=domain
    - .mrs + ipcidr  → format=mrs, behavior=ipcidr
    - .list          → format=text, behavior=classical
    """
    providers = config.get('rule-providers', {})
    for name, rule in providers.items():
        if not isinstance(rule, dict) or 'url' not in rule:
            continue
        url = rule['url']
        behavior = rule.get('behavior', '')
        fmt = rule.get('format', '')
        is_mrs = '.mrs' in url
        is_list = '.list' in url

        if is_mrs:
            if fmt != 'mrs':
                errors.append(f"锚点格式: '{name}' 是 .mrs 文件，format 应为 mrs（当前: {fmt}）")
            if behavior not in ('domain', 'ipcidr'):
                errors.append(f"锚点格式: '{name}' 是 .mrs 文件，behavior 应为 domain 或 ipcidr（当前: {behavior}）")
        elif is_list:
            if behavior != 'classical' or fmt != 'text':
                errors.append(f"锚点格式: '{name}' 是 .list 文件，应为 behavior=classical, format=text（当前: behavior={behavior}, format={fmt}）")


def check_anchor_mismatch(config, errors):
    """检查 8: 名称中的 Domain/IP 与 behavior 是否匹配（仅 .mrs 文件）
    .list 文件 behavior=classical 是固定的，Domain/IP 只表示规则内容类型。
    .mrs 文件必须：/ Domain → behavior=domain，/ IP → behavior=ipcidr。
    """
    providers = config.get('rule-providers', {})
    for name, rule in providers.items():
        if not isinstance(rule, dict) or 'url' not in rule:
            continue
        url = rule['url']
        if '.mrs' not in url:
            continue  # .list 文件跳过，classical 行为固定
        behavior = rule.get('behavior', '')
        if ' / IP' in name and behavior != 'ipcidr':
            errors.append(f"名称/行为不匹配: '{name}' 含 / IP 但 behavior={behavior}（.mrs 文件必须为 ipcidr）")
        if ' / Domain' in name and behavior != 'domain':
            errors.append(f"名称/行为不匹配: '{name}' 含 / Domain 但 behavior={behavior}（.mrs 文件必须为 domain）")


def check_unreferenced_providers(config, errors):
    """检查 9: 规则集定义但未被 rules 引用（孤立规则集）"""
    providers = config.get('rule-providers', {})
    rules = config.get('rules', [])
    refs = extract_rule_refs(rules)
    unreferenced = set(providers.keys()) - refs
    for name in sorted(unreferenced):
        errors.append(f"孤立规则集: '{name}' 已定义但未被 rules 引用")


def check_dangling_refs(config, errors):
    """检查 10: rules 中引用的规则集是否都已定义"""
    providers = config.get('rule-providers', {})
    rules = config.get('rules', [])
    refs = extract_rule_refs(rules)
    dangling = refs - set(providers.keys())
    for name in sorted(dangling):
        errors.append(f"悬空引用: rules 引用了 '{name}' 但 rule-providers 中未定义")


def check_sensitive_fields(config, errors, raw_text=""):
    """检查 11: 敏感字段不得使用真实值，必须是占位符"""
    # 检查常见真实凭据模式
    sensitive_patterns = [
        (r'password:\s*["\']?[A-Za-z0-9]{8,}["\']?', '密码看起来像真实值，应使用占位符"你的密码"'),
        (r'server:\s*["\']?\d+\.\d+\.\d+\.\d+["\']?', 'IP 看起来像真实值，应使用占位符"你的住宅IP地址"'),
        (r'url:\s*["\']?http://10\.10\.10\.\d+[^"\']*["\']?', '使用了内网订阅 URL，应使用占位符'),
    ]

    if raw_text:
        for pattern, desc in sensitive_patterns:
            if re.search(pattern, raw_text):
                errors.append(f"敏感字段: {desc}")

    # 结构化检查：proxies 中的住宅节点
    for p in config.get('proxies', []):
        if isinstance(p, dict):
            name = p.get('name', '')
            server = str(p.get('server', ''))
            username = str(p.get('username', ''))
            password = str(p.get('password', ''))

            # 住宅节点必须使用占位符
            if '住宅' in name or 'residential' in name.lower():
                if '你的' not in server and server not in ('socks.l-home.top',):
                    errors.append(f"敏感字段: 住宅节点 server='{server}' 应使用占位符")
                if username and '你的' not in username:
                    errors.append("敏感字段: 住宅节点 username 应使用占位符")
                if '你的' not in password and len(password) > 6:
                    errors.append(f"敏感字段: 住宅节点 password 应使用占位符")

            # 回家节点必须使用占位符
            if 'home' in name.lower() or '回家' in name:
                if '你的' not in password and len(password) > 6:
                    errors.append(f"敏感字段: 回家节点 password 应使用占位符")

    # proxy-providers 订阅 URL
    for name, prov in config.get('proxy-providers', {}).items():
        if isinstance(prov, dict) and 'url' in prov:
            url = str(prov['url'])
            if '你的' not in url and 'example.com' not in url:
                if '10.10.10.' in url:
                    errors.append(f"敏感字段: proxy-provider '{name}' URL 应使用占位符")


def check_unique_match(config, errors):
    """检查 12: MATCH 规则必须唯一且在最后"""
    rules = config.get('rules', [])
    match_rules = [i for i, r in enumerate(rules) if isinstance(r, str) and r.startswith('MATCH,')]

    if len(match_rules) == 0:
        errors.append("规则检查: 缺少 MATCH 兜底规则")
    elif len(match_rules) > 1:
        errors.append(f"规则检查: 存在 {len(match_rules)} 个 MATCH 规则，必须唯一")
    elif match_rules[0] != len(rules) - 1:
        errors.append(f"规则检查: MATCH 规则在位置 {match_rules[0]}，必须是最后一条")


def check_policy_cycles(config, errors):
    """检查 13: 策略组引用循环（如 A→B→C→A）"""
    groups = config.get('proxy-groups', [])
    name_to_idx = {g['name']: i for i, g in enumerate(groups)}
    visited = set()

    def dfs(name, path):
        if name in path:
            cycle_start = path.index(name)
            cycle = " → ".join(path[cycle_start:] + [name])
            errors.append(f"策略循环: {cycle}")
            return
        if name in visited or name not in name_to_idx:
            return
        visited.add(name)
        path.append(name)
        idx = name_to_idx[name]
        for ref in groups[idx].get('proxies', []):
            if ref in name_to_idx:  # 只检查策略组，跳过真实代理和直连/拒绝
                dfs(ref, path)
        path.pop()

    for g in groups:
        if g['name'] not in visited:
            dfs(g['name'], [])


def check_duplicate_yaml_keys(raw_text, errors):
    """检查 14: 同一个 YAML mapping 内的重复键。"""
    duplicates = []

    class DuplicateKeyLoader(yaml.SafeLoader):
        pass

    def construct_mapping(loader, node, deep=False):
        seen = {}
        for key_node, _ in node.value:
            if not isinstance(key_node, yaml.ScalarNode) or key_node.value == '<<':
                continue
            key = key_node.value
            line = key_node.start_mark.line + 1
            if key in seen:
                duplicates.append((key, seen[key], line))
            else:
                seen[key] = line
        return yaml.SafeLoader.construct_mapping(loader, node, deep=deep)

    DuplicateKeyLoader.add_constructor(
        yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
        construct_mapping,
    )

    try:
        yaml.load(raw_text, Loader=DuplicateKeyLoader)
    except yaml.YAMLError:
        return  # YAML syntax errors are reported by load_config.

    for key, first_line, duplicate_line in duplicates:
        errors.append(
            f"YAML 重复键: 第 {first_line} 行和第 {duplicate_line} 行都定义了 '{key}'"
        )


def check_cross_config_consistency(config1, config2, errors, name1="config1", name2="config2"):
    """检查跨配置语义一致性和两端各自的私网路由约束。

    手机版允许的功能差异：
    1. 多一个 '回家' 代理节点
    2. 多一个 '回家开关' 策略组
    3. RFC1918 私网经回家开关，且 l-home.top 直连防回环
    """
    # 检查 rule-providers 必须完全一致
    rp1 = set(config1.get('rule-providers', {}).keys())
    rp2 = set(config2.get('rule-providers', {}).keys())
    if rp1 != rp2:
        only1 = sorted(rp1 - rp2)
        only2 = sorted(rp2 - rp1)
        if only1:
            errors.append(f"跨配置不一致: {name1} 独有的规则集: {', '.join(only1)}")
        if only2:
            errors.append(f"跨配置不一致: {name2} 独有的规则集: {', '.join(only2)}")

    # 检查策略组数量：手机版应该比家用版多 1 个（回家开关）
    groups1 = [g['name'] for g in config1.get('proxy-groups', [])]
    groups2 = [g['name'] for g in config2.get('proxy-groups', [])]

    # 除了回家开关，其他策略组名称必须一致
    g1_set = set(groups1)
    g2_set = set(groups2)
    diff = g1_set.symmetric_difference(g2_set)
    allowed_diff = {'回家开关'}
    if diff - allowed_diff:
        unexpected = sorted(diff - allowed_diff)
        errors.append(f"跨配置不一致: 不允许的策略组差异: {', '.join(unexpected)}")

    expected_counts = ((name1, config1, 25, 31), (name2, config2, 25, 32))
    for config_name, config, provider_count, group_count in expected_counts:
        actual_providers = len(config.get('rule-providers', {}))
        actual_groups = len(config.get('proxy-groups', []))
        if actual_providers != provider_count:
            errors.append(
                f"Layer 2 基线: {config_name} 应有 {provider_count} 个规则集，当前 {actual_providers} 个"
            )
        if actual_groups != group_count:
            errors.append(
                f"Layer 2 基线: {config_name} 应有 {group_count} 个策略组，当前 {actual_groups} 个"
            )

    private_cidrs = ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16')
    for config_name, config, policy in (
        (name1, config1, '直连'),
        (name2, config2, '回家开关'),
    ):
        rules = set(config.get('rules', []))
        for cidr in private_cidrs:
            expected = f"IP-CIDR,{cidr},{policy},no-resolve"
            if expected not in rules:
                errors.append(f"私网路由: {config_name} 缺少 '{expected}'")
        loopback = "IP-CIDR,127.0.0.0/8,直连,no-resolve"
        if loopback not in rules:
            errors.append(f"私网路由: {config_name} 缺少 '{loopback}'")

    mobile_rules = set(config2.get('rules', []))
    if "DOMAIN-SUFFIX,l-home.top,直连" not in mobile_rules:
        errors.append("手机版防回环: 缺少 'DOMAIN-SUFFIX,l-home.top,直连'")


def check_layer3_extension(extension_path, base_configs, errors):
    """验证 Layer 3 合并源的引用完整性，并阻止与主配置名称冲突。"""
    path = Path(extension_path)
    if not path.exists():
        errors.append(f"Layer 3 扩展不存在: {extension_path}")
        return

    raw_text = path.read_text(encoding='utf-8')
    provider_section, separator, remainder = raw_text.partition(
        '# ──────────────── 扩展策略组（proxy-groups 下复制） ────────────────'
    )
    if not separator:
        errors.append("Layer 3 扩展缺少策略组分隔标记")
        return
    group_section, separator, rules_section = remainder.partition(
        '# ──────────────── 扩展规则（rules 下复制） ────────────────'
    )
    if not separator:
        errors.append("Layer 3 扩展缺少规则分隔标记")
        return

    provider_names = set(re.findall(r'^  ([^#\n][^:]+ / (?:Domain|IP)):', provider_section, re.MULTILINE))
    group_names = set(re.findall(r'^- name:\s*(.+?)\s*$', group_section, re.MULTILINE))
    rule_matches = re.findall(r'^- RULE-SET,([^,]+),([^,\n]+)', rules_section, re.MULTILINE)
    rule_refs = {provider.strip() for provider, _ in rule_matches}
    policy_refs = {policy.strip() for _, policy in rule_matches}

    for name in sorted(provider_names - rule_refs):
        errors.append(f"Layer 3 孤立规则集: '{name}' 没有对应规则行")
    for name in sorted(rule_refs - provider_names):
        errors.append(f"Layer 3 悬空引用: 规则引用了未定义的 '{name}'")

    for config_name, config in base_configs:
        base_names = {
            item.get('name') for section in ('proxies', 'proxy-groups')
            for item in config.get(section, []) if isinstance(item, dict)
        }
        collisions = sorted(group_names & base_names)
        for name in collisions:
            errors.append(f"Layer 3 名称冲突: '{name}' 已存在于{config_name}主配置")

        valid_policies = base_names | group_names | {'DIRECT', 'REJECT', '直连', '拒绝'}
        for policy in sorted(policy_refs - valid_policies):
            errors.append(f"Layer 3 策略悬空: '{policy}' 在{config_name}主配置和扩展中均未定义")


def check_url_accessibility(config, warnings, timeout=5):
    """检查 11: URL 可访问性（仅警告，不阻断）"""
    providers = config.get('rule-providers', {})
    checked = 0
    for name, rule in providers.items():
        if not isinstance(rule, dict) or 'url' not in rule:
            continue
        url = rule['url']
        if url.startswith('file:'):
            continue
        checked += 1
        try:
            resp = requests.head(url, timeout=timeout, allow_redirects=True)
            if resp.status_code != 200:
                warnings.append(f"URL 不可达: '{name}' → HTTP {resp.status_code}")
        except Exception as e:
            warnings.append(f"URL 不可达: '{name}' → {str(e)[:60]}")
    return checked


def check_trailing_whitespace(config, warnings):
    """检查 12: 配置中常见的 YAML 写法问题（仅警告）"""
    # 这个需要读原始文本
    pass


def validate_config(filename, skip_url_check=False, url_timeout=5, raw_text=""):
    """运行所有验证检查"""
    print("=" * 60)
    print(f"验证配置文件: {filename}")
    print("=" * 60)

    errors = []
    warnings = []

    # 加载配置
    config, parse_err, raw_text = load_config(filename)
    if not check_yaml_syntax(config, errors):
        print(f"\n❌ YAML 语法错误:\n  {parse_err}")
        return errors, warnings, config, raw_text

    # 运行所有检查
    checks = [
        ("必需字段", check_required_fields),
        ("重复规则集", check_duplicate_providers),
        ("策略组引用有效性", check_group_refs),
        ("规则集命名格式", check_provider_naming),
        ("锚点格式一致性", check_anchor_format),
        ("名称/行为匹配", check_anchor_mismatch),
        ("孤立规则集", check_unreferenced_providers),
        ("悬空引用", check_dangling_refs),
        ("敏感字段占位符", lambda c, e: check_sensitive_fields(c, e, raw_text)),
        ["唯一 MATCH 规则", check_unique_match],
        ["策略循环检查", check_policy_cycles],
    ]

    warnings_checks = [
        ["YAML 重复键警告", lambda c, e: check_duplicate_yaml_keys(raw_text, warnings)],
    ]

    # 手机版按 UI 使用频率排列策略组，允许引用后置的基础组；Mihomo 不要求定义顺序。
    if Path(filename).name != 'config_mobile.yaml':
        warnings_checks.insert(0, ("策略组引用顺序", check_group_order))

    for i, (desc, fn) in enumerate(checks, 1):
        before = len(errors)
        print(f"\n[{i}/{len(checks) + len(warnings_checks) + (0 if skip_url_check else 1)}] {desc}...", end=" ")
        fn(config, errors)
        if len(errors) == before:
            print("✅")
        else:
            print(f"❌ +{len(errors) - before}")

    for i, (desc, fn) in enumerate(warnings_checks, 1):
        idx = i + len(checks)
        print(f"\n[{idx}/{len(checks) + len(warnings_checks) + (0 if skip_url_check else 1)}] {desc}...", end=" ")
        before = len(warnings)
        fn(config, warnings)
        if len(warnings) == before:
            print("✅")
        else:
            print(f"⚠️  +{len(warnings) - before}")

    # URL 检查（可选，较慢）
    if not skip_url_check:
        idx = len(checks) + len(warnings_checks) + 1
        print(f"\n[{idx}/{idx}] URL 可访问性...", end=" ")
        checked = check_url_accessibility(config, warnings, url_timeout)
        print(f"✅ 已检查 {checked} 个 URL（{len(warnings)} 个警告）")

    # 总结
    print("\n" + "=" * 60)
    print("验证结果")
    print("=" * 60)

    if errors:
        print(f"\n❌ {len(errors)} 个错误（必须修复，不能发布）:")
        for i, e in enumerate(errors, 1):
            print(f"  {i}. {e}")
    else:
        print("\n✅ 无错误，可以发布")

    if warnings:
        print(f"\n⚠️  {len(warnings)} 个警告（建议修复）:")
        for i, w in enumerate(warnings, 1):
            print(f"  {i}. {w}")

    return errors, warnings, config, raw_text


def main():
    parser = argparse.ArgumentParser(description='OpenClash 配置文件验证')
    parser.add_argument('files', nargs='*', default=['config_local.yaml', 'config_mobile.yaml'],
                        help='要验证的配置文件（默认: config_local.yaml config_mobile.yaml）')
    parser.add_argument('--skip-url', action='store_true', help='跳过 URL 可访问性检查')
    parser.add_argument('--url-timeout', type=int, default=5, help='URL 检查超时秒数')
    args = parser.parse_args()

    all_errors = []
    all_warnings = []
    configs = {}

    for filename in args.files:
        errors, warnings, config, raw_text = validate_config(filename, skip_url_check=args.skip_url,
                                                             url_timeout=args.url_timeout)
        all_errors.extend(errors)
        all_warnings.extend(warnings)
        configs[Path(filename).name] = config
        print()

    # 跨配置一致性检查（如果有两个配置文件）
    if len(configs) >= 2 and 'config_local.yaml' in configs and 'config_mobile.yaml' in configs:
        print("=" * 60)
        print("[边界] 跨配置与 Layer 2 基线检查...", end=" ")
        cross_errors = []
        check_cross_config_consistency(
            configs['config_local.yaml'], configs['config_mobile.yaml'],
            cross_errors, "家用版", "手机版"
        )
        if not cross_errors:
            print("✅")
        else:
            print(f"❌ +{len(cross_errors)}")
            for e in cross_errors:
                print(f"  - {e}")
        all_errors.extend(cross_errors)

        print("[边界] Layer 3 扩展完整性检查...", end=" ")
        extension_errors = []
        check_layer3_extension(
            Path(__file__).resolve().parent / 'extensions' / 'layer3_extra.yaml',
            [('家用版', configs['config_local.yaml']), ('手机版', configs['config_mobile.yaml'])],
            extension_errors,
        )
        if not extension_errors:
            print("✅")
        else:
            print(f"❌ +{len(extension_errors)}")
            for e in extension_errors:
                print(f"  - {e}")
        all_errors.extend(extension_errors)

    # 最终结论
    if len(args.files) > 1:
        print("=" * 60)
        print(f"总计: {len(all_errors)} 个错误, {len(all_warnings)} 个警告")
        if all_errors:
            print("❌ 发布前必须修复所有错误")
        else:
            print("✅ 所有检查通过，可以发布")
        print("=" * 60)

    sys.exit(1 if all_errors else 0)


if __name__ == '__main__':
    main()
