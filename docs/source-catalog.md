# 情报与内容编辑：固定信息源清单

基于已注册83源及2026-11-24实际采集结果整理。保留 61 源，固定日包排除 22 源。频率是栏目性质，不是发布承诺；可用性以每个日包source_status为准。失败的一手源保留缺口，不能因今天失败就永久删除。

日报围绕4–5个主题：国内外模型、大厂与产品、真实应用/具身、研究、安全或商业；开发工具与Skill最多一个主题。资料不足宁缺毋滥。本清单不是编辑选题的机械篇幅分配。

## 海外厂商与模型

|名称|入口|更新频率|获取方式|本次状态|
|---|---|---|---|---|
|Google Research Blog|[google_research](https://research.google/blog/)|事件驱动／不定期发布（不承诺日更）|feed|ok|
|OpenAI News|[openai_news](https://openai.com/news/)|事件驱动／不定期发布（不承诺日更）|feed|ok|
|Claude官方文章|[claude_articles](https://claude.com/resources/articles)|事件驱动／不定期发布（不承诺日更）|html、sitemap|partial|
|Anthropic News|[anthropic_news](https://www.anthropic.com/news)|事件驱动／不定期发布（不承诺日更）|html、sitemap|partial|
|Anthropic Engineering|[anthropic_engineering](https://www.anthropic.com/engineering)|事件驱动／不定期发布（不承诺日更）|html、sitemap|partial|
|Google DeepMind Blog|[deepmind](https://deepmind.google/blog/)|事件驱动／不定期发布（不承诺日更）|feed|ok|
|Gemini官方博客|[gemini_blog](https://blog.google/products/gemini/)|事件驱动／不定期发布（不承诺日更）|feed|ok|
|Microsoft AI Source|[microsoft_ai](https://news.microsoft.com/source/topics/ai/)|事件驱动／不定期发布（不承诺日更）|feed、html|partial|
|Microsoft Research|[microsoft_research](https://www.microsoft.com/en-us/research/blog/)|事件驱动／不定期发布（不承诺日更）|feed、html|partial|
|Meta AI Blog|[meta_ai](https://ai.meta.com/blog/)|事件驱动／不定期发布（不承诺日更）|html|empty_partial|
|NVIDIA Blog|[nvidia_blog](https://blogs.nvidia.com/)|事件驱动／不定期发布（不承诺日更）|feed|ok|
|NVIDIA Technical Blog|[nvidia_technical](https://developer.nvidia.com/blog/)|事件驱动／不定期发布（不承诺日更）|feed|ok|
|xAI News|[xai_news](https://x.ai/news)|事件驱动／不定期发布（不承诺日更）|html|partial|

## 国内厂商与模型

|名称|入口|更新频率|获取方式|本次状态|
|---|---|---|---|---|
|阿里/千问官方技术|[alibaba_qwen](https://qwen.ai/blog)|事件驱动／不定期发布（不承诺日更）|github_org_repos、github_releases、html_documents|partial|
|字节Seed/火山官方|[bytedance_seed](https://seed.bytedance.com/en/)|事件驱动／不定期发布（不承诺日更）|html_cards|empty_partial|
|腾讯混元/元宝官方|[tencent_hunyuan](https://github.com/Tencent-Hunyuan)|事件驱动／不定期发布（不承诺日更）|github_org_repos、html_cards|partial|
|小米MiMo/产品官方|[xiaomi_mimo](https://github.com/XiaomiMiMo)|事件驱动／不定期发布（不承诺日更）|github_org_repos、github_releases|partial|
|智谱官方|[zhipu](https://github.com/zai-org)|事件驱动／不定期发布（不承诺日更）|github_org_repos、github_releases、markdown_index|partial|
|阶跃星辰官方|[stepfun](https://www.stepfun.com/)|事件驱动／不定期发布（不承诺日更）|github_org_repos|partial|
|MiniMax官方|[minimax](https://www.minimax.io/news)|事件驱动／不定期发布（不承诺日更）|dated_sections、github_org_repos、html_cards|partial|
|DeepSeek官方|[deepseek](https://api-docs.deepseek.com/)|事件驱动／不定期发布（不承诺日更）|dated_sections、github_org_repos|partial|
|Kimi官方|[kimi](https://platform.kimi.com/docs/llms.txt)|事件驱动／不定期发布（不承诺日更）|github_org_repos、markdown_index|partial|
|百度官方技术与IR|[baidu](https://github.com/PaddlePaddle)|事件驱动／不定期发布（不承诺日更）|github_org_repos、github_releases|partial|
|华为盘古/年报|[huawei](https://www.huaweicloud.com/product/pangu.html)|事件驱动／不定期发布（不承诺日更）|html|partial|
|快手/可灵官方|[kuaishou_kling](https://www.klingai.com/)|事件驱动／不定期发布（不承诺日更）|github_org_repos|empty_partial|

## 具身与物理AI

|名称|入口|更新频率|获取方式|本次状态|
|---|---|---|---|---|
|Tesla IR|[tesla_ir](https://ir.tesla.com/)|事件驱动／不定期发布（不承诺日更）|feed、html、sec|partial|
|宇树官方|[unitree](https://www.unitree.com/cn/news/)|事件驱动／不定期发布（不承诺日更）|github_org_repos、html_cards|partial|
|智元官方开发|[agibot](https://github.com/AgibotTech)|事件驱动／不定期发布（不承诺日更）|github_org_repos|partial|
|Figure官方|[figure](https://www.figure.ai/news)|事件驱动／不定期发布（不承诺日更）|html_cards|empty_partial|
|Physical Intelligence官方|[physical_intelligence](https://www.pi.website/blog)|事件驱动／不定期发布（不承诺日更）|html_cards|failed|
|Boston Dynamics官方|[boston_dynamics](https://bostondynamics.com/blog/)|事件驱动／不定期发布（不承诺日更）|feed、html_cards|partial|

## 论文与研究

|名称|入口|更新频率|获取方式|本次状态|
|---|---|---|---|---|
|Hugging Face Blog|[hf_blog](https://huggingface.co/blog)|事件驱动／不定期发布（不承诺日更）|feed|ok|
|Hugging Face Papers|[hf_papers](https://huggingface.co/papers)|每日榜单、收录或汇编；可能有空档|hf|ok|
|arXiv研究发现|[arxiv](https://arxiv.org/)|按arXiv工作日公告；实际按抓取窗口核验|arxiv|ok|

## 工程与开发实践

|名称|入口|更新频率|获取方式|本次状态|
|---|---|---|---|---|
|GitHub Changelog|[github_changelog](https://github.blog/changelog/)|事件驱动／不定期发布（不承诺日更）|feed|ok|
|Cursor Changelog|[cursor_changelog](https://cursor.com/changelog)|事件驱动／不定期发布（不承诺日更）|feed|ok|
|Claude Code Releases|[claude_code_releases](https://github.com/anthropics/claude-code/releases)|事件驱动／不定期发布（不承诺日更）|github_releases|ok|
|GitHub Trending日周榜|[github_trending](https://github.com/trending)|每日榜单、收录或汇编；可能有空档|trending|partial|
|重点GitHub仓库元信息与Releases|[github_repository](https://docs.github.com/en/rest)|事件驱动／不定期发布（不承诺日更）|feed、github_releases|ok|
|Simon Willison|[simon_willison](https://simonwillison.net/)|事件驱动／不定期发布（不承诺日更）|feed|ok|

## 产品发现与玩法

|名称|入口|更新频率|获取方式|本次状态|
|---|---|---|---|---|
|WaytoAGI社区日报|[waytoagi](https://daily.waytoagi.com/)|每日榜单、收录或汇编；可能有空档|feed、html|empty_partial|
|Product Hunt|[product_hunt](https://www.producthunt.com/)|每日榜单、收录或汇编；可能有空档|feed|ok|
|Show HN|[hn_show](https://news.ycombinator.com/show)|日内滚动／高频；并非每条都属于AI|hn|ok|
|BetaList|[betalist](https://betalist.com/)|每日榜单、收录或汇编；可能有空档|feed|partial|
|YC Launch|[yc_launch](https://www.ycombinator.com/launches)|事件驱动／不定期发布（不承诺日更）|yc|ok|
|FutureTools|[futuretools](https://futuretools.io/)|事件驱动／不定期发布（不承诺日更）|html|partial|

## 人物与组织判断

|名称|入口|更新频率|获取方式|本次状态|
|---|---|---|---|---|
|follow-builders|[follow_builders](https://github.com/zarazhangrui/follow-builders)|每日榜单、收录或汇编；可能有空档|follow|partial|
|Sam Altman个人博客|[sam_altman](https://blog.samaltman.com/)|事件驱动／不定期发布（不承诺日更）|feed、html|partial|
|Dario Amodei个人文章|[dario_amodei](https://darioamodei.com/)|事件驱动／不定期发布（不承诺日更）|html|empty_partial|
|One Useful Thing / Ethan Mollick|[one_useful_thing](https://www.oneusefulthing.org/)|事件驱动／不定期发布（不承诺日更）|feed|ok|

## 独立媒体与产业

|名称|入口|更新频率|获取方式|本次状态|
|---|---|---|---|---|
|The Decoder|[the_decoder](https://the-decoder.com/)|日内滚动／高频；并非每条都属于AI|feed|ok|
|IT之家|[ithome](https://www.ithome.com/)|日内滚动／高频；并非每条都属于AI|feed|partial|
|SemiAnalysis|[semianalysis](https://semianalysis.com/)|事件驱动／不定期发布（不承诺日更）|feed|ok|
|TechCrunch AI|[techcrunch_ai](https://techcrunch.com/category/artificial-intelligence/)|日内滚动／高频；并非每条都属于AI|feed|ok|
|36氪|[36kr](https://www.36kr.com/)|日内滚动／高频；并非每条都属于AI|feed|partial|

## 中文应用案例

|名称|入口|更新频率|获取方式|本次状态|
|---|---|---|---|---|
|小红书技术REDtech|[xiaohongshu_tech_wechat](https://mp.weixin.qq.com/s?__biz=Mzg4OTc2MzczNg%3D%3D&mid=2247496927&idx=1&sn=5bdb6dfef74cdd8442eef924e7ad9c15)|事件驱动／不定期发布（不承诺日更）|feed|partial|
|数字生命卡兹克|[kazike_wechat](https://mp.weixin.qq.com/s?__biz=MzIyMzA5NjEyMA%3D%3D&mid=2647688028&idx=1&sn=e509269da2e0e0b4d4dfbb121b42204b)|事件驱动／不定期发布（不承诺日更）|feed|partial|

## 商业与披露

|名称|入口|更新频率|获取方式|本次状态|
|---|---|---|---|---|
|Yahoo Finance|[yahoo_finance](https://finance.yahoo.com/)|日内滚动／高频；并非每条都属于AI|feed|partial|
|NVIDIA IR|[nvidia_ir](https://investor.nvidia.com/)|定期报告＋事件披露|feed|ok|
|SEC EDGAR|[sec_edgar](https://www.sec.gov/search-filings/edgar-application-programming-interfaces)|定期报告＋事件披露|sec|partial|
|港交所披露易|[hkexnews](https://www.hkexnews.hk/index.htm)|定期报告＋事件披露|hkex_query|ok|

## 排除与按需补查

|来源|原因|
|---|---|
|Google AI主题博客|与Gemini/DeepMind/Google Research专题高度交叉，包层保留更具体官方栏目|
|AIbase|聚合与二次转述较多，已保留IT之家、36氪及厂商原始公告|
|Cursor Blog|当前编辑入口保留更新日志；深度博客按需检索，避免开发工具占比膨胀|
|Emad Mostaque|当前实际入口为团队博客，不能代表本人X；人物动态由follow-builders统一作为线索|
|OpenClaw官方内容|窄工具来源，重点仓库发布及GitHub变更足以发现，按需补查|
|Artificial Intelligence News|宽泛二次媒体，与已保留独立媒体重叠较多|
|MarkTechPost|论文二次改写较多，优先arXiv/HF原始研究发现|
|The Verge AI|二次科技报道与现有海外媒体重叠，按需补证|
|Hacker News热点|泛HN投稿量过大且包含非AI；保留Show HN中AI相关产品发现|
|V2EX技术与AI节点|泛技术社区噪声高，无法用来源级白名单保证AI相关|
|Readhub AI|聚合转述，与厂商原稿及IT之家重复|
|虎嗅|当前连接不稳定且聚合重复较高，暂不进入固定日包|
|Techmeme|聚合重复较高，按需作为发现线索|
|Google News|既有许可约束，保持禁用|
|Bloomberg Technology|付费/标题级证据较多；市场事实优先官方披露，必要时编辑另补证|
|TechRadar AI|消费科技二次稿与产品原始入口重复|
|巨潮资讯|现配置为泛关键词标题样本，AI相关性及发行人范围不足；需定向公司配置后再启用|
|AI工具集|滚动工具目录且当前TLS失败，产品发现由PH/BetaList/YC/FutureTools覆盖|
|MIT News / Artificial intelligence|研究宣传层；固定论文入口优先arXiv/HF，大学新闻按需补查|
|WorkBuddy官方文档与更新日志|窄开发工具更新，暂不占用固定入口；开发主题已有GitHub官方变更与仓库发布，按需补查|
|Canva Design School|课程/教程常青内容，不适合作为每日增量新闻|
|Shopify官方电商与营销博客|宽泛电商与营销内容，AI信号密度不足|

完整逐源入口见[source_policy.json](../tools/source_policy.json)。文章URL精确归组或arXiv ID归组不等于新闻事件语义去重。X转录不能冒充全量点赞、转发；榜单与产品收录时间不能冒充首发时间。
