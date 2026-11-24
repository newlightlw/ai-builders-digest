# 每日公开资料包

权威入口：[latest.json](latest.json)。只有 `status=ready` 时读取，并冻结其中的 `commit_sha` 后访问 `package_path`。SHA 指向包含完整日包的不可变提交，不是 latest 指针本身的提交。

日包包含 manifest、digest-pointer、incremental 和 source_status；既有根目录日期 Markdown 是独立的 remix 归档，保持原样。

- [固定来源清单与排除理由](../docs/source-catalog.md)
- [文件、日期、去重、发布及读取约定](../docs/daily-package-contract.md)
- [可重复运行的导出工具](../tools/export_daily_package.py)

## 限定发布

父级每日只调用这条分支路径，不调用导出器的 `--publish`（那条会在干净 main 上直接推送）：

```sh
python3 packages/limited_publish.py \
  --repo . \
  --feed-root /path/to/validated/public-feed \
  --body /path/to/final.md \
  --expected-head "$(git rev-parse HEAD)"
```

调用前切到干净的非 main 分支。`--body` 是已定稿 UTF-8 字节；`--feed-root` 提供冻结的 ready 指针、cutoff、incremental 和 source_status。正文日期必须等于 cutoff 的北京时间日期，因此不能用 2026-11-24 的冻结包去写 `2026-11-25.md`。

成功时先提交根目录当日 Markdown，再提交日包，最后更新 [latest.json](latest.json)。`commit_sha` 仍是日包提交，不是 latest 自身。新写入的 latest 额外带有 `digest_sha256` 和 `digest_commit`。同一正文和同一冻结输入再跑一次不会产生新提交，也不会改写已有权威指针。

缺正文、未就绪或缺少冻结文件、校验未通过、更旧 cutoff、改写既有正文、替换已有日包、工作区不干净、HEAD 与 `--expected-head` 不一致、或本机已有发布锁，都会以非 0 退出，并且不把旧 latest 写成成功。本命令不推送、不合并、不发通知。
