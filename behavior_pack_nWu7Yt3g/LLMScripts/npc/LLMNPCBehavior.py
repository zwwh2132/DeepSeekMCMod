# -*- coding: utf-8 -*-
"""
LLMNPCBehavior — NPC 实体的 python_custom 行为节点

在 Tick() 中：
1. 检查动作队列（内存中）是否有待执行动作
2. 如果有 → 按顺序执行（导航、动画等）
3. 执行 follow_player 模式的持续追踪
4. 执行 attack_entity 模式的追击+近战伤害
"""
import mod.server.extraServerApi as serverApi

CustomGoalCls = serverApi.GetCustomGoalCls()


# 动作队列管理器（纯内存，不落盘）
class ActionQueueManager(object):
    """每个 NPC 实体的待执行动作队列"""
    _queues = {}  # {entityId: [action_dict, ...]}

    @classmethod
    def push(cls, entityId, action):
        """追加一个动作到队列末尾"""
        if entityId not in cls._queues:
            cls._queues[entityId] = []
        cls._queues[entityId].append(action)

    @classmethod
    def pop(cls, entityId):
        """从队列头部取出一个动作，取完自动清理"""
        queue = cls._queues.get(entityId)
        if not queue:
            return None
        action = queue.pop(0)
        if not queue:
            del cls._queues[entityId]
        return action

    @classmethod
    def clear(cls, entityId):
        """清空某个实体的动作队列"""
        cls._queues.pop(entityId, None)

    @classmethod
    def has_pending(cls, entityId):
        """是否还有待执行动作"""
        return bool(cls._queues.get(entityId))


class LLMNPCBehavior(CustomGoalCls):
    def __init__(self, entityId, argsJson):
        CustomGoalCls.__init__(self, entityId, argsJson)
        self.entityId = entityId
        self.factory = serverApi.GetEngineCompFactory()
        self.moveToComp = self.factory.CreateMoveTo(entityId)
        self.posComp = self.factory.CreatePos(entityId)
        self.rotComp = self.factory.CreateRot(entityId)
        self.motionComp = self.factory.CreateActorMotion(entityId)
        self.extraData = self.factory.CreateExtraData(entityId)

        # 缓存玩家列表
        self._player_list = []
        self._tick_count = 0

        print("[LLMNPCBehavior] 初始化完成 entityId: %s" % entityId)

    def CanUse(self):
        return True

    def CanContinueToUse(self):
        return True

    def CanBeInterrupted(self):
        return False

    def Start(self):
        pass

    def Stop(self):
        pass

    def Tick(self):
        self._tick_count += 1

        # ① 检查是否有待执行动作
        action = ActionQueueManager.pop(self.entityId)
        if action:
            self._execute_action(action)

        # ② 如果是跟随模式，持续追踪玩家（每 40 tick = 2秒 更新一次导航）
        if self._tick_count % 40 == 0:
            self._update_follow()

        # ③ 攻击模式：追击+伤害（每 10 tick = 0.5秒 更新，每 20 tick 造成伤害）
        if self._tick_count % 10 == 0:
            self._update_attack()

    def _execute_action(self, action):
        """执行单个动作（来自 ActionTool 的调用结果）"""
        try:
            tool_name = action.get("tool", "")
            args = action.get("args", {})

            # move_to 已经由 ActionTool.execute() 直接调用了
            # 但 move_to_player 需要在 context 中有 playerId
            # 这些都在 LLMServerSystem 中处理了
            # 这里主要处理持续性的动作状态
            if tool_name == "follow_player":
                # follow 由 _update_follow 持续驱动
                pass
            elif tool_name == "stop":
                self.motionComp.SetMotion((0, 0, 0))
            elif tool_name == "look_at":
                pitch = args.get("pitch", 0)
                yaw = args.get("yaw", 0)
                self.rotComp.SetRot((pitch, yaw))

        except Exception as e:
            print("[LLMNPCBehavior] 执行动作异常: %s" % str(e))

    def _update_follow(self):
        """跟随模式：持续向目标玩家导航"""
        targetPlayerId = self.extraData.GetExtraData("follow_target_player")
        if not targetPlayerId:
            return

        playerPos = self.posComp.GetPos()  # 先获取自己的位置
        # 检查目标玩家仍然在线
        playerList = serverApi.GetPlayerList()
        if targetPlayerId not in playerList:
            self.extraData.SetExtraData("follow_target_player", "")
            return

        # 获取目标位置并导航
        targetPosComp = self.factory.CreatePos(targetPlayerId)
        targetPos = targetPosComp.GetPos()
        if targetPos:
            self.moveToComp.SetMoveSetting(
                (targetPos[0], -1, targetPos[2]),
                1.0, 500, None
            )

    def _update_attack(self):
        """攻击模式：追击目标并在近战范围内造成伤害"""
        targetId = self.extraData.GetExtraData("attack_target_id")
        if not targetId:
            return

        # 检查目标是否还活着（靠生命值判定）
        try:
            targetAttr = self.factory.CreateAttr(targetId)
            mcEnum = serverApi.GetMinecraftEnum()
            health = targetAttr.GetAttrValue(mcEnum.AttrType.HEALTH)
            if health is None or health <= 0:
                print("[LLMNPCBehavior] 攻击目标已死亡(health=%s)，清除攻击模式: %s" % (health, targetId))
                self.extraData.SetExtraData("attack_target_id", "")
                self.extraData.SetExtraData("attack_target_name", "")
                self.extraData.SetExtraData("attack_damage", "")
                return
        except Exception:
            # 目标组件获取失败=目标已失效
            self.extraData.SetExtraData("attack_target_id", "")
            self.extraData.SetExtraData("attack_target_name", "")
            self.extraData.SetExtraData("attack_damage", "")
            return

        # 获取自己和目标的位置
        myPos = self.posComp.GetPos()
        if not myPos:
            return

        try:
            targetPosComp = self.factory.CreatePos(targetId)
            targetPos = targetPosComp.GetFootPos()
        except Exception:
            # 目标可能已失效
            self.extraData.SetExtraData("attack_target_id", "")
            return

        if not targetPos:
            return

        # 计算水平距离
        dx = myPos[0] - targetPos[0]
        dz = myPos[2] - targetPos[2]
        dist = (dx * dx + dz * dz) ** 0.5

        attackRange = 2.5  # 近战攻击范围

        if dist <= attackRange:
            # 在攻击范围内，造成伤害
            # 每 20 tick（=每2次 _update_attack 调用）才造成一次伤害
            if self._tick_count % 20 == 0:
                try:
                    damageStr = self.extraData.GetExtraData("attack_damage")
                    damage = float(damageStr) if damageStr else 10.0
                    hurtComp = self.factory.CreateHurt(targetId)
                    mcEnum = serverApi.GetMinecraftEnum()
                    hurtComp.Hurt(damage, mcEnum.ActorDamageCause.EntityAttack, self.entityId, self.entityId, False)
                except Exception as e:
                    print("[LLMNPCBehavior] 攻击伤害异常: %s" % e)
        else:
            # 在攻击范围外，追击
            self.moveToComp.SetMoveSetting(
                (targetPos[0], -1, targetPos[2]),
                1.5, 500, None
            )

    def OnDestroy(self):
        """实体销毁时的清理"""
        ActionQueueManager.clear(self.entityId)
        print("[LLMNPCBehavior] 实体销毁，清除动作队列 entityId: %s" % self.entityId)
