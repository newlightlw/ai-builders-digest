# 每日公开资料包

权威入口：[latest.json](latest.json)。只有 `status=ready` 时读取，并冻结其中的 `commit_sha` 后访问 `package_path`。SHA 指向包含完整日包的不可变提交，不是 latest 指针本身的提交。

日包包含 manifest、digest-pointer、incremental 和 source_status；既有根目录日期 Markdown 是独立的 remix 归档，保持原样。

- [固定来源清单与排除理由](../docs/source-catalog.md)
- [文件、日期、去重、发布及读取约定](../docs/daily-package-contract.md)
- [可重复运行的导出工具](../tools/export_daily_package.py)
