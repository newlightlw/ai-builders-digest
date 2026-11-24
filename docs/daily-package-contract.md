# 干净日包：读取与发布约定

本仓库根目录已有的 `YYYY-MM-DD.md` 是每日 remix 归档。本工具不新增、覆盖、改名或删除这些归档，也不代替编辑写稿。

## 唯一读取入口

1. 先读 `packages/latest.json`。仅 `status == "ready"` 时继续。
2. 冻结 `commit_sha`，再从该 SHA 读取 `package_path` 下的四个文件。不要继续按 main 混读后续版本。
3. 核对 manifest 的 status、cutoff、文件 SHA-256、数量和 source_status。部分、失败、空集和禁用均保留。
4. `digest_path` 指向既有同日 remix，可能为 null（等待编辑）。`digest-pointer.json` 保存它的独立提交及字节哈希。既有晨间 remix 不能声称取材自当日傍晚的新采集包。

`date` 是采集 cutoff 的北京时间日期；09:00 编辑通常使用前一日18:00批次。抓取延迟时保留真实 cutoff，不能回填历史快照。

## 为什么是两个提交

先提交完整数据包，再提交 latest 指针。因此 `commit_sha` 是**包含日包的不可变提交**，不是包含 latest 指针自身的提交。若把自身提交 SHA 写进自身文件，会产生循环依赖。所有读取路径在 package commit 中确实存在。

首次正式日包可填充此前只有 `[]`/`{}` 的空占位文件；已有真实包保持不可变。相同输入幂等；同日输入或来源策略变化写入 `packages/YYYY-MM-DD/revisions/<cutoff-time>-<fingerprint>/`，latest 指向该版本。根目录日期归档始终保持原字节。

## 处理范围

- 上游已验证公开采集批次 → 固定来源白名单 → 移除导航/共享列表 → 泛媒体及产品发现标题AI相关性过滤 → 精确URL/arXiv身份归组 → 每源预算。
- 来源完整决策见 [source-catalog.md](source-catalog.md) 和 [source_policy.json](../tools/source_policy.json)。排除固定出口不等于删除上游档案。
- incremental 只含首次入库或字段变化的公开元数据；原始时间字段和R编号保留。正文补抓、证据核验、语义事件去重和中文成稿由编辑继续完成。
- `filtered_counts` 分别记录排除来源、非AI标题、材料不足、重复和预算延后；这些不是永久删除。
- 不上传私人听众卡、用户记忆、配置、群标识、凭证、SQLite、原始HTTP响应、整篇文章或本机绝对路径。
- X汇编不等于完整点赞转发图谱；榜单、收录、论文推荐日不等于首发日；首次入库不等于新新闻。

## 执行

需要 Python 3.10+、git 和已经授权给本仓库的 Git 凭证。工具无第三方Python依赖。

```sh
python3 tools/export_daily_package.py --feed-root /path/to/validated/public-feed
python3 tools/export_daily_package.py --feed-root /path/to/validated/public-feed --publish
python3 -m unittest discover -s tests -v
```

`--publish` 要求干净 main，先 fast-forward 拉取；只提交自己的日包路径及 latest，普通 push，绝不 force push。失败保留已有远端指针；若推送结果不明，先查远端提交，不重复创建日包。source_status 中的 keep/exclude 与实际可用状态是两个维度，不能互相替代。

Grok 的9点成稿排程由其既有任务管理；本工具只更新资料包，不发群、不向Bot发消息、不启动付费模型或创建新的9点任务。
