## 新版国内站适配（2026-10-18）

使用 `app.igpsport.cn` 对应的 API，支持请求签名、Token 登录、记录详情和 FIT 下载。
默认检查 IGP 最近 20 条记录中的骑行记录，按完整开始时间与行者记录去重；不是全历史迁移工具。
行者记录分页读取。原有佳明与国际站支持状态不变。

在仓库 Settings → Secrets and variables → Actions 设置 `USERNAME`、`PASSWORD`。
只填值，不加引号；当前仍要求 IGP 和行者使用相同账号密码。不要填写 GARMIN_PASSWORD，除非要运行旧佳明分支。
然后 Actions → IGPSport Data Sync To Xingzhe → Run workflow 手动执行。

本地运行：`python -m pip install -r requirements.txt`，通过环境变量提供凭据后执行 `python ActivitySync.py`。
离线测试：`python -m unittest -v`。测试不使用真实凭据，不执行网络同步。
请勿将密码、Token、下载签名 URL 提交到仓库。

签名 Python 代码来源及许可证见 `igp_vendor/`。WASM 来自该参考项目收录的官方前端文件，其独立上游许可证尚未确认。
验证结果：9 个离线回归测试通过；已在线验证公开密钥握手及 WASM 签名生成。
目前为本地适配版本；尚未完成真实账号的端到端同步验证。接口和前端版本以后仍可能变化。


# IGPSPORT骑行记录同步行者(ActivitySync.py)


# <b>佳明渠道已经无法进行使用</b>

- [功能说明和操作流程说明](https://abigeater.com/archives/511)
- 支持把佳明数据同步到行者
- <del>支持国际版IGPSPORT</del>（igp更新了版本 需要适配)
- [2025/02/20]更新行者登录密码算法，请Fork的拉取一下代码（别光Fork呀点点Star，球球了）
- [2025/08/07]<del>更新igpsport的文件获取</del>
- [2025/08/08]更新igpsport的文件获取

<del>

# 佳明大陆区同步跑步数据到国际区(GarminSync.py)
- 账号设计复用上面的操作文档，要求大陆区和国际区同一个账号密码（可自行修改代码成不同的）
- 变量名修改成：GARMIN_RUN_EMAIL(登录邮箱)，GARMIN_RUN_PASSWORD(登录密码)
- 脚本默认仅同步执行的前5条大陆区数据
- 如果需要同步全部数据 clone 到本地后 修改大陆区limit条件大于你的记录数并且即可
- 该脚本为同步跑步数据，需要骑行数据修改获取的type（已注释）即可。
- 已知问题：偶尔可能登录失败，需重新执行

</del>

# 付费服务 - 数据同步平台
- 非<b>个人需求</b>但看挺多人问的，所以花了时间整理了下，做了个付费平台有意愿可以使用，该仓库服务已满足需求的就不用再买啦~
- 网站：http://d2d.abigeater.com
- 支持各个平台互相转换，目前支持：IGPSport，行者，<del>国际版佳明，大陆版佳明</del>，高驰，迈金，IGPSport国际版
- 若使用该付费服务出现问题可邮箱联系：abigeater@163.com