# 每日公开资料包

权威入口：[latest.json](latest.json)。只有 `status=ready` 时读取，并冻结其中的 `commit_sha` 后访问 `package_path`。SHA 指向包含完整日包的不可变提交，不是 latest 指针本身的提交。

日包包含 manifest、digest-pointer、incremental 和 source_status；既有根目录日期 Markdown 是独立的 remix 归档，保持原样。

- [固定来源清单与排除理由](../docs/source-catalog.md)
- [文件、日期、去重、发布及读取约定](../docs/daily-package-contract.md)
- [可重复运行的导出工具](../tools/export_daily_package.py)

## 早报发布日与冻结源

[latest.json](latest.json) 仍是采集日包的权威入口。它的 `date` 和 `cutoff` 是采集批次的北京时间，不是早报发布日。契约规定 09:00 编辑使用前一日 18:00 批次：已发布的 `2026-11-24.md` 对应该前一日截止；下一期 `2026-11-25.md` 使用本目录已钉住的 `2026-11-24T18:05:20.756572+08:00` 冻结包。不要把发布日写成 cutoff 日期，也不要为了发 11-25 再造一份采集包。

调用方需要已经在仓库里的四份不可变文件，由 `latest.json` 的 `commit_sha` 钉住：

- `manifest.json`
- `digest-pointer.json`
- `incremental.jsonl`
- `source_status.json`

不需要、也不接受 `validated/public-feed` 或 `--feed-root`。没有这四文件和 ready 指针时，本路径不能标成 ready。

在干净的非 main 分支上，于发布日当天调用：

```sh
python3 packages/limited_publish.py \
  --repo . \
  --body /path/to/final.md \
  --publication-date 2026-11-25 \
  --expected-head "$(git rev-parse HEAD)"
```

正式调用不要传 `--now`。成功时只新增该发布日的根目录 Markdown、`publications/<发布日>.json` 和 [publication-latest.json](publication-latest.json)。`source_commit_sha` 仍是冻结日包提交。`collection_created` 为 false。发布记录同时写明 `publication_date` 与 `source_date` / `source_cutoff`。采集用的 `latest.json` 和既有日期包保持原字节。

同一正文、同一发布日、同一冻结提交再跑一次不会产生新提交。未来截止时间、发布日不晚于源批次、退回更早的发布指针、覆盖历史正文、源哈希不符、增量或来源状态缺失、工作区不干净、HEAD 不一致或发布锁占用，都会失败且不写出 ready。发布时刻晚于截止超过 36 小时时，记录里的 `lag_notice` 必须保留，覆盖计数仍等于冻结批次全文。本命令不采集、不推送、不合并、不发通知。
