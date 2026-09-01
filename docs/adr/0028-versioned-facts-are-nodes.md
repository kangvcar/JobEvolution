# 版本化岗位事实使用节点存储

`RequirementVersion` 节点连接岗位、技能点、要求组、证据和审核记录,API 与图谱画布再把当前获批版本投影为要求边;不再把版本字段和证据 ID 塞进 `REQUIRES` 关系。`JobDefinitionVersion` 连接多个 `DefinitionClaim`,每条声明连接自己的证据和审核记录,岗位指向当前获批定义版本。预览与正式事实保存在同一个 Neo4j,依靠显式发布状态隔离;公开查询只读取 `approved` 与 `auto_passed`,不维护第二个图库。
