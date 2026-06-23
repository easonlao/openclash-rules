# Liandu Rule Audit

## Current extraction

- `Popcorn / Domain` only contains `DOMAIN-SUFFIX,popcorn.plus`
- hard-coded proxy IP ranges were extracted to:
  - [../list/Proxy_IPCIDR.review.list](../list/Proxy_IPCIDR.review.list)
- suspicious/personal proxy domains were extracted to:
  - [../list/Proxy_Personal.review.list](../list/Proxy_Personal.review.list)
- personal/direct whitelist domains were extracted to:
  - [../list/Direct_Personal.review.list](../list/Direct_Personal.review.list)

## Initial recommendation

### Delete first

- `Popcorn / Domain`

### Remove from generic baseline unless proven necessary

- all hard-coded `IP-CIDR` entries in `Proxy.list`
- airport/panel/personal domains in `Proxy_Personal.review.list`
- personal/direct whitelist domains in `Direct_Personal.review.list`

### Keep in generic baseline candidates

- mainstream CN domains from the vendor blocks in `Direct.list`
- public service domains with clear attribution in `Proxy.list`

## Notes

- `DOMAIN-SUFFIX,l-home.top` has been added into the review extraction for personal direct domains.
- `DOMAIN-KEYWORD,baidu` is too broad and should not stay in a generic baseline without a strong reason.
