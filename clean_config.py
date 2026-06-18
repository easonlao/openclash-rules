import yaml

for fname in ['config_local.yaml', 'config_mobile.yaml']:
    with open(fname, 'r') as f:
        cfg = yaml.safe_load(f)

    # 删掉所有 dialer-proxy
    for p in cfg.get('proxies', []):
        p.pop('dialer-proxy', None)
    for g in cfg.get('proxy-groups', []):
        g.pop('dialer-proxy', None)

    # 删掉 住宅-中转
    cfg['proxy-groups'] = [g for g in cfg['proxy-groups'] if g.get('name') != '住宅-中转']

    # 验证
    bad = [g['name'] for g in cfg['proxy-groups'] if g.get('type') is None]
    dp = sum(1 for g in cfg['proxy-groups'] if 'dialer-proxy' in g)
    print(f'{fname}: {len(cfg["proxy-groups"])} groups, missing type={bad}, dialer-proxy={dp}')

    with open(fname, 'w') as f:
        yaml.dump(cfg, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
    print(f'✅ {fname} 已更新')
